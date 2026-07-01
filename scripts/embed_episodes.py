#!/usr/bin/env python3
"""
Embed episodes for semantic search (RAG).

Computes a text-embedding-3-small embedding from each episode's title +
description + first 500 chars of transcript, stored in Episode.embedding
(pgvector column, Postgres only).

By default, only processes episodes that don't have an embedding yet
(incremental). Use --all to re-embed everything, or --max N to limit scope.

Requires: OPENAI_API_KEY in .env. Requires a Postgres database with pgvector -
exits cleanly with a message if DATABASE_URL is unset or points at SQLite,
since vector similarity can't run there.

Usage:
    python scripts/embed_episodes.py                # Only un-embedded episodes
    python scripts/embed_episodes.py --all          # Re-embed all episodes
    python scripts/embed_episodes.py --max 5        # Limit to 5 most recent
    python scripts/embed_episodes.py --episode-id 427
    python scripts/embed_episodes.py --dry-run      # Show what would be embedded
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.models import Episode, SubtitleSegment, _migrate_schema, get_engine, get_session
from src.rag import EMBEDDING_MODEL, embed_text, get_client, is_semantic_search_available


def build_input_text(session, episode: Episode, max_transcript_chars: int = 500) -> str:
    """title + description + first `max_transcript_chars` of the transcript."""
    segments = (
        session.query(SubtitleSegment)
        .filter(SubtitleSegment.episode_id == episode.id)
        .order_by(SubtitleSegment.start_time)
        .all()
    )
    transcript = " ".join(s.text for s in segments)[:max_transcript_chars]
    parts = [episode.title or "", episode.description or "", transcript]
    return "\n".join(p for p in parts if p)


def main():
    parser = argparse.ArgumentParser(description="Embed episodes for semantic search via OpenAI")
    parser.add_argument("--all", action="store_true", help="Re-embed all episodes")
    parser.add_argument("--max", type=int, metavar="N", help="Process only N most recent episodes")
    parser.add_argument("--episode-id", type=int, metavar="ID", help="Process only this episode")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be embedded")
    parser.add_argument(
        "--db",
        default=None,
        help="Database URL (default: DATABASE_URL env var, then SQLite fallback)",
    )
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set. Add it to .env")
        sys.exit(1)

    engine = get_engine(args.db)
    _migrate_schema(engine)
    session = get_session(engine)

    if not is_semantic_search_available(session):
        print(
            "Semantic search requires Postgres + pgvector; DATABASE_URL is unset or "
            "points at SQLite. Skipping embedding step."
        )
        sys.exit(0)

    query = session.query(Episode).order_by(Episode.published_at.desc())
    if args.episode_id:
        query = query.filter(Episode.id == args.episode_id)
        episodes = query.all()
        if not episodes:
            print(f"Episode {args.episode_id} not found.")
            sys.exit(1)
    else:
        if not args.all:
            query = query.filter(Episode.embedding.is_(None))
        if args.max:
            query = query.limit(args.max)
        episodes = query.all()

    if not episodes:
        print("No episodes need embedding." if not args.all else "No episodes found.")
        sys.exit(0)

    print("=" * 60)
    print("Dutch News Learner - Embed Episodes")
    print("=" * 60)
    mode = "incremental (un-embedded only)" if not args.all else "all episodes"
    print(f"Episodes: {len(episodes)} ({mode})")
    print(f"Model: {EMBEDDING_MODEL}")
    if args.dry_run:
        print("(Dry run - no changes)")
    print()

    client = get_client()
    total_embedded = 0

    for ep in episodes:
        print(f"[{ep.id}] {ep.title[:50]}...")
        if args.dry_run:
            print("  Would embed")
            continue
        text = build_input_text(session, ep)
        if not text.strip():
            print("  Skipped: no title/description/transcript text")
            continue
        try:
            ep.embedding = embed_text(client, text)
            session.commit()
            total_embedded += 1
        except Exception as e:
            print(f"  ⚠ API error: {e}")

    print()
    print(f"Total episodes embedded: {total_embedded}")


if __name__ == "__main__":
    main()
