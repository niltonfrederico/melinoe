import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.client import ModelConfig
from melinoe.client import complete
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("load_relevant_memory")
_MEMORY_DIR = Path(__file__).parent.parent / "memories"


@dataclass
class RelevantMemories:
    relevant_keys: list[str]
    context: str


class LoadRelevantMemorySkill(Step):
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

        response = complete(self.model_config, messages, temperature=0.0, response_format={"type": "json_object"})
        content = response.choices[0].message.content or ""

        try:
            data: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError:
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
