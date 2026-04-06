#!/usr/bin/env python3
"""
Enrich vocabulary items that have no translation using LLM (GPT-4o-mini).

Fills VocabularyItem.translation for words where the dictionary has no entry.
Uses each word's POS tag and an example sentence from the episode for context.
Only fills gaps — never overwrites existing dictionary-provided translations.

Requires: OPENAI_API_KEY in .env

Usage:
    python scripts/enrich_vocab_llm.py              # Default: up to 200 missing words
    python scripts/enrich_vocab_llm.py --all         # All missing words
    python scripts/enrich_vocab_llm.py --max 50      # Limit to 50 words
    python scripts/enrich_vocab_llm.py --dry-run     # Preview without changes
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI
from sqlalchemy import func, or_

from src.models import (
    EpisodeVocabulary,
    VocabularyItem,
    _migrate_schema,
    get_engine,
    get_session,
)

BATCH_SIZE = 25
MODEL = "gpt-4o-mini"
MAX_RETRIES = 3
RETRY_DELAY = 2


def _build_prompt(words: list[dict]) -> str:
    """Build the LLM prompt for a batch of words."""
    lines = []
    for i, w in enumerate(words, 1):
        parts = [f'{i}. {w["lemma"]} ({w["pos"]})']
        if w.get("example"):
            parts.append(f'  Example: "{w["example"]}"')
        lines.append("\n".join(parts))

    word_block = "\n".join(lines)
    return f"""You are a Dutch-English dictionary assistant. For each Dutch word below,
provide a concise English definition (max 15 words). Use the POS tag and example
sentence to pick the correct meaning.

Rules:
- For verbs: start with "to " (e.g. "to extinguish")
- For nouns: give the English noun (e.g. "fire, blaze")
- For adjectives/adverbs: give the English equivalent (e.g. "expensive")
- If a word has multiple meanings, pick the one that fits the example sentence
- Output ONLY a JSON array of strings, one definition per word, same order
- No numbering, no explanations, no markdown — just the JSON array

Words:
{word_block}

JSON array of English definitions:"""


def enrich_batch(client: OpenAI, words: list[dict]) -> list[str | None]:
    """
    Call LLM for a batch of words. Returns list of English definitions
    (same length as input; None for any word that failed).
    """
    prompt = _build_prompt(words)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Dutch-English dictionary. Output only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown fences if model wraps in ```json ... ```
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3].strip()

            definitions = json.loads(raw)
            if isinstance(definitions, list) and len(definitions) >= len(words):
                return [d if isinstance(d, str) and d.strip() else None for d in definitions[: len(words)]]
            if isinstance(definitions, list):
                padded = definitions + [None] * (len(words) - len(definitions))
                return [d if isinstance(d, str) and d.strip() else None for d in padded[: len(words)]]

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            if attempt < MAX_RETRIES - 1:
                print(f"    Retry {attempt + 1}/{MAX_RETRIES} (parse error: {e})")
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            print(f"    Failed to parse after {MAX_RETRIES} attempts: {e}")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"    Retry {attempt + 1}/{MAX_RETRIES} (API error: {e})")
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            print(f"    API error after {MAX_RETRIES} attempts: {e}")

    return [None] * len(words)


def get_missing_vocab(session, max_words: int | None = None) -> list[dict]:
    """
    Query vocabulary items with no translation, along with one example sentence.
    Returns list of dicts with keys: id, lemma, pos, example.
    """
    example_subq = (
        session.query(
            EpisodeVocabulary.vocabulary_id,
            func.min(EpisodeVocabulary.example_sentence).label("example"),
        )
        .group_by(EpisodeVocabulary.vocabulary_id)
        .subquery()
    )

    query = (
        session.query(
            VocabularyItem.id,
            VocabularyItem.lemma,
            VocabularyItem.pos,
            example_subq.c.example,
        )
        .outerjoin(example_subq, VocabularyItem.id == example_subq.c.vocabulary_id)
        .filter(
            or_(
                VocabularyItem.translation == None,  # noqa: E711
                VocabularyItem.translation == "",
            )
        )
        .order_by(VocabularyItem.lemma)
    )

    if max_words is not None:
        query = query.limit(max_words)

    rows = query.all()
    return [
        {"id": r[0], "lemma": r[1], "pos": r[2] or "UNKNOWN", "example": r[3] or ""}
        for r in rows
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Enrich vocabulary with LLM-generated English definitions"
    )
    parser.add_argument("--all", action="store_true", help="Process all missing words")
    parser.add_argument(
        "--max", type=int, metavar="N", default=200,
        help="Max words to process (default: 200)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--db", default=None, help="Database URL (default: DATABASE_URL env var, then SQLite fallback)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set. Add it to .env")
        sys.exit(1)

    engine = get_engine(args.db)
    _migrate_schema(engine)
    session = get_session(engine)

    max_words = None if args.all else args.max
    missing = get_missing_vocab(session, max_words=max_words)

    if not missing:
        print("All vocabulary items already have translations. Nothing to do.")
        session.close()
        return

    total_in_db = session.query(VocabularyItem).count()
    total_missing = session.query(VocabularyItem).filter(
        or_(VocabularyItem.translation == None, VocabularyItem.translation == "")  # noqa: E711
    ).count()

    print("=" * 60)
    print("Dutch News Learner — LLM Vocabulary Enrichment")
    print("=" * 60)
    print(f"Total vocabulary items: {total_in_db}")
    print(f"Missing translations:  {total_missing}")
    print(f"Processing this run:   {len(missing)}")
    print(f"Model: {MODEL} | Batch size: {BATCH_SIZE}")
    if args.dry_run:
        print("(Dry run — no changes will be saved)")
    print()

    client = OpenAI(api_key=api_key)
    enriched = 0
    failed = 0

    for i in range(0, len(missing), BATCH_SIZE):
        batch = missing[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(missing) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} words)...")

        if args.dry_run:
            for w in batch:
                ex = f' — "{w["example"][:50]}..."' if w["example"] else ""
                print(f"    {w['lemma']} ({w['pos']}){ex}")
            enriched += len(batch)
            continue

        definitions = enrich_batch(client, batch)

        for word, defn in zip(batch, definitions):
            if defn and defn.strip():
                trimmed = defn.strip()[:200]
                vocab_item = session.get(VocabularyItem, word["id"])
                if vocab_item:
                    vocab_item.translation = trimmed
                    enriched += 1
            else:
                failed += 1
                print(f"    No definition returned for: {word['lemma']}")

        session.commit()
        # Brief pause between batches to respect rate limits
        if i + BATCH_SIZE < len(missing):
            time.sleep(0.5)

    session.close()

    print()
    print("=" * 60)
    print("ENRICHMENT SUMMARY")
    print("=" * 60)
    print(f"Words processed: {enriched + failed}")
    print(f"Enriched:        {enriched}")
    print(f"Failed:          {failed}")
    if args.dry_run:
        print("(Dry run — no changes saved)")
    else:
        print("Restart the app to see updated definitions.")


if __name__ == "__main__":
    main()
