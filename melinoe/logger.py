import logging
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_MAGENTA = "\033[35m"
_BLUE = "\033[34m"

_LEVEL_STYLES: dict[int, str] = {
    logging.DEBUG: _DIM,
    logging.INFO: _CYAN,
    logging.WARNING: _YELLOW,
    logging.ERROR: _RED,
    logging.CRITICAL: _BOLD + _RED,
}

_NAME_COLORS: dict[str, str] = {
    "workflow": _MAGENTA,
    "step": _BLUE,
    "llm": _GREEN,
}


class _ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        level_style = _LEVEL_STYLES.get(record.levelno, _RESET)
        name_color = _NAME_COLORS.get(record.name, _CYAN)
        tag = f"{name_color}{_BOLD}[{record.name}]{_RESET}"
        msg = f"{level_style}{record.getMessage()}{_RESET}"
        return f"{tag} {msg}"


def _make_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"melinoe.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_ConsoleFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger


workflow_log = _make_logger("workflow")
step_log = _make_logger("step")
llm_log = _make_logger("llm")
bot_log = _make_logger("bot")


@contextmanager
def timed_step(name: str) -> Generator[None, None, None]:
    step_log.info(f"{name} starting...")
    start = time.perf_counter()
    try:
        yield
    except Exception as exc:
        elapsed = time.perf_counter() - start
        step_log.error(f"{name} failed after {elapsed:.2f}s — {exc}")
        raise
    else:
        elapsed = time.perf_counter() - start
        step_log.info(f"{name} done ({elapsed:.2f}s)")


@contextmanager
def timed_workflow(name: str) -> Generator[None, None, None]:
    workflow_log.info(f"{_BOLD}{name}{_RESET} starting")
    start = time.perf_counter()
    try:
        yield
    except Exception as exc:
        elapsed = time.perf_counter() - start
        workflow_log.error(f"{name} failed after {elapsed:.2f}s — {exc}")
        raise
    else:
        elapsed = time.perf_counter() - start
        workflow_log.info(f"{_BOLD}{name}{_RESET} completed in {elapsed:.2f}s")
