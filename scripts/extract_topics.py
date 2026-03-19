#!/usr/bin/env python3
"""
Extract 3 topic keywords per episode for Related reading links.

Uses OpenAI to extract topics from title + description (or first transcript lines).
Stores in Episode.topics as pipe-separated: "topic1|topic2|topic3".

By default, only processes episodes that have transcripts but no topics yet (incremental).
Use --all to process all episodes, or --max N to limit scope.

Requires: OPENAI_API_KEY in .env

Usage:
    python scripts/extract_topics.py                 # Only episodes missing topics
    python scripts/extract_topics.py --all          # All episodes
    python scripts/extract_topics.py --max 5       # Limit to 5 most recent (within scope)
    python scripts/extract_topics.py --episode-id 427
    python scripts/extract_topics.py --dry-run     # Show what would be extracted
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI

from src.models import Episode, SubtitleSegment, _migrate_schema, get_engine, get_session

MODEL = "gpt-4o-mini"


def extract_topics(client: OpenAI, title: str, description: str, transcript_preview: str) -> list[str]:
    """
    Use LLM to extract 3 topic keywords for related news search.
    Returns list of 3 strings (Dutch keywords suitable for NOS search).
    """
    context = f"""Title: {title}
Description: {description[:500] if description else "(none)"}
First lines of transcript:
{transcript_preview[:600] if transcript_preview else "(none)"}"""

    prompt = f"""This is a NOS Journaal in Makkelijke Taal episode (Dutch news in easy language).
Extract exactly 3 topic keywords for related news search. Use short Dutch search terms (1-2 words each).
Examples: olie, fatbikes, Flevoland, klimaat, politie, Oekraïne.

Output exactly 3 keywords, one per line. No numbering, no explanations.

{context}

Topic keywords (one per line):"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You extract news topic keywords. Output only 3 keywords, one per line."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    result = response.choices[0].message.content.strip()
    lines = [line.strip() for line in result.split("\n") if line.strip()]
    # Remove leading numbers if model added them
    cleaned = []
    for line in lines[:3]:
        if line and line[0].isdigit() and ". " in line:
            line = line.split(". ", 1)[1]
        cleaned.append(line.strip())
    return cleaned[:3]


def extract_topics_for_episode(session, episode: Episode, client: OpenAI, dry_run: bool = False) -> str | None:
    """
    Extract topics for one episode. Returns pipe-separated string or None.
    """
    segments = (
        session.query(SubtitleSegment)
        .filter(SubtitleSegment.episode_id == episode.id)
        .order_by(SubtitleSegment.start_time)
        .limit(15)
        .all()
    )
    transcript_preview = "\n".join(s.text for s in segments) if segments else ""

    if dry_run:
        print(f"  Would extract from: title + desc + {len(segments)} transcript lines")
        return None

    if not (episode.title or transcript_preview):
        return None

    try:
        topics = extract_topics(
            client,
            episode.title or "",
            episode.description or "",
            transcript_preview,
        )
        return "|".join(topics) if topics else None
    except Exception as e:
        print(f"  ⚠ API error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Extract topic keywords for Related reading")
    parser.add_argument("--all", action="store_true", help="Process all episodes (re-extract even those with topics)")
    parser.add_argument("--max", type=int, metavar="N", help="Process only N most recent episodes")
    parser.add_argument("--episode-id", type=int, metavar="ID", help="Process only this episode")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be extracted")
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
        # Incremental: only episodes missing topics
        if not args.all:
            query = query.filter(
                (Episode.topics.is_(None)) | (Episode.topics == "")
            )
        if args.max:
            query = query.limit(args.max)
        episodes = query.all()

    if not episodes:
        print("No episodes need topic extraction." if not args.all else "No episodes with transcripts found.")
        sys.exit(0)

    print("=" * 60)
    print("Dutch News Learner — Extract Topics")
    print("=" * 60)
    mode = "incremental (missing topics only)" if not args.all else "all episodes"
    print(f"Episodes: {len(episodes)} ({mode})")
    print(f"Model: {MODEL}")
    if args.dry_run:
        print("(Dry run — no changes)")
    print()

    client = OpenAI(api_key=api_key)

    for ep in episodes:
        print(f"[{ep.id}] {ep.title[:50]}...")
        topics_str = extract_topics_for_episode(session, ep, client, dry_run=args.dry_run)
        if topics_str:
            ep.topics = topics_str
            print(f"  Topics: {topics_str}")
            if not args.dry_run:
                session.commit()
        elif not args.dry_run and ep.topics:
            print(f"  (kept existing: {ep.topics})")

    print()
    print("Restart the app to see Related reading.")


if __name__ == "__main__":
    main()
