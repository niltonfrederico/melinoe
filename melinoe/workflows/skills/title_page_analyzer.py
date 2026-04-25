import base64
import json
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.client import ModelConfig
from melinoe.client import complete
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("title_page_analyzer")

_MIME_MAP: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


@dataclass
class CipData:
    author: str | None
    title: str | None
    isbn: str | None
    cdd: str | None
    cdu: str | None
    subject_headings: list[str]


@dataclass
class TitlePageAnalysis:
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
    # convenience: merged authors as single string for downstream use
    author_string: str | None = field(init=False)

    def __post_init__(self) -> None:
        self.author_string = ", ".join(self.author) if self.author else None


class TitlePageAnalyzerSkill(Step):
    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["title_page_analyzer"]

    def validate(self, file_path: Path | str, **kwargs: Any) -> None:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Title page image not found: {path}")
        if path.suffix.lower() not in _MIME_MAP:
            raise ValueError(f"Unsupported image format: {path.suffix}")

    def execute(self, file_path: Path | str, **kwargs: Any) -> TitlePageAnalysis:
        path = Path(file_path)
        image_b64 = base64.b64encode(self.load_file_bytes(path)).decode()
        mime_type = _MIME_MAP[path.suffix.lower()]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _DEFINITION.system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze this title page (folha de rosto) and return the structured JSON.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                ],
            },
        ]

        response = complete(self.model_config, messages, temperature=0.0, response_format={"type": "json_object"})
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from title page analysis model")

        data: dict[str, Any] = json.loads(content)
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
