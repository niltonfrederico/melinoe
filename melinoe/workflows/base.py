"""Abstract base classes for workflow steps and workflow orchestrators."""

import base64
import os
import tempfile
import time
from abc import ABC
from abc import abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from melinoe.clients.ai import SUPPORTED_IMAGE_TYPES
from melinoe.clients.ai import ModelConfig
from melinoe.clients.ai import complete_json
from melinoe.logger import step_log

MEMORY_DIR = Path(__file__).parent / "memories"


class Step(ABC):
    """Atomic, reusable workflow step backed by a single LLM call.

    Subclasses must set `model_config` and implement `validate()` and `execute()`.
    """

    model_config: ModelConfig
    skills: list[str]

    def __init__(self) -> None:
        self._temp_files: list[Path] = []
        if not hasattr(type(self), "skills"):
            self.skills = []
        self.validate_init()

    def validate_init(self) -> None:
        if not hasattr(self, "model_config") or not self.model_config:
            raise ValueError("ModelConfig is required for Step initialization.")

    def load_file(self, path: Path | str) -> str:
        return Path(path).read_text()

    def load_file_bytes(self, path: Path | str) -> bytes:
        return Path(path).read_bytes()

    def write_output(self, path: Path | str, content: str) -> None:
        Path(path).write_text(content)

    def create_temp_file(self, suffix: str = ".tmp", content: str | None = None) -> Path:
        fd, raw = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        path = Path(raw)
        if content is not None:
            path.write_text(content)
        self._temp_files.append(path)
        return path

    def remove_temp_file(self, path: Path | str) -> None:
        resolved = Path(path)
        resolved.unlink(missing_ok=True)
        self._temp_files = [p for p in self._temp_files if p != resolved]

    def cleanup_temp_files(self) -> None:
        for p in self._temp_files:
            p.unlink(missing_ok=True)
        self._temp_files.clear()

    def __del__(self) -> None:
        self.cleanup_temp_files()

    # --- image helpers ---

    def _validate_image_file(self, path: Path | str, label: str = "Image") -> None:
        """Raise if path does not exist or has an unsupported image extension."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"{label} not found: {p}")
        if p.suffix.lower() not in SUPPORTED_IMAGE_TYPES:
            raise ValueError(f"Unsupported image format: {p.suffix}")

    def _complete_image_json(
        self,
        path: Path | str,
        system_prompt: str,
        user_text: str,
    ) -> dict[str, Any]:
        """Base64-encode an image, send it to the configured model, and return the parsed JSON dict."""
        p = Path(path)
        image_b64 = base64.b64encode(self.load_file_bytes(p)).decode()
        mime_type = SUPPORTED_IMAGE_TYPES[p.suffix.lower()]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                ],
            },
        ]
        return complete_json(self.model_config, messages)

    # --- lifecycle ---

    @abstractmethod
    def validate(self, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        pass

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Validate inputs, execute, and return the result; logs timing on success and failure."""
        name = type(self).__name__
        step_log.info("%s starting...", name)
        start = time.perf_counter()
        try:
            self.validate(*args, **kwargs)
            result = self.execute(*args, **kwargs)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            step_log.error("%s failed after %.2fs — %s", name, elapsed, exc)
            raise
        elapsed = time.perf_counter() - start
        step_log.info("%s done (%.2fs)", name, elapsed)
        return result


class Workflow(ABC):
    """Orchestrates an ordered sequence of Steps and manages persistent memory."""

    agent: str
    steps: list[Step]

    def __init__(self) -> None:
        self.on_progress: Callable[[str], None] | None = None
        self.validate_init()

    def _emit(self, message: str) -> None:
        """Fire the progress callback if one is registered."""
        if self.on_progress is not None:
            self.on_progress(message)

    def validate_init(self) -> None:
        if not hasattr(self, "agent") or not self.agent:
            raise ValueError("agent is required for Workflow initialization.")

    # --- memory ---

    def load_memory(self, key: str) -> str | None:
        path = MEMORY_DIR / f"{key}.md"
        return path.read_text() if path.exists() else None

    def save_memory(self, key: str, content: str) -> None:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        (MEMORY_DIR / f"{key}.md").write_text(content)

    def delete_memory(self, key: str) -> None:
        (MEMORY_DIR / f"{key}.md").unlink(missing_ok=True)

    # --- file I/O ---

    def load_file(self, path: Path | str) -> str:
        return Path(path).read_text()

    def load_file_bytes(self, path: Path | str) -> bytes:
        return Path(path).read_bytes()

    def load_files(self, paths: list[Path | str]) -> dict[str, str]:
        return {str(p): self.load_file(p) for p in paths}

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        pass


def merged_confidence(a: str, b: str) -> str:
    """Return the lower of two confidence strings ('high', 'medium', 'low')."""
    order = {"high": 2, "medium": 1, "low": 0}
    level = min(order.get(a, 0), order.get(b, 0))
    return ["low", "medium", "high"][level]
