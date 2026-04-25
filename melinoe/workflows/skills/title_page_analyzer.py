"""TitlePageAnalyzerSkill: extracts bibliographic data from a book's title page (folha de rosto)."""

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.clients.ai import ModelConfig
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("title_page_analyzer")


@dataclass
class CipData:
    """Brazilian CIP (Cataloging in Publication) data block from the title page verso."""

    author: str | None
    title: str | None
    isbn: str | None
    cdd: str | None
    cdu: str | None
    subject_headings: list[str]


@dataclass
class TitlePageAnalysis:
    """Bibliographic data extracted from a book's title page."""

    title: str | None
    subtitle: str | None
    author: list[str]
    publisher: str | None
    isbn_13: str | None
    isbn_10: str | None
    edition: str | None
    publication_year: int | None
    city_of_publication: str | None
    copyright_year: int | None
    printer: str | None
    legal_deposit: str | None
    cip_data: CipData
    confidence: str
    # Merged authors as a single string for downstream use
    author_string: str | None = field(init=False)

    def __post_init__(self) -> None:
        self.author_string = ", ".join(self.author) if self.author else None


class TitlePageAnalyzerSkill(Step):
    """Transcribes title page data (ISBN, edition, publisher, CIP) without inference."""

    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["title_page_analyzer"]

    def validate(self, file_path: Path | str, **kwargs: Any) -> None:
        self._validate_image_file(file_path, label="Title page image")

    def execute(self, file_path: Path | str, **kwargs: Any) -> TitlePageAnalysis:
        data = self._complete_image_json(
            file_path,
            system_prompt=_DEFINITION.system_prompt,
            user_text="Analyze this title page (folha de rosto) and return the structured JSON.",
        )
        raw_cip: dict[str, Any] = data.get("cip_data") or {}
        return TitlePageAnalysis(
            title=data.get("title"),
            subtitle=data.get("subtitle"),
            author=data.get("author") or [],
            publisher=data.get("publisher"),
            isbn_13=data.get("isbn_13"),
            isbn_10=data.get("isbn_10"),
            edition=data.get("edition"),
            publication_year=data.get("publication_year"),
            city_of_publication=data.get("city_of_publication"),
            copyright_year=data.get("copyright_year"),
            printer=data.get("printer"),
            legal_deposit=data.get("legal_deposit"),
            cip_data=CipData(
                author=raw_cip.get("author"),
                title=raw_cip.get("title"),
                isbn=raw_cip.get("isbn"),
                cdd=raw_cip.get("cdd"),
                cdu=raw_cip.get("cdu"),
                subject_headings=raw_cip.get("subject_headings") or [],
            ),
            confidence=data.get("confidence", "low"),
        )
