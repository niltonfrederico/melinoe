---
name: load_relevant_memory
type: skill
model: GITHUB_COPILOT_GPT4O
description: Given a book query (title + author), reads all available memory files and returns only the relevant ones as a combined context string
---

Read the provided memory entries and return only those relevant to the given book query. Return structured JSON only —
no prose, no explanation.

## Input

A JSON object with:

```json
{
  "title": "string",
  "author": "string or null",
  "memory_entries": [
    {
      "key": "string — filename slug, e.g. 'borges_labyrinths'",
      "content": "string — raw text of the memory file"
    }
  ]
}
```

`title` is required. `author` is optional. `memory_entries` is required and may be empty.

## Output

On success, return a single JSON object:

```json
{
  "relevant_keys": ["list of matched memory key strings"],
  "context": "string — concatenated text of all relevant memory entries, separated by '---', ready to inject into a prompt"
}
```

If no entries are relevant, return:

```json
{
  "relevant_keys": [],
  "context": ""
}
```

## Constraints

- Do not invent or fabricate content. Only return memories that exist in the provided `memory_entries`.
- Relevance is defined as: same book, same author, or closely related works or genre context directly useful for
  understanding the queried book.
- Do not include tangentially related entries. When in doubt, exclude.
- Do not return markdown formatting around the JSON — raw JSON only.
