"""ProfessorCatalogerSkill: sintetiza o registro catalográfico completo de um trabalho de Nilton Manoel."""

import json
from dataclasses import dataclass
from typing import Any
from typing import ClassVar

from melinoe.clients.ai import ModelConfig
from melinoe.clients.ai import complete_json
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("professor_cataloger")


@dataclass
class ProfessorWorkMetadata:
    """Consolidated catalog record for a work by Nilton Manoel."""

    title: str | None
    author: str
    pseudonym: str | None
    work_type: str
    literary_form: str | None
    year_estimate: int | None
    year_is_estimate: bool
    publication_context: str | None
    location: str | None
    competition_info: str | None
    coauthors: list[str]
    tags: list[str]
    notes: str | None
    confidence: str


class ProfessorCatalogerSkill(Step):
    """Synthesizes a full catalog record for a work by Nilton Manoel using LLM reasoning."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["professor_cataloger"]

    def validate(self, cover_analysis: dict[str, Any], classification: dict[str, Any], **kwargs: Any) -> None:
        if not cover_analysis:
            raise ValueError("cover_analysis is required for cataloging")
        if not classification:
            raise ValueError("classification is required for cataloging")

    def execute(
        self,
        cover_analysis: dict[str, Any],
        classification: dict[str, Any],
        detection: dict[str, Any] | None = None,
        memory_context: str | None = None,
        **kwargs: Any,
    ) -> ProfessorWorkMetadata:
        payload: dict[str, Any] = {
            "cover_analysis": cover_analysis,
            "classification": classification,
        }
        if detection:
            payload["detection"] = detection
        if memory_context:
            payload["memory_context"] = memory_context

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _DEFINITION.system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        data = complete_json(self.model_config, messages)

        return ProfessorWorkMetadata(
            title=data.get("title") or None,
            author=data.get("author", "Nilton Manoel"),
            pseudonym=data.get("pseudonym") or None,
            work_type=data.get("work_type", "outro"),
            literary_form=data.get("literary_form") or None,
            year_estimate=data.get("year_estimate") or None,
            year_is_estimate=bool(data.get("year_is_estimate", True)),
            publication_context=data.get("publication_context") or None,
            location=data.get("location") or None,
            competition_info=data.get("competition_info") or None,
            coauthors=data.get("coauthors") or [],
            tags=data.get("tags") or [],
            notes=data.get("notes") or None,
            confidence=data.get("confidence", "low"),
        )
