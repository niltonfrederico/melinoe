"""LLM client abstraction: model configurations and completion helpers."""

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import litellm

from melinoe.logger import llm_log

SUPPORTED_IMAGE_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


@dataclass(frozen=True)
class ModelConfig:
    """Identifies an LLM endpoint (model name, API key env var, optional base URL)."""

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
    model="claude-sonnet-4-6",
    api_key_env="ANTHROPIC_API_KEY",
)

CLAUDE_OPUS = ModelConfig(
    model="claude-opus-4-7",
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
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> litellm.ModelResponse:
    """Call the LLM and return the raw response, logging timing and token usage."""
    call_kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "api_key": os.environ.get(config.api_key_env),
        **kwargs,
    }
    if config.api_base is not None:
        call_kwargs["api_base"] = config.api_base
    llm_log.info(f"Calling {config.model}...")
    start = time.perf_counter()
    response = litellm.completion(**call_kwargs)
    elapsed = time.perf_counter() - start
    usage = getattr(response, "usage", None)
    tokens = f"{usage.total_tokens} tokens" if usage else "usage unavailable"
    llm_log.info(f"{config.model} responded in {elapsed:.2f}s ({tokens})")
    return response


def complete_json(
    config: ModelConfig,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    """Call the LLM with JSON response format and return the parsed dict.

    Raises ValueError if the model returns empty content or unparseable JSON.
    """
    kwargs.setdefault("response_format", {"type": "json_object"})
    kwargs.setdefault("temperature", 0.0)
    response = complete(config, messages, **kwargs)
    content = response.choices[0].message.content
    if not content:
        raise ValueError(f"Empty JSON response from {config.model}")
    return json.loads(content)
