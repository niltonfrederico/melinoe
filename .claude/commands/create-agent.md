# Create Agent

Use the hecate sub-agent to create a new Agent for this project.

Arguments: $ARGUMENTS

An Agent is a `Workflow` subclass in `melinoe/workflows/agents/`. It orchestrates one or more Skills
(Steps) to accomplish a multi-step goal. It holds a `steps: list[Step]` and implements `run()`.

Ask hecate to:

1. Derive a snake_case filename and PascalCase class name from the arguments
1. Infer which existing Skills (if any) the agent should compose, or leave `steps` as an empty list
   with a comment for what to add
1. Create `melinoe/workflows/agents/{name}.py` with a complete `Workflow` subclass
1. Update `melinoe/workflows/agents/__init__.py` to export the new class

If the description is ambiguous about what the agent should orchestrate, ask the user before generating code.
