"""PlanScrapingSkill: planeja o próximo lote de URLs e queries para o Senhor das Horas Mortas."""

import json
from dataclasses import dataclass
from typing import Any
from typing import ClassVar

from melinoe.clients.ai import GEMINI_FLASH
from melinoe.clients.ai import ModelConfig
from melinoe.clients.ai import complete_json_with_fallback
from melinoe.workflows.base import Step
from melinoe.workflows.skills.load_scraping_state import ScrapingState
from melinoe.workflows.skills.loader import load_skill
from melinoe.workflows.skills.professor_detector import load_professor_profile

_DEFINITION = load_skill("plan_scraping")
_DEFAULT_BATCH_SIZE = 10


@dataclass
class ScrapingPlan:
    """Next batch of URLs and search queries for the scraper to execute."""

    next_urls: list[str]
    search_queries: list[str]
    planning_notes: str | None


class PlanScrapingSkill(Step):
    """Produces the next scraping batch based on current state and the Professor's profile."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["plan_scraping"]

    def validate(self, state: ScrapingState, **kwargs: Any) -> None:
        if state is None:
            raise ValueError("ScrapingState is required for planning")

    def execute(
        self,
        state: ScrapingState,
        trigger: str = "cron",
        batch_size: int = _DEFAULT_BATCH_SIZE,
        **kwargs: Any,
    ) -> ScrapingPlan:
        profile = load_professor_profile()
        payload: dict[str, Any] = {
            "state": {
                "visited_urls_count": len(state.visited_urls),
                "pending_urls": state.pending_urls[:50],  # cap to avoid huge payloads
                "found_mentions_count": len(state.found_mentions),
                "stats": state.stats,
                "session_count": state.session_count,
            },
            "trigger": trigger,
            "batch_size": batch_size,
        }
        if profile:
            payload["professor_profile"] = profile

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _DEFINITION.system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        data = complete_json_with_fallback(self.model_config, GEMINI_FLASH, messages)

        # Never revisit already-visited URLs
        visited = set(state.visited_urls)
        next_urls = [u for u in (data.get("next_urls") or []) if u not in visited]
        # Also drain pending queue up to batch_size
        pending_to_add = [u for u in state.pending_urls if u not in visited and u not in next_urls]
        combined = (next_urls + pending_to_add)[:batch_size]

        return ScrapingPlan(
            next_urls=combined,
            search_queries=data.get("search_queries") or [],
            planning_notes=data.get("planning_notes") or None,
        )
