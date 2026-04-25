"""ProfessorClassifierSkill: classifica o gênero e tipo literário de um trabalho de Nilton Manoel."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.clients.ai import ModelConfig
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("professor_classifier")


@dataclass
class ProfessorWorkClassification:
    """Structured literary classification of a work by Nilton Manoel."""

    work_type: str
    literary_form: str | None
    is_collection: bool
    collection_title: str | None
    estimated_work_count: int | None
    competition_name: str | None
    confidence: str
    classification_notes: str | None


class ProfessorClassifierSkill(Step):
    """Classifies the literary genre and type of a work by Nilton Manoel from a cover image."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["professor_classifier"]

    def validate(self, file_path: Path | str, **kwargs: Any) -> None:
        self._validate_image_file(file_path, label="Cover image")

    def execute(self, file_path: Path | str, **kwargs: Any) -> ProfessorWorkClassification:
        data = self._complete_image_json(
            file_path,
            system_prompt=_DEFINITION.system_prompt,
            user_text="Classifique o tipo e gênero literário deste trabalho e retorne o JSON.",
        )
        return ProfessorWorkClassification(
            work_type=data.get("work_type", "outro"),
            literary_form=data.get("literary_form") or None,
            is_collection=bool(data.get("is_collection", False)),
            collection_title=data.get("collection_title") or None,
            estimated_work_count=data.get("estimated_work_count") or None,
            competition_name=data.get("competition_name") or None,
            confidence=data.get("confidence", "low"),
            classification_notes=data.get("classification_notes") or None,
        )
