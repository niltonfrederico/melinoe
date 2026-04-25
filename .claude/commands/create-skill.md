# Create Skill

Use the hecate sub-agent to create a new Skill definition for this project.

Arguments: $ARGUMENTS

A Skill is a focused, single-purpose `.md` file in `melinoe/workflows/skills/`. It defines a system
prompt scoped to one task (extract, classify, transform, etc.) along with its expected input/output
format and the litellm model preset to use.

Ask hecate to:

1. Derive a snake_case filename from the arguments
1. Infer the skill's purpose, input/output contract, and appropriate model preset from the description
1. Create `melinoe/workflows/skills/{name}.md` with correct frontmatter and body

If no description is provided alongside the name, ask the user what the skill should do before generating the file.
