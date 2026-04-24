______________________________________________________________________

## name: book_lookup type: skill model: GEMINI_FLASH description: Given a book title and author, retrieves bibliographic metadata from Open Library or Google Books and returns it as structured JSON.

Look up bibliographic metadata for the given book using Open Library (openlibrary.org) or Google Books (books.googleapis.com). Return structured JSON only — no prose, no explanation.

## Input

A JSON object with:

```json
{
  "title": "string",
  "author": "string"
}
```

Both fields are required. If either is missing or empty, return an error JSON (see Output).

## Output

On success, return a single JSON object:

```json
{
  "title": "string",
  "author": "string",
  "isbn_13": "string or null",
  "isbn_10": "string or null",
  "publication_year": "integer or null",
  "publisher": "string or null",
  "page_count": "integer or null",
  "language": "string or null",
  "synopsis": "string or null",
  "genres": ["list of strings"],
  "ratings": {
    "goodreads_average": "float or null",
    "goodreads_count": "integer or null",
    "google_books_average": "float or null",
    "google_books_count": "integer or null"
  },
  "awards": ["list of strings — award name and year if known"],
  "source": "open_library | google_books | both | none",
  "confidence": "high | medium | low"
}
```

On failure (missing input, no results found, or lookup error):

```json
{
  "error": "string describing the failure",
  "title": "string or null",
  "author": "string or null"
}
```

## Constraints

- Prefer Open Library for ISBNs and publication data; prefer Google Books for ratings and synopsis.
- Do not fabricate metadata. If a field is unavailable from the source, use `null`.
- If multiple editions exist, return the earliest original publication year and note the most recent publisher.
- Do not return markdown formatting around the JSON — raw JSON only.
