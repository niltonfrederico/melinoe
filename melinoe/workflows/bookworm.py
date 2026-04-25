"""BookwormWorkflow: orchestrates the full book identification and analysis pipeline."""

import json
import re
import shutil
from dataclasses import asdict
from dataclasses import replace as dc_replace
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import ClassVar

import melinoe.settings as settings
from melinoe.clients.meilisearch import MeilisearchClient
from melinoe.clients.meilisearch import build_book_document
from melinoe.clients.seaweedfs import SeaweedFSClient
from melinoe.logger import workflow_log
from melinoe.workflows.base import Step
from melinoe.workflows.base import Workflow
from melinoe.workflows.base import merged_confidence
from melinoe.workflows.skills.book_lookup import BookLookupSkill
from melinoe.workflows.skills.book_lookup import BookMetadata
from melinoe.workflows.skills.cover_analyzer import CoverAnalyzerSkill
from melinoe.workflows.skills.hecate import HecateSkill
from melinoe.workflows.skills.load_relevant_memory import LoadRelevantMemorySkill
from melinoe.workflows.skills.loader import load_agent
from melinoe.workflows.skills.loader import load_soul
from melinoe.workflows.skills.title_page_analyzer import TitlePageAnalysis
from melinoe.workflows.skills.title_page_analyzer import TitlePageAnalyzerSkill
from melinoe.workflows.skills.write_memory import WriteMemorySkill


class NotABookCoverError(Exception):
    """Raised when the image does not contain a legible book cover."""


class BookAlreadyRegisteredError(Exception):
    """Raised when a matching memory already exists and force_update is False."""

    def __init__(self, memory_keys: list[str], title: str, author: str | None) -> None:
        self.memory_keys = memory_keys
        self.title = title
        self.author = author
        super().__init__(f"Book already registered: {title!r}")


_OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


class BookwormWorkflow(Workflow):
    agent = "bookworm"

    def __init__(self) -> None:
        self._agent_def = load_agent("bookworm")
        self._soul_def = load_soul("bibliophile")
        self._hecate = HecateSkill()
        self._load_memory = LoadRelevantMemorySkill()
        self._cover_analyzer = CoverAnalyzerSkill()
        self._title_page_analyzer = TitlePageAnalyzerSkill()
        self._book_lookup = BookLookupSkill()
        self._write_memory = WriteMemorySkill()
        self.steps: list[Step] = [
            self._hecate,
            self._load_memory,
            self._cover_analyzer,
            self._title_page_analyzer,
            self._book_lookup,
            self._write_memory,
        ]
        super().__init__()

    @property
    def system_prompt(self) -> str:
        return f"{self._soul_def.system_prompt}\n\n---\n\n{self._agent_def.system_prompt}"

    def run(
        self,
        file_path: Path | str,
        title_page_path: Path | str | None = None,
        force_update: bool = False,
    ) -> dict[str, Any]:
        file_path = Path(file_path)
        title_page_path = Path(title_page_path) if title_page_path is not None else None
        workflow_log.info("BookwormWorkflow → %s", file_path.name)

        self._emit("Verificando se é uma capa de livro...")
        check = self._hecate.run(file_path)
        if not check.is_book_cover or not check.is_legible:
            workflow_log.info("Hecate rejected image — %s", check.reason)
            raise NotABookCoverError(check.reason)

        self._emit("Analisando a capa do livro...")
        cover = self._cover_analyzer.run(file_path)

        if not cover.title:
            raise ValueError(f"Could not extract book title from cover: {file_path.name}")

        workflow_log.info(
            f"Cover identified: title={cover.title!r}, author={cover.author!r}, confidence={cover.confidence}"
        )

        title_page: TitlePageAnalysis | None = None
        if title_page_path is not None:
            self._emit("Analisando a folha de rosto...")
            title_page = self._title_page_analyzer.run(title_page_path)
            workflow_log.info(
                f"Title page analyzed: isbn_13={title_page.isbn_13!r}, confidence={title_page.confidence}"
            )

        self._emit("Consultando minhas memórias...")
        memories = self._load_memory.run(title=cover.title, author=cover.author)

        if memories.relevant_keys:
            count = len(memories.relevant_keys)
            workflow_log.info("Memories loaded: %s relevant entr%s", count, "y" if count == 1 else "ies")
            if not force_update:
                raise BookAlreadyRegisteredError(memories.relevant_keys, cover.title, cover.author)
        else:
            workflow_log.info("No relevant memories found")

        self._emit("Buscando informações sobre o livro...")
        metadata = self._book_lookup.run(
            title=cover.title,
            author=cover.author,
            memory_context=memories.context or None,
            title_page_data=asdict(title_page) if title_page is not None else None,
        )

        workflow_log.info("Metadata fetched: confidence=%s", metadata.confidence)

        metadata = self._enrich_compilation_title(metadata, cover.subtitle)

        result: dict[str, Any] = {
            "cover_analysis": asdict(cover),
            "title_page_analysis": asdict(title_page) if title_page is not None else None,
            "bibliographic_metadata": asdict(metadata),
            "report_confidence": merged_confidence(cover.confidence, metadata.confidence),
            "notes": memories.context or None,
        }

        self._emit("Registrando na memória...")
        self._write_memory.run(report=result)

        output_dir = self._write_output(result, cover.title, cover.author, file_path, title_page_path)
        result["output_dir"] = str(output_dir)

        workflow_log.info("Output saved → %s", output_dir)
        return result

    def _write_output(
        self,
        result: dict[str, Any],
        title: str,
        author: str | None,
        cover_path: Path,
        title_page_path: Path | None,
    ) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        author_slug = (author or "unknown").lower().replace(" ", "-")[:30]
        title_slug = title.lower().replace(" ", "-")[:50]
        folder_name = f"{timestamp}-{author_slug}-{title_slug}"
        output_dir = _OUTPUT_DIR / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Copy images locally
        cover_dest = output_dir / f"cover{cover_path.suffix}"
        shutil.copy2(cover_path, cover_dest)

        title_page_dest: Path | None = None
        if title_page_path is not None:
            title_page_dest = output_dir / f"title_page{title_page_path.suffix}"
            shutil.copy2(title_page_path, title_page_dest)

        # Upload images to SeaweedFS
        sfs = SeaweedFSClient(settings.SEAWEEDFS_FILER_URL, settings.SEAWEEDFS_PUBLIC_URL or None)
        cover_upload = sfs.upload(cover_dest, f"books/{folder_name}/cover{cover_path.suffix}")
        result["cover_url"] = cover_upload.url

        if title_page_dest is not None:
            tp_upload = sfs.upload(title_page_dest, f"books/{folder_name}/title_page{title_page_dest.suffix}")
            result["title_page_url"] = tp_upload.url

        json_path = output_dir / "result.json"
        json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

        # Index to Meilisearch
        meili = MeilisearchClient(settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY)
        meili.index_book(build_book_document(folder_name, result))

        return output_dir

    _YEAR_IN_TITLE = re.compile(r"\b(19|20)\d{2}\b")
    _EDITION_IN_TITLE = re.compile(r"\b\d+[aª°]?\s*(ed(i[çc][aã]o)?|edition)\b", re.IGNORECASE)
    _ORDINAL_IN_TITLE = re.compile(r"\b\d+[aª°]\b")
    _COMPILATION_TYPES: ClassVar[frozenset[str]] = frozenset({"antologia", "premiação"})

    def _enrich_compilation_title(self, metadata: BookMetadata, subtitle: str | None) -> BookMetadata:
        if metadata.content_type not in self._COMPILATION_TYPES:
            return metadata

        title = metadata.title
        already_has_marker = (
            self._YEAR_IN_TITLE.search(title)
            or self._EDITION_IN_TITLE.search(title)
            or self._ORDINAL_IN_TITLE.search(title)
        )
        if already_has_marker:
            return metadata

        # Try to extract edition/year from subtitle first, then fall back to publication_year
        marker: str | None = None
        if subtitle:
            year_match = self._YEAR_IN_TITLE.search(subtitle)
            edition_match = self._EDITION_IN_TITLE.search(subtitle) or self._ORDINAL_IN_TITLE.search(subtitle)
            if edition_match:
                marker = edition_match.group(0).strip()
            elif year_match:
                marker = year_match.group(0)

        if not marker and metadata.publication_year:
            marker = str(metadata.publication_year)

        if not marker:
            return metadata

        return dc_replace(metadata, title=f"{title} — {marker}")
