"""EnrichProfessorProfileSkill: atualiza o perfil de Nilton Manoel com dados descobertos pelo scraper."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.clients.ai import GEMINI_FLASH
from melinoe.clients.ai import ModelConfig
from melinoe.clients.ai import complete_json_with_fallback
from melinoe.workflows.base import Step
from melinoe.workflows.skills.execute_web_mentions import WebMentionsResult
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("enrich_professor_profile")
_MEMORY_DIR = Path(__file__).parent.parent / "memories"
_PROFESSOR_PROFILE_KEY = "professor_profile"


@dataclass
class ProfileEnrichmentResult:
    """Result of attempting to enrich the Professor's profile."""

    profile_updated: bool
    new_discoveries: list[str]


class EnrichProfessorProfileSkill(Step):
    """Extracts identity markers from web mentions and updates the Professor's persistent profile."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["enrich_professor_profile"]

    def validate(self, mentions_result: WebMentionsResult, **kwargs: Any) -> None:
        if mentions_result is None:
            raise ValueError("WebMentionsResult is required")

    def execute(self, mentions_result: WebMentionsResult, **kwargs: Any) -> ProfileEnrichmentResult:
        if not mentions_result.mentions:
            return ProfileEnrichmentResult(profile_updated=False, new_discoveries=[])

        existing_profile = self._load_profile()
        mentions_data = [
            {
                "url": m.url,
                "snippet": m.snippet,
                "confidence": m.confidence,
                "source_type": m.source_type,
                "discovered_aliases": m.discovered_aliases,
                "discovered_venues": m.discovered_venues,
                "discovered_years": m.discovered_years,
            }
            for m in mentions_result.mentions
        ]

        payload: dict[str, Any] = {
            "existing_profile": existing_profile or "",
            "new_mentions": mentions_data,
        }
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _DEFINITION.system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        try:
            data = complete_json_with_fallback(self.model_config, GEMINI_FLASH, messages)
        except Exception:
            return ProfileEnrichmentResult(profile_updated=False, new_discoveries=[])

        if data.get("profile_updated") and data.get("updated_profile"):
            _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            (_MEMORY_DIR / f"{_PROFESSOR_PROFILE_KEY}.md").write_text(data["updated_profile"])

        return ProfileEnrichmentResult(
            profile_updated=bool(data.get("profile_updated", False)),
            new_discoveries=data.get("new_discoveries") or [],
        )

    def _load_profile(self) -> str | None:
        path = _MEMORY_DIR / f"{_PROFESSOR_PROFILE_KEY}.md"
        return path.read_text() if path.exists() else None
