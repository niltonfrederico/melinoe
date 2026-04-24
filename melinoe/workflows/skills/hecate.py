import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import ClassVar

from melinoe.client import ModelConfig
from melinoe.client import complete
from melinoe.workflows.base import Step
from melinoe.workflows.skills.loader import load_skill

_DEFINITION = load_skill("hecate")

_MIME_MAP: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


@dataclass
class BookCoverCheck:
    is_book_cover: bool
    is_legible: bool
    reason: str


class HecateSkill(Step):
    model_config: ModelConfig = _DEFINITION.model
    skills: ClassVar[list[str]] = ["hecate"]

    def validate(self, file_path: Path | str, **kwargs: Any) -> None:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        if path.suffix.lower() not in _MIME_MAP:
            raise ValueError(f"Unsupported image format: {path.suffix}")

    def execute(self, file_path: Path | str, **kwargs: Any) -> BookCoverCheck:
        path = Path(file_path)
        image_b64 = base64.b64encode(self.load_file_bytes(path)).decode()
        mime_type = _MIME_MAP[path.suffix.lower()]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _DEFINITION.system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Avalie esta imagem e retorne o JSON."},
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
            raise ValueError("Empty response from image check model")

        data: dict[str, Any] = json.loads(content)
        return BookCoverCheck(
            is_book_cover=bool(data.get("is_book_cover", False)),
            is_legible=bool(data.get("is_legible", False)),
            reason=data.get("reason", ""),
        )
