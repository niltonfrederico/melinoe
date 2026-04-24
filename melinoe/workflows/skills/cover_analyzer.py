import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.client import ModelConfig
from melinoe.client import complete
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("cover_analyzer")

_MIME_MAP: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


@dataclass
class CoverAnalysis:
    title: str | None
    subtitle: str | None
    author: str | None
    publisher: str | None
    series: str | None
    genre: str | None
    design_style: str | None
    mood: str | None
    target_audience: str | None
    visual_elements: list[str]
    confidence: str
    color_palette: dict[str, Any]
    typography: dict[str, Any]


class CoverAnalyzerSkill(Step):
    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["cover_analyzer"]

    def validate(self, file_path: Path | str, **kwargs: Any) -> None:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Cover image not found: {path}")
        if path.suffix.lower() not in _MIME_MAP:
            raise ValueError(f"Unsupported image format: {path.suffix}")

    def execute(self, file_path: Path | str, **kwargs: Any) -> CoverAnalysis:
        path = Path(file_path)
        image_b64 = base64.b64encode(self.load_file_bytes(path)).decode()
        mime_type = _MIME_MAP[path.suffix.lower()]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _DEFINITION.system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this book cover and return the structured JSON."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                ],
            },
        ]

        response = complete(self.model_config, messages, temperature=0.0, response_format={"type": "json_object"})
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from cover analysis model")

        data: dict[str, Any] = json.loads(content)
        return CoverAnalysis(
            title=data.get("title"),
            subtitle=data.get("subtitle"),
            author=data.get("author"),
            publisher=data.get("publisher"),
            series=data.get("series"),
            genre=data.get("genre"),
            design_style=data.get("design_style"),
            mood=data.get("mood"),
            target_audience=data.get("target_audience"),
            visual_elements=data.get("visual_elements") or [],
            confidence=data.get("confidence", "low"),
            color_palette=data.get("color_palette") or {},
            typography=data.get("typography") or {},
        )
