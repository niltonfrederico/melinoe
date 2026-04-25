"""WriteMemorySkill: persists a completed book report as a Markdown memory entry."""

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

_DEFINITION = load_skill("write_memory")


@dataclass
class WrittenMemory:
    """Reference to a memory entry saved to disk."""

    memory_key: str
    memory_path: Path


class WriteMemorySkill(Step):
    """Generates a structured Markdown memory file from a book analysis report."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["write_memory"]

    def validate(self, report: dict[str, Any], **kwargs: Any) -> None:
        if not isinstance(report, dict):
            raise ValueError("report must be a dict")
        if "cover_analysis" not in report or "bibliographic_metadata" not in report:
            raise ValueError("report must contain cover_analysis and bibliographic_metadata")

    def execute(self, report: dict[str, Any], **kwargs: Any) -> WrittenMemory:
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

        return WrittenMemory(memory_key=memory_key, memory_path=memory_path)

    def _fallback_key(self, report: dict[str, Any]) -> str:
        cover = report.get("cover_analysis") or {}
        title = (cover.get("title") or "unknown").lower().replace(" ", "_")[:40]
        author = (cover.get("author") or "").lower().replace(" ", "_")[:20]
        return f"{author}_{title}".strip("_") if author else title
