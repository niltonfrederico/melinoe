# Melinoe — Project Rules

## What this project is

Melinoe is a Telegram bot that identifies books from cover photos. It uses a pipeline of LLM-backed skills orchestrated by `BookwormWorkflow`. The name `hallm9000` is the repo slug; the Python package is `melinoe`.

______________________________________________________________________

## Tech stack

- **Python 3.13** — use modern syntax freely (e.g. `X | Y` unions, `match`, `type` aliases)
- **Poetry** — dependency manager; never use pip directly
- **litellm** — unified LLM client abstraction (`melinoe/client.py`)
- **python-telegram-bot** — async Telegram integration
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

- **No relative imports** — ruff enforces this; all imports must be absolute
- **Single-line isort** — one import per line
- **Type annotations everywhere** — use `ClassVar` for class-level attributes, `Any` only when unavoidable
- **No comments on obvious code** — only add a comment when the *why* is non-obvious
- **No docstrings on trivial methods** — module-level docstrings are fine; skip them on short helpers
- **Dataclasses for all structured data** — prefer `@dataclass` or `@dataclass(frozen=True)` over plain dicts for return types

______________________________________________________________________

## Development commands

```bash
# Run the bot
poetry run python -m melinoe.bot

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

Never access `os.environ` directly in business logic — go through `settings.py` or the `ModelConfig.api_key_env` indirection in `client.py`.

______________________________________________________________________

## Output structure

Results are written to `output/<timestamp>-<author>-<title>/`:

- `cover.<ext>` — copy of the input cover image
- `title_page.<ext>` — copy of the title page (if provided)
- `result.json` — full JSON output with `cover_analysis`, `title_page_analysis`, `bibliographic_metadata`, `report_confidence`, and `notes`

______________________________________________________________________

## What to avoid

- Don't add new dependencies without discussing first — the dependency list is intentionally minimal
- Don't call `execute()` directly on a `Step` — always use `run()` to get logging and timing
- Don't store secrets or API keys in code or committed files — use `.env`
- Don't add error handling for impossible cases — trust the dataclass contract and `validate()` gates
- Don't invent new LLM client wrappers — extend `client.py` if a new model is needed
