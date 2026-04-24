import os
import tempfile
import time
from abc import ABC
from abc import abstractmethod
from pathlib import Path

from melinoe.client import ModelConfig
from melinoe.logger import step_log

_MEMORY_DIR = Path(__file__).parent / "memories"


class Step(ABC):
    model_config: ModelConfig
    skills: list[str]

    def __init__(self):
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

    def __del__(self):
        self.cleanup_temp_files()

    @abstractmethod
    def validate(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def execute(self, *args, **kwargs):
        pass

    def run(self, *args, **kwargs):
        name = type(self).__name__
        step_log.info(f"{name} starting...")
        start = time.perf_counter()
        try:
            self.validate(*args, **kwargs)
            result = self.execute(*args, **kwargs)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            step_log.error(f"{name} failed after {elapsed:.2f}s — {exc}")
            raise
        elapsed = time.perf_counter() - start
        step_log.info(f"{name} done ({elapsed:.2f}s)")
        return result


class Workflow(ABC):
    agent: str
    steps: list[Step]

    def __init__(self):
        self.validate_init()

    def validate_init(self) -> None:
        if not hasattr(self, "agent") or not self.agent:
            raise ValueError("agent is required for Workflow initialization.")

    # --- memory ---

    def load_memory(self, key: str) -> str | None:
        path = _MEMORY_DIR / f"{key}.md"
        return path.read_text() if path.exists() else None

    def save_memory(self, key: str, content: str) -> None:
        _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        (_MEMORY_DIR / f"{key}.md").write_text(content)

    def delete_memory(self, key: str) -> None:
        (_MEMORY_DIR / f"{key}.md").unlink(missing_ok=True)

    # --- file I/O ---

    def load_file(self, path: Path | str) -> str:
        return Path(path).read_text()

    def load_file_bytes(self, path: Path | str) -> bytes:
        return Path(path).read_bytes()

    def load_files(self, paths: list[Path | str]) -> dict[str, str]:
        return {str(p): self.load_file(p) for p in paths}

    @abstractmethod
    def run(self, *args, **kwargs):
        pass
