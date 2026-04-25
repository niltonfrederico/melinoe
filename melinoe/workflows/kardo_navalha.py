"""KardoNavalhaWorkflow: cataloga trabalhos de Nilton Manoel (O Professor)."""

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import melinoe.settings as settings
from melinoe.clients.meilisearch import NiltonWorksMeilisearchClient
from melinoe.clients.meilisearch import build_professor_document
from melinoe.clients.seaweedfs import SeaweedFSClient
from melinoe.logger import workflow_log
from melinoe.workflows.base import Step
from melinoe.workflows.base import Workflow
from melinoe.workflows.skills.load_relevant_memory import LoadRelevantMemorySkill
from melinoe.workflows.skills.loader import load_agent
from melinoe.workflows.skills.loader import load_soul
from melinoe.workflows.skills.professor_cataloger import ProfessorCatalogerSkill
from melinoe.workflows.skills.professor_classifier import ProfessorClassifierSkill
from melinoe.workflows.skills.professor_detector import ProfessorDetectionResult
from melinoe.workflows.skills.professor_detector import ProfessorDetectorSkill
from melinoe.workflows.skills.write_professor_memory import WriteProfessorMemorySkill

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "professor"


class ProfessorWorkAlreadyRegisteredError(Exception):
    """Raised when a matching memory already exists and force_update is False."""

    def __init__(self, memory_keys: list[str], title: str | None) -> None:
        self.memory_keys = memory_keys
        self.title = title
        super().__init__(f"Professor work already registered: {title!r}")


class KardoNavalhaWorkflow(Workflow):
    agent = "kardo_navalha"

    def __init__(self) -> None:
        self._agent_def = load_agent("kardo_navalha")
        self._soul_def = load_soul("kardo_navalha")
        self._detector = ProfessorDetectorSkill()
        self._load_memory = LoadRelevantMemorySkill()
        self._classifier = ProfessorClassifierSkill()
        self._cataloger = ProfessorCatalogerSkill()
        self._write_memory = WriteProfessorMemorySkill()
        self.steps: list[Step] = [
            self._detector,
            self._load_memory,
            self._classifier,
            self._cataloger,
            self._write_memory,
        ]
        super().__init__()

    @property
    def system_prompt(self) -> str:
        return f"{self._soul_def.system_prompt}\n\n---\n\n{self._agent_def.system_prompt}"

    def run(
        self,
        file_path: Path | str,
        detection: ProfessorDetectionResult | None = None,
        force_update: bool = False,
    ) -> dict[str, Any]:
        file_path = Path(file_path)
        workflow_log.info("KardoNavalhaWorkflow → %s", file_path.name)

        self._emit("Verificando autoria do Professor...")
        if detection is None:
            detection = self._detector.run(file_path)

        if not detection.is_professor_work:
            raise ValueError(f"Image is not a Professor work: {detection.reason}")

        workflow_log.info(
            "Professor work confirmed — confidence=%s, hint=%s",
            detection.confidence,
            detection.work_type_hint,
        )

        self._emit("Consultando memórias anteriores...")
        title_hint = detection.work_type_hint or "trabalho do Professor"
        memories = self._load_memory.run(title=title_hint, author="Nilton Manoel")

        if memories.relevant_keys and not force_update:
            raise ProfessorWorkAlreadyRegisteredError(memories.relevant_keys, title_hint)

        self._emit("Classificando o tipo de obra...")
        classification = self._classifier.run(file_path)
        workflow_log.info(
            "Work classified: type=%r, confidence=%s", classification.work_type, classification.confidence
        )

        self._emit("Catalogando o trabalho...")
        from melinoe.workflows.skills.cover_analyzer import CoverAnalyzerSkill

        cover_analyzer = CoverAnalyzerSkill()
        cover = cover_analyzer.run(file_path)

        catalog = self._cataloger.run(
            cover_analysis=asdict(cover),
            classification=asdict(classification),
            detection=asdict(detection),
            memory_context=memories.context or None,
        )
        workflow_log.info("Catalog produced: title=%r, confidence=%s", catalog.title, catalog.confidence)

        result: dict[str, Any] = {
            "detection": asdict(detection),
            "classification": asdict(classification),
            "cover_analysis": asdict(cover),
            "catalog": asdict(catalog),
            "report_confidence": self._merged_confidence(detection.confidence, catalog.confidence),
        }

        self._emit("Salvando na memória...")
        self._write_memory.run(report=result)

        output_dir = self._write_output(result, catalog.title, catalog.work_type, file_path)
        result["output_dir"] = str(output_dir)

        self._emit("Enfileirando pesquisa do Senhor das Horas Mortas...")
        self._enqueue_scraping(result)

        workflow_log.info("Output saved → %s", output_dir)
        return result

    def _write_output(
        self,
        result: dict[str, Any],
        title: str | None,
        work_type: str,
        cover_path: Path,
    ) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        title_slug = (title or "sem-titulo").lower().replace(" ", "-")[:50]
        work_type_slug = work_type.lower().replace(" ", "-")[:20]
        folder_name = f"{timestamp}-professor-{work_type_slug}-{title_slug}"
        output_dir = _OUTPUT_DIR / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)

        cover_dest = output_dir / f"cover{cover_path.suffix}"
        shutil.copy2(cover_path, cover_dest)

        sfs = SeaweedFSClient(settings.SEAWEEDFS_FILER_URL, settings.SEAWEEDFS_PUBLIC_URL or None)
        cover_upload = sfs.upload(cover_dest, f"professor/{folder_name}/cover{cover_path.suffix}")
        result["cover_url"] = cover_upload.url

        json_path = output_dir / "result.json"
        json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

        meili = NiltonWorksMeilisearchClient(settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY)
        meili.index_work(build_professor_document(folder_name, result))

        return output_dir

    def _enqueue_scraping(self, result: dict[str, Any]) -> None:
        """Fire-and-forget: enqueue a scraping task triggered by this new cataloged work."""
        try:
            import asyncio

            from melinoe.worker import enqueue_scrape_task

            asyncio.get_event_loop().run_until_complete(enqueue_scrape_task())
        except Exception as exc:
            workflow_log.warning("Failed to enqueue scraping task — %s", exc)

    @staticmethod
    def _merged_confidence(a: str, b: str) -> str:
        order = {"high": 2, "medium": 1, "low": 0}
        return (
            "high"
            if min(order.get(a, 0), order.get(b, 0)) == 2
            else ("medium" if min(order.get(a, 0), order.get(b, 0)) == 1 else "low")
        )
