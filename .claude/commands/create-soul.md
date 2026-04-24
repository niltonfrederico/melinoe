Use the hecate sub-agent to create a new Soul for this project.

Arguments: $ARGUMENTS

A Soul is a stateful, persona-driven entity in `melinoe/workflows/souls/`. Unlike Skills and Agents, a Soul is not a `Step` or `Workflow` subclass — it maintains a conversation `history`, has a fixed `name` and `system_prompt` that define its persona, and exposes a `chat(message)` method. Souls are built for multi-turn interactions where context must persist across calls.

Ask hecate to:

1. Derive a snake_case filename and PascalCase class name from the arguments
1. Craft a `system_prompt` that reflects the soul's persona and purpose based on the description
1. Choose an appropriate `ModelConfig` preset (conversational souls often benefit from CLAUDE_SONNET for quality)
1. Create `melinoe/workflows/souls/{name}.py` with a complete Soul class (name, system_prompt, model_config, history, chat, reset)
1. Update `melinoe/workflows/souls/__init__.py` to export the new class

If no personality or purpose is described, ask the user before generating the soul.
