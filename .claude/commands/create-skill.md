Use the hecate sub-agent to create a new Skill for this project.

Arguments: $ARGUMENTS

A Skill is a `Step` subclass in `melinoe/workflows/skills/`. It does exactly one focused thing — parse input, call an LLM, transform data — and is reusable across multiple agents.

Ask hecate to:

1. Derive a snake_case filename and PascalCase class name from the arguments
1. Infer the skill's purpose and the right `ModelConfig` preset from the description
1. Create `melinoe/workflows/skills/{name}.py` with a complete `Step` subclass
1. Update `melinoe/workflows/skills/__init__.py` to export the new class

If no description is provided alongside the name, ask the user what the skill should do before generating code.
