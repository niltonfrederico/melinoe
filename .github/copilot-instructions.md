# Melinoe — Copilot Instructions

## Project overview

Melinoe is a Telegram bot that identifies books from cover photos, orchestrated by `BookwormWorkflow`. The repo slug is `melinoe`; the Python package is `melinoe`. Two specialist agents handle the literary works of Nilton Manoel de Andrade Teixeira (O Professor): `KardoNavalhaWorkflow` (physical cover cataloging → Meilisearch) and `SenhorDasHorasMortasWorkflow` (ARQ-scheduled web scraper).

See [CLAUDE.md](../.claude/CLAUDE.md) for architecture details, agent guidelines, and project conventions.

______________________________________________________________________

## Tech stack

- **Python 3.13** — use modern syntax (`X | Y` unions, `match`, `type` aliases)
- **Poetry** — dependency manager; never use pip directly
- **litellm** — unified LLM client (`melinoe/clients/ai.py`)
- **python-telegram-bot** — async Telegram integration
- **arq** — asyncio-native Redis task queue (`melinoe/worker.py`)
- **ruff** — linter and formatter (line length 120)
- **ty** — type checker

______________________________________________________________________

## Python coding standards

### PEP 8

- Line length: 120 characters (ruff-enforced)
- Two blank lines between top-level definitions; one blank line between methods
- `snake_case` for functions/variables; `PascalCase` for classes; `UPPER_SNAKE_CASE` for module-level constants

### Typing — strict, no exceptions

- **Every** function parameter, return type, and class attribute must have a type annotation
- Use `X | Y` unions (Python 3.10+ syntax); never `Union[X, Y]` or `Optional[X]`
- Use `ClassVar[T]` for class-level attributes
- **Never use `Any`** — if `Any` seems necessary, stop and ask the user to clarify the intended type
- **Never use `# type: ignore`** — if a suppression seems necessary, stop and ask the user; fix the underlying issue instead
- Use `@dataclass` or `@dataclass(frozen=True)` for all structured return types; no plain dicts
- Parameterize all generic types: `list[str]`, `dict[str, int]`, not `list`, `dict`

### Imports

- **All imports at module top level** — never inside functions, methods, or conditional blocks
- Typing-only imports (used only in annotations) must live inside `if TYPE_CHECKING:` blocks
- Absolute imports only — no relative imports (ruff enforces this)
- One import per line (single-line isort)

```python
# correct
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from melinoe.workflows.base import Step
```

### Architecture rules

- Call `Step.run()`, never `Step.execute()` directly — `run()` handles logging and timing
- Use `self._emit(message)` in `Workflow` subclasses for Telegram progress updates
- Never hardcode model strings — use `ModelConfig` constants from `melinoe/clients/ai.py`
- Never access `os.environ` directly in business logic — use `melinoe/settings.py`
- Don't add dependencies without explicit discussion

______________________________________________________________________

## Build and test

```bash
poetry run ruff check melinoe/      # lint
poetry run ruff format melinoe/     # format
poetry run ty check melinoe/        # type check
poetry run pytest                   # tests
poetry run python -m melinoe.bot    # run bot
poetry run python -m arq melinoe.worker.WorkerSettings  # run ARQ worker
```

Pre-commit runs ruff on every commit — never skip with `--no-verify`.
