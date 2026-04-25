# Melinoe — Project Rules

## What this project is

Melinoe is a Telegram bot that identifies books from cover photos. It uses a pipeline of LLM-backed skills orchestrated by `BookwormWorkflow`. The name `hallm9000` is the repo slug; the Python package is `melinoe`.

Melinoe also has two specialized agents for the literary work of **Nilton Manoel de Andrade Teixeira** (O Professor):

- **KardoNavalhaWorkflow** — catalogs physical covers of his works into the `nilton_works` Meilisearch index
- **SenhorDasHorasMortasWorkflow** — autonomous ARQ-scheduled web scraper that maps his digital presence and enriches `professor_profile.md`

______________________________________________________________________

## Tech stack

- **Python 3.13** — use modern syntax freely (e.g. `X | Y` unions, `match`, `type` aliases)
- **Poetry** — dependency manager; never use pip directly
- **litellm** — unified LLM client abstraction (`melinoe/client.py`)
- **python-telegram-bot** — async Telegram integration
- **arq** — asyncio-native Redis task queue for background jobs (worker: `melinoe/worker.py`)
- **ruff** — linter and formatter (line length 120, absolute imports only)
- **ty** — type checker

______________________________________________________________________

## Architecture

### Core abstractions (`melinoe/workflows/base.py`)

**`Step`** — one atomic LLM call. Subclasses must:

- Set a class-level `model_config: ModelConfig`
- Implement `validate(*args, **kwargs) -> None` — raise on bad input
- Implement `execute(*args, **kwargs)` — return a dataclass
- Call via `run()`, never `execute()` directly — `run()` handles logging and timing

**`Workflow`** — orchestrates an ordered list of Steps. Subclasses must:

- Set a class-level `agent: str` matching an `.md` file in `workflows/agents/`
- Implement `run(*args, **kwargs)`
- Use `self._emit(message)` for progress updates to the Telegram bot

### Definition files (`.md` with YAML frontmatter)

Every skill, agent, and soul is defined by a paired Markdown file loaded via `loader.py`. Frontmatter fields:

```
---
name: <name>
type: skill | agent | soul
model: GEMINI_FLASH | GEMINI_PRO | CLAUDE_SONNET | CLAUDE_OPUS | GITHUB_COPILOT_GPT4O | GITHUB_COPILOT_O1_REASONING
description: <one-line description>
---
<system prompt body>
```

- Skills live in `melinoe/workflows/skills/<name>.md` + `<name>.py`
- Agents live in `melinoe/workflows/agents/<name>.md`
- Souls live in `melinoe/workflows/souls/<name>.md`

### Model assignment policy

| Task type | Model |
|---|---|
| Vision (cover/title page analysis, validation) | `GEMINI_FLASH` |
| Memory filtering and synthesis | `GITHUB_COPILOT_GPT4O` |
| Heavy reasoning or fallback | `GEMINI_PRO` or `CLAUDE_SONNET` |

Never hardcode a model string — always use the `ModelConfig` constants from `melinoe/client.py`.

### Structured output

Skills return **dataclasses**, not raw dicts. Always define a dataclass for the result type alongside the skill class in the same file.

### Memory

Persistent book memories live in `melinoe/workflows/memories/<slug>.md` (one file per book). The `Workflow` base class provides `load_memory`, `save_memory`, and `delete_memory`.

______________________________________________________________________

## Code conventions

### Imports

- **No relative imports** — ruff enforces this; all imports must be absolute
- **Single-line isort** — one import per line
- **All imports at module top level** — never inside functions, methods, or conditional blocks
- **Typing-only imports inside `TYPE_CHECKING`** — any symbol used only in annotations must live in an `if TYPE_CHECKING:` block

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from melinoe.workflows.base import Step
```

### Typing — strict

- **Type annotations everywhere** — every parameter, return type, and class attribute
- Use `ClassVar[T]` for class-level attributes
- Use `X | Y` unions (Python 3.10+); never `Union[X, Y]` or `Optional[X]`
- **Never use `Any`** — if `Any` appears necessary, stop and ask the user to clarify the intended type before proceeding
- **Never use `# type: ignore`** — fix the underlying issue; if a suppression seems unavoidable, ask the user first
- Parameterize all generic types: `list[str]`, `dict[str, int]`, not `list`, `dict`

### Style

- **No comments on obvious code** — only add a comment when the *why* is non-obvious
- **No docstrings on trivial methods** — module-level docstrings are fine; skip them on short helpers
- **Dataclasses for all structured data** — prefer `@dataclass` or `@dataclass(frozen=True)` over plain dicts for return types
- Line length: 120 characters (ruff-enforced)
- Two blank lines between top-level definitions; one blank line between methods

______________________________________________________________________

## Development commands

```bash
# Run the bot
poetry run python -m melinoe.bot

# Run the ARQ worker (Senhor das Horas Mortas cron + KardoNavalha enqueue)
poetry run python -m arq melinoe.worker.WorkerSettings

# Run the CLI script
poetry run python scripts/cover_analyzer.py path/to/cover.jpg

# Lint
poetry run ruff check melinoe/

# Format
poetry run ruff format melinoe/

# Type check
poetry run ty check melinoe/

# Install pre-commit hooks (once)
poetry run pre-commit install
```

Pre-commit runs ruff automatically on every commit. Never skip it with `--no-verify`.

______________________________________________________________________

## Adding a new skill

1. Create `melinoe/workflows/skills/<name>.md` with the frontmatter and system prompt
1. Create `melinoe/workflows/skills/<name>.py` with:
   - A result dataclass
   - A `Step` subclass with `model_config`, `validate()`, and `execute()`
1. Export from `melinoe/workflows/skills/__init__.py`
1. Wire into the relevant `Workflow` if needed

______________________________________________________________________

## Environment variables

Defined in `melinoe/settings.py` via `environs`. Required:

- `TELEGRAM_BOT_TOKEN`
- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY` (optional, for Claude models)
- `GITHUB_COPILOT_API_KEY`
- `REDIS_URL` (default: `redis://localhost:6379`)
- `MEILISEARCH_URL` + `MEILISEARCH_API_KEY`

Never access `os.environ` directly in business logic — go through `settings.py` or the `ModelConfig.api_key_env` indirection in `client.py`.

______________________________________________________________________

## Professor agents — Nilton Manoel de Andrade Teixeira

### Identity disambiguation — three writers named Nilton

There are three writers named Nilton in the same family. Never confuse them:

| Name | Relation | Role in this system |
|---|---|---|
| **Nilton Manoel de Andrade Teixeira** | O Professor (the father) | **Target** — all professor\_ code refers to him |
| **Nilton da Costa** | Grandfather — also a writer | Out of scope — do not catalog |
| **Nilton Frederico** | Son of Nilton Manoel — also a writer | Out of scope — do not catalog |

He signed his works as **Nilton Manoel** (without the full surname). The full legal name appears in prompts for disambiguation confidence.

### Pseudonyms

- **Kardo Navalha** — used in some works and as agent persona name
- **Senhor das Horas Mortas** — used in some works and as scraper agent persona name

### Work types

`trova | haicai | aldravia | soneto | conto | cronica | jornal | pesquisa | poesia | poema | entrevista | jogo_floral | manuscrito | outro`

### Associations

- **UBT** — União Brasileira de Trovadores (correct name; not UBRATT, not ABT)
- **Jogos Florais** — trovadorismo competitions he participated in

### Naming convention in code

- All Python identifiers use `professor`: `ProfessorDetectorSkill`, `professor_classifier.py`, `professor_profile.md`, etc.
- "Nilton Manoel" / "O Professor" only appears inside `.md` system prompts and prose
- `KardoNavalhaWorkflow` and `SenhorDasHorasMortasWorkflow` are proper names — kept as-is

### Meilisearch indexes

- `books` — existing index for general book catalog
- `nilton_works` — new index for Professor's work catalog (`NiltonWorksMeilisearchClient`)

### ARQ background jobs

- `scrape_task` — runs `SenhorDasHorasMortasWorkflow`; triggered by cron (03:00 UTC daily) or by `KardoNavalhaWorkflow` after a new work is cataloged
- Worker entry point: `poetry run python -m arq melinoe.worker.WorkerSettings`

______________________________________________________________________

## Output structure

Results are written to `output/<timestamp>-<author>-<title>/`:

- `cover.<ext>` — copy of the input cover image
- `title_page.<ext>` — copy of the title page (if provided)
- `result.json` — full JSON output with `cover_analysis`, `title_page_analysis`, `bibliographic_metadata`, `report_confidence`, and `notes`

Professor works write to `output/professor/<timestamp>-professor-<type>-<title>/` with the same structure plus `catalog` and `classification` fields.

______________________________________________________________________

## What to avoid

- Don't add new dependencies without discussing first — the dependency list is intentionally minimal
- Don't call `execute()` directly on a `Step` — always use `run()` to get logging and timing
- Don't store secrets or API keys in code or committed files — use `.env`
- Don't add error handling for impossible cases — trust the dataclass contract and `validate()` gates
- Don't invent new LLM client wrappers — extend `client.py` if a new model is needed
