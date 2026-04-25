"""ProfessorDetectorSkill: detecta se uma imagem é um trabalho de Nilton Manoel (O Professor)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.clients.ai import ModelConfig
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("professor_detector")
_MEMORY_DIR = Path(__file__).parent.parent / "memories"
_PROFESSOR_PROFILE_KEY = "professor_profile"


@dataclass
class ProfessorDetectionResult:
    """Result of the Professor authorship detection gate."""

    is_professor_work: bool
    confidence: str
    reason: str
    work_type_hint: str | None


class ProfessorDetectorSkill(Step):
    """Evaluates whether an image is a work by Nilton Manoel (O Professor), using a dynamic profile."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["professor_detector"]

    def validate(self, file_path: Path | str, **kwargs: Any) -> None:
        self._validate_image_file(file_path, label="Cover image")

    def execute(self, file_path: Path | str, **kwargs: Any) -> ProfessorDetectionResult:
        profile = self._load_profile()
        user_text = "Avalie esta imagem e retorne o JSON."
        if profile:
            user_text = f"Perfil acumulado do Professor:\n\n{profile}\n\n---\n\n{user_text}"

        data = self._complete_image_json(
            file_path,
            system_prompt=_DEFINITION.system_prompt,
            user_text=user_text,
        )
        return ProfessorDetectionResult(
            is_professor_work=bool(data.get("is_professor_work", False)),
            confidence=data.get("confidence", "low"),
            reason=data.get("reason", ""),
            work_type_hint=data.get("work_type_hint") or None,
        )

    def _load_profile(self) -> str | None:
        path = _MEMORY_DIR / f"{_PROFESSOR_PROFILE_KEY}.md"
        return path.read_text() if path.exists() else None
