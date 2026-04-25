"""WriteProfessorMemorySkill: persiste o registro catalográfico de um trabalho de Nilton Manoel."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.clients.ai import GEMINI_FLASH
from melinoe.clients.ai import ModelConfig
from melinoe.clients.ai import complete_json_with_fallback
from melinoe.workflows.base import MEMORY_DIR
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("write_professor_memory")


@dataclass
class WrittenProfessorMemory:
    """Reference to a catalog memory entry saved to disk."""

    memory_key: str
    memory_path: Path


class WriteProfessorMemorySkill(Step):
    """Generates a structured Markdown memory file from a Professor work catalog report."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["write_professor_memory"]

    def validate(self, report: dict[str, Any], **kwargs: Any) -> None:
        if not isinstance(report, dict):
            raise ValueError("report must be a dict")
        if "catalog" not in report:
            raise ValueError("report must contain a catalog field")

    def execute(self, report: dict[str, Any], **kwargs: Any) -> WrittenProfessorMemory:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _DEFINITION.system_prompt},
            {"role": "user", "content": json.dumps(report, ensure_ascii=False)},
        ]

        try:
            data = complete_json_with_fallback(self.model_config, GEMINI_FLASH, messages)
        except Exception:
            data = {}

        memory_key: str = data.get("memory_key") or self._fallback_key(report)
        memory_content: str = data.get("memory_content") or json.dumps(report, indent=2, ensure_ascii=False)

        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        memory_path = MEMORY_DIR / f"{memory_key}.md"
        memory_path.write_text(memory_content)

        return WrittenProfessorMemory(memory_key=memory_key, memory_path=memory_path)

    def _fallback_key(self, report: dict[str, Any]) -> str:
        catalog: dict[str, Any] = report.get("catalog") or {}
        work_type = (catalog.get("work_type") or "obra").lower().replace(" ", "_")
        title = (catalog.get("title") or "sem_titulo").lower().replace(" ", "_")[:30]
        return f"professor_{work_type}_{title}"
