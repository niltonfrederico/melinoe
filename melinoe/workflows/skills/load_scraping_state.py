"""LoadScrapingStateSkill: carrega o estado persistido do Senhor das Horas Mortas."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.clients.ai import GEMINI_FLASH
from melinoe.clients.ai import ModelConfig
from melinoe.workflows.base import Step

_MEMORY_DIR = Path(__file__).parent.parent / "memories"
_STATE_KEY = "professor_scraping_state"

_SEED_URLS: list[str] = [
    "https://falandodetrova.com.br/niltonmanoel",
    "https://www.movimentodasartes.com.br/",
]


@dataclass
class ScrapingState:
    """Persistent state for the Senhor das Horas Mortas autonomous scraper."""

    visited_urls: list[str]
    pending_urls: list[str]
    found_mentions: list[dict[str, Any]]
    stats: dict[str, Any]
    session_count: int


class LoadScrapingStateSkill(Step):
    """Loads the persisted scraping state from disk; initializes with seed URLs on first run."""

    model_config: ModelConfig = GEMINI_FLASH
    skills: ClassVar[list[str]] = ["load_scraping_state"]

    def validate(self, **kwargs: Any) -> None:
        pass

    def execute(self, **kwargs: Any) -> ScrapingState:
        path = _MEMORY_DIR / f"{_STATE_KEY}.json"
        if path.exists():
            raw = json.loads(path.read_text())
            return ScrapingState(
                visited_urls=raw.get("visited_urls", []),
                pending_urls=raw.get("pending_urls", []),
                found_mentions=raw.get("found_mentions", []),
                stats=raw.get("stats", {}),
                session_count=raw.get("session_count", 0),
            )
        return ScrapingState(
            visited_urls=[],
            pending_urls=list(_SEED_URLS),
            found_mentions=[],
            stats={"total_mentions": 0, "total_urls_visited": 0, "total_sessions": 0},
            session_count=0,
        )
