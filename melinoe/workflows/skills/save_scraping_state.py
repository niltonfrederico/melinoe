"""SaveScrapingStateSkill: persiste o estado atualizado do Senhor das Horas Mortas."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.clients.ai import GEMINI_FLASH
from melinoe.clients.ai import ModelConfig
from melinoe.workflows.base import Step
from melinoe.workflows.skills.execute_web_mentions import WebMentionsResult
from melinoe.workflows.skills.load_scraping_state import ScrapingState

_MEMORY_DIR = Path(__file__).parent.parent / "memories"
_STATE_KEY = "professor_scraping_state"


@dataclass
class SavedScrapingState:
    """Confirmation that the scraping state was persisted."""

    state_key: str
    total_visited: int
    total_pending: int
    total_mentions: int


class SaveScrapingStateSkill(Step):
    """Merges scraping results into the current state and persists it to disk."""

    model_config: ModelConfig = GEMINI_FLASH
    skills: ClassVar[list[str]] = ["save_scraping_state"]

    def validate(self, state: ScrapingState, mentions_result: WebMentionsResult, **kwargs: Any) -> None:
        if state is None:
            raise ValueError("ScrapingState is required")
        if mentions_result is None:
            raise ValueError("WebMentionsResult is required")

    def execute(
        self,
        state: ScrapingState,
        mentions_result: WebMentionsResult,
        newly_discovered_urls: list[str] | None = None,
        **kwargs: Any,
    ) -> SavedScrapingState:
        visited_set = set(state.visited_urls)
        for url in mentions_result.urls_visited:
            visited_set.add(url)

        pending_set = set(state.pending_urls) - visited_set
        for url in mentions_result.newly_discovered_urls:
            if url not in visited_set:
                pending_set.add(url)

        new_mentions = [
            {
                "url": m.url,
                "snippet": m.snippet,
                "confidence": m.confidence,
                "source_type": m.source_type,
                "discovered_aliases": m.discovered_aliases,
                "discovered_venues": m.discovered_venues,
                "discovered_years": m.discovered_years,
                "context_notes": m.context_notes,
            }
            for m in mentions_result.mentions
        ]

        updated_stats: dict[str, Any] = dict(state.stats)
        updated_stats["total_mentions"] = updated_stats.get("total_mentions", 0) + len(new_mentions)
        updated_stats["total_urls_visited"] = len(visited_set)
        updated_stats["total_sessions"] = state.session_count + 1

        updated_state: dict[str, Any] = {
            "visited_urls": sorted(visited_set),
            "pending_urls": sorted(pending_set),
            "found_mentions": state.found_mentions + new_mentions,
            "stats": updated_stats,
            "session_count": state.session_count + 1,
        }

        _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        path = _MEMORY_DIR / f"{_STATE_KEY}.json"
        path.write_text(json.dumps(updated_state, indent=2, ensure_ascii=False))

        return SavedScrapingState(
            state_key=_STATE_KEY,
            total_visited=len(visited_set),
            total_pending=len(pending_set),
            total_mentions=len(updated_state["found_mentions"]),
        )
