# Importing vocabulary export into Anki

The API can return an **Anki-style CSV** for simple flashcard import (no `.apkg` required).

## Export

Call (with your usual auth: Bearer JWT or `X-Session-Token`):

```http
GET /api/vocabulary/export?format=csv&template=anki
```

Optional filters (same as the default export):

- `status=all` **or** comma-separated subset, e.g. `status=new,learning`
- `has_note=true|false` — only rows with / without a learner note
- `episode_from=YYYY-MM-DD` and/or `episode_to=YYYY-MM-DD` — only words that appear in an episode published on those calendar days (UTC). Example: today’s video only → set both to today’s date.

## Columns

| Column | Contents |
|--------|-----------|
| **Front** | Word (dictionary headword / lemma) |
| **Back** | NL meaning, EN meaning, episode example, and your note (when present), separated by newlines |
| **Tags** | `dutch_news_learner` |

## Anki desktop

1. **File → Import** and choose the downloaded CSV.
2. Set **Fields separated by**: Comma (or let Anki auto-detect).
3. Map **Front** → first field, **Back** → second, **Tags** → tags (if your note type supports it).
4. Choose a note type (e.g. *Basic*) and deck, then import.

You can duplicate the deck or edit the **Back** template later to hide/show lines.

## JSON

Same shape as JSON rows with keys `Front`, `Back`, `Tags`:

```http
GET /api/vocabulary/export?format=json&template=anki
```
