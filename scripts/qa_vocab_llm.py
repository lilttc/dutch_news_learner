#!/usr/bin/env python3
"""
LLM-as-judge vocabulary QA: fix POS errors, wrong translations, flag idioms.

For each vocabulary item, sends the lemma + POS + translation + example sentence
to GPT-4o-mini and asks it to verify:
  1. Is the POS tag correct for this context?
  2. Is the translation correct for this context?
  3. Is this word part of a multi-word expression or idiom?

Corrections are stored in qa_pos, qa_translation, qa_note on VocabularyItem.
qa_checked is set to True once a word has been reviewed (even if nothing was wrong).
The display layer prefers qa_pos / qa_translation over the originals when present.

By default, only processes words not yet QA'd. Use --all to re-check everything.

Requires: OPENAI_API_KEY in .env

Usage:
    python scripts/qa_vocab_llm.py              # Only un-checked words (up to --max)
    python scripts/qa_vocab_llm.py --all        # Re-check all words
    python scripts/qa_vocab_llm.py --max 100    # Limit to 100 words
    python scripts/qa_vocab_llm.py --episode-id 536   # Only words from one episode
    python scripts/qa_vocab_llm.py --dry-run    # Show what would be checked
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
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

BATCH_SIZE = 20
DEFAULT_MODEL = "gpt-4o-mini"
MAX_RETRIES = 3
RETRY_DELAY = 2

EVAL_LOG = Path(__file__).resolve().parent.parent / "logs" / "qa_vocab_eval.jsonl"


def _log_eval(word: dict, qa_pos: str | None, qa_translation: str | None, qa_note: str | None) -> None:
    """Append one JSONL line per reviewed word to logs/qa_vocab_eval.jsonl.

    Every word gets a line — corrections and clean passes alike — so you can
    measure correction rate and audit model decisions over time.
    """
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "lemma": word["lemma"],
        "original_pos": word["pos"],
        "original_translation": word["translation"],
        "original_example": word["example"],
        "qa_pos": qa_pos,               # None = model agreed with original
        "qa_translation": qa_translation,
        "qa_note": qa_note,
    }
    EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVAL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _build_prompt(words: list[dict]) -> str:
    lines = []
    for i, w in enumerate(words, 1):
        lines.append(
            f'{i}. "{w["lemma"]}" — POS: {w["pos"]}, translation: "{w["translation"]}"'
        )
        if w.get("example"):
            lines.append(f'   Example: "{w["example"]}"')

    word_block = "\n".join(lines)
    return f"""You are a Dutch linguistics expert reviewing vocabulary entries for a language-learning app.

For each word below, check:
1. Is the POS tag correct given the example sentence? (NOUN / VERB / ADJ / ADV)
2. Is the translation correct for this specific context?
3. Is this word part of a fixed multi-word expression or idiom (e.g. "ten slotte", "zorgen voor")?

Output a JSON array with one object per word, in the same order. Use null when the original is correct.
Schema for each object:
  "corrected_pos":         string or null  (e.g. "NOUN" — only if the original POS is wrong)
  "corrected_translation": string or null  (e.g. "votes" — only if the original translation is wrong or missing)
  "mwe_note":              string or null  (e.g. "part of 'ten slotte' (finally)" — only if MWE/idiom)

Output ONLY the JSON array. No markdown, no explanations.

Words:
{word_block}

JSON array:"""


def _qa_batch(client: OpenAI, words: list[dict], model: str) -> list[dict]:
    """
    Run QA on a batch of words. Returns one result dict per word.
    On failure returns a list of empty dicts (no corrections applied).
    """
    prompt = _build_prompt(words)
    empty = [{"corrected_pos": None, "corrected_translation": None, "mwe_note": None}] * len(words)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Dutch linguistics expert. Output only valid JSON.",
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

            results = json.loads(raw)
            if not isinstance(results, list):
                raise ValueError(f"Expected list, got {type(results)}")

            # Pad to match input length in case the model returned fewer items
            results = (results + empty)[: len(words)]
            return results

        except (json.JSONDecodeError, ValueError) as e:
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

    return empty


def _get_words_to_check(session, max_words: int | None, all_words: bool, episode_id: int | None) -> list[dict]:
    """
    Query vocabulary items to QA, with one example sentence per word.
    Returns list of dicts: id, lemma, pos, translation, example.
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
            VocabularyItem.translation,
            example_subq.c.example,
        )
        .outerjoin(example_subq, VocabularyItem.id == example_subq.c.vocabulary_id)
    )

    if episode_id is not None:
        query = query.join(
            EpisodeVocabulary,
            EpisodeVocabulary.vocabulary_id == VocabularyItem.id,
        ).filter(EpisodeVocabulary.episode_id == episode_id)

    if not all_words:
        query = query.filter(
            or_(VocabularyItem.qa_checked == False, VocabularyItem.qa_checked == None)  # noqa: E711,E712
        )

    query = query.order_by(VocabularyItem.lemma)

    if max_words is not None:
        query = query.limit(max_words)

    rows = query.all()
    return [
        {
            "id": r[0],
            "lemma": r[1],
            "pos": r[2] or "UNKNOWN",
            "translation": r[3] or "(none)",
            "example": r[4] or "",
        }
        for r in rows
    ]


def main():
    parser = argparse.ArgumentParser(
        description="LLM-as-judge QA: fix POS errors, wrong translations, flag idioms"
    )
    parser.add_argument("--all", action="store_true", help="Re-check all words (not just un-checked)")
    parser.add_argument(
        "--max", type=int, metavar="N", default=200,
        help="Max words to process in one run (default: 200)",
    )
    parser.add_argument("--episode-id", type=int, metavar="ID", help="Only check words from this episode")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenAI model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be checked, no changes saved")
    parser.add_argument("--db", default=None, help="Database URL (default: DATABASE_URL env var)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set. Add it to .env")
        sys.exit(1)

    engine = get_engine(args.db)
    _migrate_schema(engine)
    session = get_session(engine)

    max_words = None if args.all else args.max
    words = _get_words_to_check(session, max_words=max_words, all_words=args.all, episode_id=args.episode_id)

    if not words:
        print("No vocabulary items to QA. All words already checked (use --all to re-check).")
        session.close()
        return

    total_unchecked = session.query(VocabularyItem).filter(
        or_(VocabularyItem.qa_checked == False, VocabularyItem.qa_checked == None)  # noqa: E711,E712
    ).count()

    print("=" * 60)
    print("Dutch News Learner — Vocab QA Agent")
    print("=" * 60)
    print(f"Total words not yet QA'd: {total_unchecked}")
    print(f"Processing this run:      {len(words)}")
    print(f"Model: {args.model} | Batch size: {BATCH_SIZE}")
    if args.dry_run:
        print("(Dry run — no changes will be saved)")
    print()

    client = OpenAI(api_key=api_key)

    corrected_pos = 0
    corrected_translation = 0
    flagged_mwe = 0
    checked = 0

    for i in range(0, len(words), BATCH_SIZE):
        batch = words[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(words) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} words)...")

        if args.dry_run:
            for w in batch:
                ex = f' — "{w["example"][:60]}"' if w["example"] else ""
                print(f"    {w['lemma']} ({w['pos']}) = {w['translation']}{ex}")
            checked += len(batch)
            continue

        results = _qa_batch(client, batch, model=args.model)

        for word, result in zip(batch, results):
            vocab_item = session.query(VocabularyItem).get(word["id"])
            if not vocab_item:
                continue

            new_pos = result.get("corrected_pos")
            new_translation = result.get("corrected_translation")
            note = result.get("mwe_note")

            # Only store and count when the value genuinely differs from the original.
            # The model sometimes returns the original instead of null — ignore those.
            if new_pos and isinstance(new_pos, str):
                new_pos = new_pos.strip().upper()
                if new_pos != (word["pos"] or "").upper():
                    vocab_item.qa_pos = new_pos
                    corrected_pos += 1
                    print(f"    POS fix: {word['lemma']} {word['pos']} → {new_pos}")

            if new_translation and isinstance(new_translation, str):
                new_translation = new_translation.strip()
                if new_translation.lower() != (word["translation"] or "").lower():
                    vocab_item.qa_translation = new_translation
                    corrected_translation += 1
                    print(f"    Translation fix: {word['lemma']} \"{word['translation']}\" → \"{new_translation}\"")

            if note and isinstance(note, str):
                vocab_item.qa_note = note.strip()
                flagged_mwe += 1
                print(f"    MWE/idiom: {word['lemma']} — {note.strip()}")

            vocab_item.qa_checked = True
            checked += 1

            _log_eval(
                word,
                qa_pos=vocab_item.qa_pos,
                qa_translation=vocab_item.qa_translation,
                qa_note=vocab_item.qa_note,
            )

        session.commit()

        if i + BATCH_SIZE < len(words):
            time.sleep(0.5)

    session.close()

    print()
    print("=" * 60)
    print("QA SUMMARY")
    print("=" * 60)
    print(f"Words reviewed:          {checked}")
    print(f"POS corrections:         {corrected_pos}")
    print(f"Translation corrections: {corrected_translation}")
    print(f"MWE / idioms flagged:    {flagged_mwe}")
    if args.dry_run:
        print("(Dry run — no changes saved)")
    else:
        print("Restart the app to see corrected definitions.")


if __name__ == "__main__":
    main()
