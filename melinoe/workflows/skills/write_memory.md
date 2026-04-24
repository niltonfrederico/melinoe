______________________________________________________________________

## name: write_memory type: skill model: GITHUB_COPILOT_GPT4O description: Given a completed book report (cover analysis + bibliographic metadata), generates a concise, structured memory entry suitable for future retrieval.

Generate a memory entry from the provided book report. Return structured JSON only — no prose, no explanation.

## Input

A JSON object with:

```json
{
  "cover_analysis": {
    "title": "string or null",
    "author": "string or null",
    "genre": "string or null",
    "mood": "string or null",
    "confidence": "high | medium | low"
  },
  "bibliographic_metadata": {
    "title": "string",
    "author": "string",
    "isbn_13": "string or null",
    "isbn_10": "string or null",
    "publication_year": "integer or null",
    "publisher": "string or null",
    "synopsis": "string or null",
    "genres": ["list of strings"]
  },
  "report_confidence": "high | medium | low"
}
```

All top-level fields are required. Individual nested fields may be null.

## Output

Return a single JSON object:

```json
{
  "memory_key": "string — slug formatted as '{author_slug}_{title_slug}', lowercase, hyphens for spaces, no special characters",
  "memory_content": "string — markdown-formatted memory entry under 300 words"
}
```

The `memory_content` value must follow this structure:

```
# {Title}

**Author:** {author}
**ISBN:** {isbn_13 or isbn_10 or 'N/A'}
**Year:** {publication_year or 'N/A'}
**Publisher:** {publisher or 'N/A'}
**Genres:** {comma-separated genre tags}
**Confidence:** {report_confidence}

## Synopsis

{one short paragraph synopsis snippet, max 100 words}
```

## Constraints

- Be factual and concise. Do not add commentary, opinions, or filler.
- Derive all content strictly from the provided report fields. Do not fabricate details.
- Keep `memory_content` under 300 words.
- Include enough structured detail (title, author, ISBN, year, genres) to support future relevance matching by `load_relevant_memory`.
- Write all `memory_content` text in Brazilian Portuguese (pt-BR). Labels (Author, ISBN, etc.) may remain in English for machine readability, but all narrative text (synopsis) must be in pt-BR.
- Do not return markdown formatting around the JSON — raw JSON only.
