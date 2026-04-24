from dataclasses import dataclass
from pathlib import Path

from melinoe.client import CLAUDE_OPUS
from melinoe.client import CLAUDE_SONNET
from melinoe.client import GEMINI_FLASH
from melinoe.client import GEMINI_PRO
from melinoe.client import GITHUB_COPILOT_GPT4O
from melinoe.client import GITHUB_COPILOT_O1_REASONING
from melinoe.client import ModelConfig

_WORKFLOWS_DIR = Path(__file__).parent.parent

_MODEL_PRESETS: dict[str, ModelConfig] = {
    "GEMINI_FLASH": GEMINI_FLASH,
    "GEMINI_PRO": GEMINI_PRO,
    "CLAUDE_SONNET": CLAUDE_SONNET,
    "CLAUDE_OPUS": CLAUDE_OPUS,
    "GITHUB_COPILOT_GPT4O": GITHUB_COPILOT_GPT4O,
    "GITHUB_COPILOT_O1_REASONING": GITHUB_COPILOT_O1_REASONING,
}


@dataclass(frozen=True)
class Definition:
    name: str
    type: str
    model: ModelConfig
    description: str
    system_prompt: str


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.index("---", 3)
    front = text[3:end].strip()
    body = text[end + 3 :].strip()
    meta: dict[str, str] = {}
    for line in front.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return meta, body


def load(name: str, definition_type: str) -> Definition:
    path = _WORKFLOWS_DIR / f"{definition_type}s" / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Definition not found: {path}")
    meta, body = _parse_frontmatter(path.read_text())
    model = _MODEL_PRESETS.get(meta.get("model", ""), GEMINI_FLASH)
    return Definition(
        name=meta.get("name", name),
        type=meta.get("type", definition_type),
        model=model,
        description=meta.get("description", ""),
        system_prompt=body,
    )


def load_skill(name: str) -> Definition:
    return load(name, "skill")


def load_agent(name: str) -> Definition:
    return load(name, "agent")


def load_soul(name: str) -> Definition:
    return load(name, "soul")
