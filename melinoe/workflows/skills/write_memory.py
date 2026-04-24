import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.client import ModelConfig
from melinoe.client import complete
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("write_memory")
_MEMORY_DIR = Path(__file__).parent.parent / "memories"


@dataclass
class WrittenMemory:
    memory_key: str
    memory_path: Path


class WriteMemorySkill(Step):
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

        response = complete(self.model_config, messages, temperature=0.0, response_format={"type": "json_object"})
        content = response.choices[0].message.content or ""

        try:
            data: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError:
            data = {}

        memory_key: str = data.get("memory_key") or self._fallback_key(report)
        memory_content: str = data.get("memory_content") or json.dumps(report, indent=2, ensure_ascii=False)

        _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        memory_path = _MEMORY_DIR / f"{memory_key}.md"
        memory_path.write_text(memory_content)

        return WrittenMemory(memory_key=memory_key, memory_path=memory_path)

    def _fallback_key(self, report: dict[str, Any]) -> str:
        cover = report.get("cover_analysis") or {}
        title = (cover.get("title") or "unknown").lower().replace(" ", "_")[:40]
        author = (cover.get("author") or "").lower().replace(" ", "_")[:20]
        return f"{author}_{title}".strip("_") if author else title
