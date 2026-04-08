#!/usr/bin/env python3
"""
Translate subtitle segments from Dutch to English using OpenAI.

Stores translations in SubtitleSegment.translation_en. Idempotent: skips segments
that already have a translation. Similar to tai8bot episode summarization.

By default, only processes episodes that have segments needing translation (incremental).
Use --all to process all episodes, or --max N to limit scope.

Requires: OPENAI_API_KEY in .env

Usage:
    python scripts/translate_segments.py                 # Only episodes with untranslated segments
    python scripts/translate_segments.py --all          # All episodes
    python scripts/translate_segments.py --max 5        # Limit to 5 most recent (within scope)
    python scripts/translate_segments.py --episode-id 427
    python scripts/translate_segments.py --dry-run      # Show what would be translated
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI
from sqlalchemy import or_

from src.models import Episode, SubtitleSegment, _migrate_schema, get_engine, get_session

# Batch size for API calls (balance cost vs latency)
BATCH_SIZE = 12

# Model: gpt-4o-mini is cheap and good for translation
MODEL = "gpt-4o-mini"


def translate_batch(client: OpenAI, texts: list[str]) -> list[str]:
    """
    Translate a batch of Dutch texts to English.
    Returns one translation per input, same order.
    """
    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
    prompt = f"""Translate these Dutch sentences to English. They are from NOS news in easy language.
Output exactly one English translation per line, in the same order. No numbering, no explanations.
Preserve the tone (news, factual). Keep proper nouns (names, places) as-is.

Dutch:
{numbered}

English translations (one per line):"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a translator. Output only the translations, one per line."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    result = response.choices[0].message.content.strip()
    # Parse by number so blank lines in the response don't shift subsequent translations.
    # Build a dict {1: "...", 2: "...", ...} then reconstruct in order.
    by_number: dict[int, str] = {}
    unnumbered: list[str] = []
    for line in result.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line[0].isdigit() and ". " in line:
            raw_num, text = line.split(". ", 1)
            try:
                by_number[int(raw_num)] = text.strip()
                continue
            except ValueError:
                pass
        unnumbered.append(line)

    if by_number:
        # Numbered response: reconstruct in 1-based order, empty string for missing entries
        cleaned = [by_number.get(i + 1, "") for i in range(len(texts))]
    else:
        # Fallback: unnumbered response, pad/truncate to match input length
        cleaned = (unnumbered + [""] * len(texts))[: len(texts)]
    return cleaned


def translate_segments_for_episode(
    session,
    episode: Episode,
    client: OpenAI,
    dry_run: bool = False,
    force: bool = False,
) -> tuple[int, int]:
    """
    Translate segments for one episode. Returns (translated_count, skipped_count).
    """
    segments = (
        session.query(SubtitleSegment)
        .filter(SubtitleSegment.episode_id == episode.id)
        .order_by(SubtitleSegment.start_time)
        .all()
    )
    if force:
        to_translate = segments
    else:
        to_translate = [s for s in segments if not s.translation_en or not s.translation_en.strip()]
    if not to_translate:
        return 0, len(segments)

    translated = 0
    for i in range(0, len(to_translate), BATCH_SIZE):
        batch = to_translate[i : i + BATCH_SIZE]
        texts = [s.text for s in batch]
        if dry_run:
            print(f"  Would translate {len(texts)} segments")
            translated += len(batch)
            continue
        try:
            translations = translate_batch(client, texts)
            for seg, trans in zip(batch, translations):
                if trans:
                    seg.translation_en = trans
                    translated += 1
        except Exception as e:
            print(f"  ⚠ API error: {e}")
            break
    return translated, len(segments) - len(to_translate)


def main():
    parser = argparse.ArgumentParser(description="Translate subtitle segments to English via OpenAI")
    parser.add_argument("--all", action="store_true", help="Process all episodes (re-process even fully translated)")
    parser.add_argument("--force", action="store_true", help="Re-translate segments that already have a translation (use after fixing pipeline bugs)")
    parser.add_argument("--max", type=int, metavar="N", help="Process only N most recent episodes")
    parser.add_argument("--episode-id", type=int, metavar="ID", help="Process only this episode")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be translated")
    parser.add_argument("--db", default=None, help="Database URL (default: DATABASE_URL env var, then SQLite fallback)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set. Add it to .env")
        sys.exit(1)

    engine = get_engine(args.db)
    _migrate_schema(engine)
    session = get_session(engine)

    query = (
        session.query(Episode)
        .filter(Episode.transcript_fetched == True)
        .order_by(Episode.published_at.desc())
    )
    if args.episode_id:
        query = query.filter(Episode.id == args.episode_id)
        episodes = query.all()
        if not episodes:
            print(f"Episode {args.episode_id} not found.")
            sys.exit(1)
    else:
        # Incremental: only episodes with segments needing translation
        if not args.all:
            has_untranslated = (
                session.query(SubtitleSegment.episode_id)
                .filter(
                    or_(
                        SubtitleSegment.translation_en.is_(None),
                        SubtitleSegment.translation_en == "",
                    )
                )
                .distinct()
            )
            query = query.filter(Episode.id.in_(has_untranslated))
        if args.max:
            query = query.limit(args.max)
        episodes = query.all()

    if not episodes:
        print("No episodes need translation." if not args.all else "No episodes with transcripts found.")
        sys.exit(0)

    print("=" * 60)
    print("Dutch News Learner - Translate Segments")
    print("=" * 60)
    mode = "incremental (untranslated segments only)" if not args.all else "all episodes"
    print(f"Episodes: {len(episodes)} ({mode})")
    print(f"Model: {MODEL} | Batch size: {BATCH_SIZE}")
    if args.dry_run:
        print("(Dry run - no changes)")
    print()

    client = OpenAI(api_key=api_key)
    total_translated = 0

    for ep in episodes:
        print(f"[{ep.id}] {ep.title[:50]}...")
        trans, skip = translate_segments_for_episode(session, ep, client, dry_run=args.dry_run, force=args.force)
        total_translated += trans
        if trans or skip:
            print(f"  Translated: {trans} | Already had: {skip}")
        if not args.dry_run and trans:
            session.commit()

    print()
    print(f"Total segments translated: {total_translated}")
    print("Restart the app to see English translations.")


if __name__ == "__main__":
    main()
