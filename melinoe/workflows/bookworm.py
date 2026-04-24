import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from melinoe.logger import workflow_log
from melinoe.workflows.base import Step
from melinoe.workflows.base import Workflow
from melinoe.workflows.skills.book_lookup import BookLookupSkill
from melinoe.workflows.skills.cover_analyzer import CoverAnalyzerSkill
from melinoe.workflows.skills.load_relevant_memory import LoadRelevantMemorySkill
from melinoe.workflows.skills.loader import load_agent
from melinoe.workflows.skills.loader import load_soul
from melinoe.workflows.skills.write_memory import WriteMemorySkill

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


class BookwormWorkflow(Workflow):
    agent = "bookworm"

    def __init__(self) -> None:
        self._agent_def = load_agent("bookworm")
        self._soul_def = load_soul("bibliophile")
        self._load_memory = LoadRelevantMemorySkill()
        self._cover_analyzer = CoverAnalyzerSkill()
        self._book_lookup = BookLookupSkill()
        self._write_memory = WriteMemorySkill()
        self.steps: list[Step] = [
            self._load_memory,
            self._cover_analyzer,
            self._book_lookup,
            self._write_memory,
        ]
        super().__init__()

    @property
    def system_prompt(self) -> str:
        return f"{self._soul_def.system_prompt}\n\n---\n\n{self._agent_def.system_prompt}"

    def run(self, file_path: Path | str) -> dict[str, Any]:
        file_path = Path(file_path)
        workflow_log.info(f"BookwormWorkflow → {file_path.name}")

        cover = self._cover_analyzer.run(file_path)

        if not cover.title:
            raise ValueError(f"Could not extract book title from cover: {file_path.name}")

        workflow_log.info(
            f"Cover identified: title={cover.title!r}, author={cover.author!r}, confidence={cover.confidence}"
        )

        memories = self._load_memory.run(title=cover.title, author=cover.author)

        if memories.relevant_keys:
            count = len(memories.relevant_keys)
            workflow_log.info(f"Memories loaded: {count} relevant entr{'y' if count == 1 else 'ies'}")
        else:
            workflow_log.info("No relevant memories found")

        metadata = self._book_lookup.run(
            title=cover.title,
            author=cover.author,
            memory_context=memories.context or None,
        )

        workflow_log.info(f"Metadata fetched: confidence={metadata.confidence}")

        result: dict[str, Any] = {
            "cover_analysis": asdict(cover),
            "bibliographic_metadata": asdict(metadata),
            "report_confidence": self._merged_confidence(cover.confidence, metadata.confidence),
            "notes": memories.context or None,
        }

        self._write_memory.run(report=result)

        output_path = self._write_output(result, cover.title, cover.author)
        result["output_file"] = str(output_path)

        workflow_log.info(f"Output saved → {output_path}")
        return result

    def _write_output(self, result: dict[str, Any], title: str, author: str | None) -> Path:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        author_slug = (author or "unknown").lower().replace(" ", "-")[:30]
        title_slug = title.lower().replace(" ", "-")[:50]
        filename = f"{timestamp}-{author_slug}-{title_slug}.json"
        output_path = _OUTPUT_DIR / filename
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        return output_path

    def _merged_confidence(self, cover_conf: str, meta_conf: str) -> str:
        order = {"high": 2, "medium": 1, "low": 0}
        level = min(order.get(cover_conf, 0), order.get(meta_conf, 0))
        return ["low", "medium", "high"][level]
