"""CoverAnalyzerSkill: extracts visual and contextual metadata from a book cover image."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.clients.ai import ModelConfig
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("cover_analyzer")


@dataclass
class CoverAnalysis:
    """Structured visual analysis of a book cover."""

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
    """Analyzes book cover images to extract title, author, genre, design, and visual metadata."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["cover_analyzer"]

    def validate(self, file_path: Path | str, **kwargs: Any) -> None:
        self._validate_image_file(file_path, label="Cover image")

    def execute(self, file_path: Path | str, **kwargs: Any) -> CoverAnalysis:
        data = self._complete_image_json(
            file_path,
            system_prompt=_DEFINITION.system_prompt,
            user_text="Analyze this book cover and return the structured JSON.",
        )
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
