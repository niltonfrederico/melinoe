import base64
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import litellm


@dataclass(frozen=True)
class ModelConfig:
    model: str
    api_key_env: str
    api_base: str | None = None


GEMINI_FLASH = ModelConfig(
    model="gemini/gemini-2.5-flash",
    api_key_env="GEMINI_API_KEY",
)

GEMINI_PRO = ModelConfig(
    model="gemini/gemini-2.5-pro",
    api_key_env="GEMINI_API_KEY",
)

CLAUDE_SONNET = ModelConfig(
    model="claude-sonnet-4-5",
    api_key_env="ANTHROPIC_API_KEY",
)

CLAUDE_OPUS = ModelConfig(
    model="claude-opus-4-5",
    api_key_env="ANTHROPIC_API_KEY",
)

GITHUB_COPILOT_GPT4O = ModelConfig(
    model="openai/gpt-4o",
    api_key_env="GITHUB_COPILOT_API_KEY",
    api_base="https://models.inference.ai.azure.com",
)

GITHUB_COPILOT_O1_REASONING = ModelConfig(
    model="openai/o1",
    api_key_env="GITHUB_COPILOT_API_KEY",
    api_base="https://models.inference.ai.azure.com",
)


def complete(
    config: ModelConfig,
    messages: list[dict[str, str]],
    **kwargs: Any,
) -> litellm.ModelResponse:
    call_kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "api_key": os.environ.get(config.api_key_env),
        **kwargs,
    }
    if config.api_base is not None:
        call_kwargs["api_base"] = config.api_base
    return litellm.completion(**call_kwargs)


@dataclass(frozen=True)
class BookCoverMetadata:
    """Structured metadata extracted from a book cover via OCR."""

    title: str
    author: str | None = None
    year: int | None = None


def extract_book_cover_metadata(
    image_path: Path | str,
    config: ModelConfig = GEMINI_FLASH,
) -> BookCoverMetadata:
    """
    Extract book metadata (title, author, year) from a cover image using OCR.

    Args:
        image_path: Path to the book cover image file
        config: AI model configuration (default: Gemini Flash for cost/speed)

    Returns:
        BookCoverMetadata with extracted title, author, and year

    Raises:
        FileNotFoundError: If image_path does not exist
        ValueError: If the model fails to extract required metadata
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Read and encode image as base64
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Determine MIME type from file extension
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime_type = mime_map.get(image_path.suffix.lower(), "image/jpeg")

    prompt = """You are analyzing a book cover image. Extract the following information:

1. **Title**: The main title of the book (required)
2. **Author**: The author's name (if visible on the cover)
3. **Year**: The publication year (if visible on the cover)

Return your response EXACTLY in this JSON format (no additional text, no markdown):
{
  "title": "extracted title here",
  "author": "extracted author name or null",
  "year": extracted_year_as_number_or_null
}

Rules:
- If author is not visible, use null
- If year is not visible, use null
- Year must be a number (e.g., 2024) or null, not a string
- Be precise: extract exactly what's on the cover, don't infer or guess"""

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": f"data:{mime_type};base64,{image_b64}",
                },
            ],
        }
    ]

    response = complete(config, messages, temperature=0.0, response_format={"type": "json_object"})

    # Extract JSON from response
    import json

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("Model returned empty response")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse model response as JSON: {e}") from e

    # Validate required fields
    if "title" not in data or not data["title"]:
        raise ValueError("Model failed to extract book title")

    return BookCoverMetadata(
        title=data["title"],
        author=data.get("author"),
        year=data.get("year"),
    )
