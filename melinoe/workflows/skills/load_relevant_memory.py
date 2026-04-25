"""LoadRelevantMemorySkill: retrieves contextually relevant prior book memories via LLM filtering."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.client import ModelConfig
from melinoe.client import complete_json
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("load_relevant_memory")
_MEMORY_DIR = Path(__file__).parent.parent / "memories"


@dataclass
class RelevantMemories:
    """LLM-filtered subset of stored memories relevant to the current query."""

    relevant_keys: list[str]
    context: str


class LoadRelevantMemorySkill(Step):
    """Scans all stored Markdown memories and returns those relevant to a given title/author."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["load_relevant_memory"]

    def validate(self, title: str, **kwargs: Any) -> None:
        if not title or not title.strip():
            raise ValueError("Title is required for memory lookup")

    def execute(self, title: str, author: str | None = None, **kwargs: Any) -> RelevantMemories:
        entries = self._read_all_memories()
        if not entries:
            return RelevantMemories(relevant_keys=[], context="")

        payload: dict[str, Any] = {
            "title": title,
            "author": author,
            "memory_entries": entries,
        }
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _DEFINITION.system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        try:
            data = complete_json(self.model_config, messages)
        except (ValueError, Exception):
            return RelevantMemories(relevant_keys=[], context="")

        return RelevantMemories(
            relevant_keys=data.get("relevant_keys") or [],
            context=data.get("context") or "",
        )

    def _read_all_memories(self) -> list[dict[str, str]]:
        if not _MEMORY_DIR.exists():
            return []
        entries = []
        for path in sorted(_MEMORY_DIR.glob("*.md")):
            if path.name == ".gitkeep":
                continue
            entries.append({"key": path.stem, "content": path.read_text()})
        return entries
