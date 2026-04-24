import json
import urllib.parse
from dataclasses import dataclass
from typing import Any
from typing import ClassVar

import httpx

from melinoe.client import ModelConfig
from melinoe.client import complete
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("book_lookup")

_HEADERS = {"User-Agent": "melinoe-bookworm/0.1 (niltonfrederico@pm.me)"}
_TIMEOUT = 10.0


@dataclass
class BookMetadata:
    title: str
    author: str | None
    isbn_13: str | None
    isbn_10: str | None
    publication_year: int | None
    publisher: str | None
    page_count: int | None
    language: str | None
    synopsis: str | None
    genres: list[str]
    ratings: dict[str, Any]
    awards: list[str]
    source: str
    confidence: str


class BookLookupSkill(Step):
    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["book_lookup"]

    def validate(self, title: str, **kwargs: Any) -> None:
        if not title or not title.strip():
            raise ValueError("Book title is required for lookup")

    def execute(
        self, title: str, author: str | None = None, memory_context: str | None = None, **kwargs: Any
    ) -> BookMetadata:
        sources: dict[str, Any] = {}

        sources["open_library"] = self._fetch_open_library(title, author)
        sources["google_books"] = self._fetch_google_books(title, author)
        sources["estante_virtual"] = self._fetch_estante_virtual(title, author)
        sources["skoob"] = self._fetch_skoob(title, author)

        return self._synthesize(title, author, sources, memory_context=memory_context)

    # --- fetchers ---

    def _get(self, url: str) -> dict[str, Any] | str | None:
        try:
            with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    return resp.json()
                return resp.text
        except Exception:
            return None

    def _fetch_open_library(self, title: str, author: str | None) -> dict[str, Any]:
        params: dict[str, str] = {
            "title": title,
            "limit": "3",
            "fields": (
                "title,author_name,isbn,first_publish_year,publisher,"
                "number_of_pages_median,language,subject,first_sentence"
            ),
        }
        if author:
            params["author"] = author
        url = f"https://openlibrary.org/search.json?{urllib.parse.urlencode(params)}"
        data = self._get(url)
        if not isinstance(data, dict):
            return {}
        docs = data.get("docs") or []
        return docs[0] if docs else {}

    def _fetch_google_books(self, title: str, author: str | None) -> dict[str, Any]:
        query = f'intitle:"{title}"'
        if author:
            query += f' inauthor:"{author}"'
        url = f"https://www.googleapis.com/books/v1/volumes?{urllib.parse.urlencode({'q': query, 'maxResults': '3'})}"
        data = self._get(url)
        if not isinstance(data, dict):
            return {}
        items = data.get("items") or []
        return items[0].get("volumeInfo", {}) if items else {}

    def _fetch_estante_virtual(self, title: str, author: str | None) -> str | None:
        query = f"{title} {author}" if author else title
        url = f"https://www.estantevirtual.com.br/busca?{urllib.parse.urlencode({'q': query})}"
        result = self._get(url)
        return result if isinstance(result, str) else None

    def _fetch_skoob(self, title: str, author: str | None) -> str | None:
        query = f"{title} {author}" if author else title
        url = f"https://www.skoob.com.br/livro/busca.php?{urllib.parse.urlencode({'term': query})}"
        result = self._get(url)
        return result if isinstance(result, str) else None

    # --- synthesis via Gemini ---

    def _synthesize(
        self, title: str, author: str | None, sources: dict[str, Any], memory_context: str | None = None
    ) -> BookMetadata:
        ol = sources.get("open_library") or {}
        gb = sources.get("google_books") or {}
        ev_html = sources.get("estante_virtual")
        sk_html = sources.get("skoob")

        context_parts = [
            f"Title: {title}",
            f"Author: {author or 'unknown'}",
            "",
            "## Open Library",
            json.dumps(ol, ensure_ascii=False)[:2000] if ol else "No results.",
            "",
            "## Google Books",
            json.dumps(gb, ensure_ascii=False)[:2000] if gb else "No results.",
            "",
            "## Estante Virtual (HTML excerpt)",
            (ev_html or "No results.")[:3000],
            "",
            "## Skoob (HTML excerpt)",
            (sk_html or "No results.")[:3000],
        ]

        if memory_context:
            context_parts += ["", "## Prior Memory Context", memory_context[:2000]]

        prompt = "\n".join(context_parts)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _DEFINITION.system_prompt},
            {
                "role": "user",
                "content": f"Synthesize the following multi-source data into the required JSON structure:\n\n{prompt}",
            },
        ]

        response = complete(self.model_config, messages, temperature=0.0, response_format={"type": "json_object"})
        content = response.choices[0].message.content or ""

        try:
            data: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError:
            data = {}

        if "error" in data:
            return BookMetadata(
                title=title,
                author=author,
                isbn_13=None,
                isbn_10=None,
                publication_year=None,
                publisher=None,
                page_count=None,
                language=None,
                synopsis=None,
                genres=[],
                ratings={},
                awards=[],
                source="none",
                confidence="low",
            )

        return BookMetadata(
            title=data.get("title") or title,
            author=data.get("author") or author,
            isbn_13=data.get("isbn_13"),
            isbn_10=data.get("isbn_10"),
            publication_year=data.get("publication_year"),
            publisher=data.get("publisher"),
            page_count=data.get("page_count"),
            language=data.get("language"),
            synopsis=data.get("synopsis"),
            genres=data.get("genres") or [],
            ratings=data.get("ratings") or {},
            awards=data.get("awards") or [],
            source=data.get("source", "none"),
            confidence=data.get("confidence", "low"),
        )
