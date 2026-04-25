"""ExecuteWebMentionsSkill: visita URLs, extrai conteúdo e analisa menções a Nilton Manoel."""

import json
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any
from typing import ClassVar

import httpx

from melinoe.clients.ai import GEMINI_PRO
from melinoe.clients.ai import ModelConfig
from melinoe.clients.ai import complete_json_with_fallback
from melinoe.workflows.base import Step
from melinoe.workflows.skills.load_scraping_state import ScrapingState
from melinoe.workflows.skills.loader import load_skill
from melinoe.workflows.skills.plan_scraping import ScrapingPlan

_DEFINITION = load_skill("execute_web_mentions")

_HEADERS = {"User-Agent": "melinoe-senhor-das-horas-mortas/0.1 (niltonfrederico@pm.me; catalogacao-literaria)"}
_TIMEOUT = 15.0
_MAX_CONTENT_CHARS = 8000  # cap page content to avoid exceeding context limits
_DDG_URL = "https://html.duckduckgo.com/html/"
_DDG_MAX_RESULTS = 10


@dataclass
class WebMention:
    """A confirmed or likely mention of Nilton Manoel found on a web page."""

    url: str
    snippet: str
    confidence: str
    source_type: str
    discovered_aliases: list[str]
    discovered_venues: list[str]
    discovered_years: list[int]
    context_notes: str | None
    article_text: str | None = None


@dataclass
class WebMentionsResult:
    """Aggregated result of scraping a batch of URLs."""

    mentions: list[WebMention]
    newly_discovered_urls: list[str]
    urls_visited: list[str]
    urls_failed: list[str]


class ExecuteWebMentionsSkill(Step):
    """Fetches web pages and uses LLM to identify mentions of Nilton Manoel."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["execute_web_mentions"]

    def validate(self, plan: ScrapingPlan, state: ScrapingState, **kwargs: Any) -> None:
        if plan is None:
            raise ValueError("ScrapingPlan is required")

    def execute(self, plan: ScrapingPlan, state: ScrapingState, **kwargs: Any) -> WebMentionsResult:
        all_mentions: list[WebMention] = []
        all_discovered: list[str] = []
        visited: list[str] = []
        failed: list[str] = []
        visited_set = set(state.visited_urls)

        with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            for url in plan.next_urls:
                if url in visited_set:
                    continue
                mentions, discovered, ok = self._process_url(client, url)
                if ok:
                    visited.append(url)
                    all_mentions.extend(mentions)
                    all_discovered.extend(discovered)
                else:
                    failed.append(url)

            for query in plan.search_queries:
                search_urls = self._search_duckduckgo(client, query)
                all_discovered.extend(u for u in search_urls if u not in visited_set)

        return WebMentionsResult(
            mentions=all_mentions,
            newly_discovered_urls=list(dict.fromkeys(all_discovered)),  # deduplicate, preserve order
            urls_visited=visited,
            urls_failed=failed,
        )

    def _process_url(self, client: httpx.Client, url: str) -> tuple[list[WebMention], list[str], bool]:
        try:
            response = client.get(url)
            response.raise_for_status()
            content = self._extract_text(response.text)
        except Exception:
            return [], [], False

        mentions, discovered = self._analyze_content(url, content)
        for mention in mentions:
            if mention.source_type == "news":
                mention.article_text = content
        return mentions, discovered, True

    def _search_duckduckgo(self, client: httpx.Client, query: str) -> list[str]:
        """Query DuckDuckGo HTML endpoint and return result URLs."""
        try:
            response = client.post(_DDG_URL, data={"q": query}, timeout=_TIMEOUT)
            response.raise_for_status()
        except Exception:
            return []

        raw_urls = re.findall(r'href="(/l/\?[^"]+|https?://[^"]+)"', response.text)
        results: list[str] = []
        for raw in raw_urls:
            if raw.startswith("http"):
                results.append(raw)
            elif raw.startswith("/l/?"):
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query)
                if "uddg" in parsed:
                    results.append(urllib.parse.unquote(parsed["uddg"][0]))
            if len(results) >= _DDG_MAX_RESULTS:
                break
        return results

    def _extract_text(self, html: str) -> str:
        """Naive HTML tag stripper — removes tags and collapses whitespace."""
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:_MAX_CONTENT_CHARS]

    def _analyze_content(self, url: str, content: str) -> tuple[list[WebMention], list[str]]:
        # Quick pre-filter: if none of the known names appear, skip LLM call
        keywords = ("nilton manoel", "kardo navalha", "senhor das horas mortas")
        if not any(kw in content.lower() for kw in keywords):
            return [], []

        payload = {"url": url, "content": content}
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _DEFINITION.system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            data = complete_json_with_fallback(self.model_config, GEMINI_PRO, messages)
        except Exception:
            return [], []

        mentions: list[WebMention] = []
        for m in data.get("mentions") or []:
            mentions.append(
                WebMention(
                    url=url,
                    snippet=m.get("snippet", ""),
                    confidence=m.get("confidence", "low"),
                    source_type=m.get("source_type", "other"),
                    discovered_aliases=m.get("discovered_aliases") or [],
                    discovered_venues=m.get("discovered_venues") or [],
                    discovered_years=m.get("discovered_years") or [],
                    context_notes=m.get("context_notes") or None,
                )
            )

        discovered: list[str] = data.get("discovered_urls") or []
        return mentions, discovered
