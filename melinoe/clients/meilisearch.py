"""Meilisearch client for indexing book analysis results."""

import re
from typing import Any

import meilisearch

from melinoe.logger import workflow_log

_SEARCHABLE_ATTRIBUTES = [
    "title",
    "author",
    "synopsis",
    "genres",
    "publisher",
    "isbn_13",
    "isbn_10",
]

_FILTERABLE_ATTRIBUTES = [
    "publication_year",
    "language",
    "origin",
    "confidence",
    "genres",
]


class MeilisearchClient:
    INDEX_NAME = "books"

    def __init__(self, url: str, api_key: str) -> None:
        self._client = meilisearch.Client(url, api_key)
        self._index = self._ensure_index()

    def index_book(self, document: dict[str, Any]) -> None:
        self._index.add_documents([document])
        workflow_log.info(f"Meilisearch ← indexed '{document.get('title')}' (id={document.get('id')})")

    def delete_book(self, book_id: str) -> None:
        self._index.delete_document(book_id)
        workflow_log.info(f"Meilisearch ← deleted id={book_id}")

    def _ensure_index(self) -> meilisearch.index.Index:
        try:
            self._client.create_index(self.INDEX_NAME, {"primaryKey": "id"})
        except meilisearch.errors.MeilisearchApiError as exc:
            if exc.code != "index_already_exists":
                raise
        index = self._client.index(self.INDEX_NAME)
        index.update_searchable_attributes(_SEARCHABLE_ATTRIBUTES)
        index.update_filterable_attributes(_FILTERABLE_ATTRIBUTES)
        return index


def _sanitize_id(folder_name: str) -> str:
    # Meilisearch IDs only allow a-z A-Z 0-9, hyphens, and underscores
    return re.sub(r"[^a-zA-Z0-9\-_]", "_", folder_name)


def build_book_document(folder_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Flatten result.json into a Meilisearch-optimized document."""
    meta: dict[str, Any] = result.get("bibliographic_metadata") or {}
    ratings: dict[str, Any] = meta.get("ratings") or {}
    return {
        "id": _sanitize_id(folder_name),
        "title": meta.get("title"),
        "author": meta.get("author"),
        "isbn_13": meta.get("isbn_13"),
        "isbn_10": meta.get("isbn_10"),
        "publication_year": meta.get("publication_year"),
        "publisher": meta.get("publisher"),
        "page_count": meta.get("page_count"),
        "language": meta.get("language"),
        "synopsis": meta.get("synopsis"),
        "genres": meta.get("genres") or [],
        "awards": meta.get("awards") or [],
        "origin": meta.get("origin"),
        "content_type": meta.get("content_type"),
        "goodreads_average": ratings.get("goodreads_average"),
        "goodreads_count": ratings.get("goodreads_count"),
        "cover_url": result.get("cover_url"),
        "title_page_url": result.get("title_page_url"),
        "confidence": result.get("report_confidence"),
        "analyzed_at": folder_name[:15].replace("_", "T")[:15],
    }
