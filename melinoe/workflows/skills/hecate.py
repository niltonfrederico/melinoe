"""HecateSkill: validates that an image contains a legible book cover before processing."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.client import ModelConfig
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("hecate")


@dataclass
class BookCoverCheck:
    """Result of the image validation gate."""

    is_book_cover: bool
    is_legible: bool
    reason: str


class HecateSkill(Step):
    """Rejects images that are not legible book covers before the rest of the workflow runs."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["hecate"]

    def validate(self, file_path: Path | str, **kwargs: Any) -> None:
        self._validate_image_file(file_path, label="Cover image")

    def execute(self, file_path: Path | str, **kwargs: Any) -> BookCoverCheck:
        data = self._complete_image_json(
            file_path,
            system_prompt=_DEFINITION.system_prompt,
            user_text="Avalie esta imagem e retorne o JSON.",
        )
        return BookCoverCheck(
            is_book_cover=bool(data.get("is_book_cover", False)),
            is_legible=bool(data.get("is_legible", False)),
            reason=data.get("reason", ""),
        )
