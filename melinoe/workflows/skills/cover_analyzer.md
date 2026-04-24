---
name: cover_analyzer
type: skill
model: GEMINI_FLASH
description: Analyzes a book cover image and extracts structured visual and contextual data as JSON.
---

Analyze the provided book cover image and extract all identifiable information. Return structured JSON only — no prose, no explanation.

## Input

A book cover image provided as either:
- A publicly accessible URL string
- A base64-encoded image string

## Output

Return a single JSON object with the following fields. Use `null` for any field that cannot be determined from the image.

```json
{
  "title": "string or null",
  "subtitle": "string or null",
  "author": "string or null",
  "publisher": "string or null",
  "series": "string or null",
  "genre": "string or null",
  "color_palette": {
    "dominant": ["hex string", ...],
    "accent": ["hex string", ...],
    "background": "hex string or null"
  },
  "design_style": "string — e.g. minimalist, illustrative, photographic, typographic, collage",
  "mood": "string — e.g. melancholic, tense, whimsical, clinical, romantic",
  "typography": {
    "title_typeface_style": "string — e.g. serif, sans-serif, display, handwritten",
    "hierarchy_notes": "string or null"
  },
  "target_audience": "string — e.g. adult literary fiction, young adult, middle grade, academic",
  "visual_elements": ["list of notable imagery or motifs visible on the cover"],
  "confidence": "high | medium | low"
}
```

## Constraints

- Do not infer information not visible in the image.
- If the image is unclear, blurry, or not a book cover, set `"confidence": "low"` and populate only the fields you can determine.
- Do not return markdown formatting around the JSON — raw JSON only.
