#!/usr/bin/env python3
"""
Inspect the Dutch News Learner database.

Usage:
    python scripts/query_db.py [--episodes] [--vocab] [--episode-id N] [--top N]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import func, or_

from src.models import (
    Episode,
    EpisodeVocabulary,
    SubtitleSegment,
    VocabularyItem,
    get_engine,
    get_session,
)


def show_episodes(session, limit=10):
    """List episodes with subtitle and vocabulary counts."""
    episodes = session.query(Episode).order_by(Episode.published_at.desc()).limit(limit).all()
    print("\n📺 EPISODES")
    print("-" * 70)
    for ep in episodes:
        vocab_count = session.query(EpisodeVocabulary).filter_by(episode_id=ep.id).count()
        seg_count = len(ep.subtitle_segments)
        pub = ep.published_at.strftime("%Y-%m-%d") if ep.published_at else "?"
        print(f"  {ep.id} | {pub} | {ep.video_id}")
        print(f"      {ep.title[:55]}...")
        print(f"      Segments: {seg_count} | Vocabulary: {vocab_count}")
        print()


def show_vocabulary(session, limit=20, episode_id=None):
    """List vocabulary items, optionally filtered by episode."""
    query = session.query(VocabularyItem).order_by(VocabularyItem.lemma)
    if episode_id:
        subq = session.query(EpisodeVocabulary.vocabulary_id).filter_by(episode_id=episode_id)
        query = query.filter(VocabularyItem.id.in_(subq))
    items = query.limit(limit).all()
    print(f"\n📚 VOCABULARY (top {limit})" + (f" for episode {episode_id}" if episode_id else ""))
    print("-" * 70)
    for v in items:
        ep_count = session.query(EpisodeVocabulary).filter_by(vocabulary_id=v.id).count()
        total = session.query(EpisodeVocabulary.occurrence_count).filter_by(vocabulary_id=v.id)
        total_count = sum(r[0] for r in total)
        trans = f" → {v.translation}" if v.translation else ""
        print(f"  {v.lemma} ({v.pos}){trans}")
        print(f"      In {ep_count} episodes, {total_count} occurrences")
    print()


def show_translation_status(session):
    """Show how many episodes need translation (have segments without translation_en)."""
    # Episodes with transcripts
    total_with_transcript = (
        session.query(Episode).filter(Episode.transcript_fetched == True).count()
    )

    # Episodes with at least one segment missing translation
    needs_translation = (
        session.query(SubtitleSegment.episode_id)
        .filter(
            or_(
                SubtitleSegment.translation_en.is_(None),
                SubtitleSegment.translation_en == "",
            )
        )
        .distinct()
    )
    episode_ids_needing = {r[0] for r in needs_translation}

    # Segments: total vs translated
    total_segments = session.query(SubtitleSegment).count()
    translated_segments = (
        session.query(SubtitleSegment)
        .filter(
            SubtitleSegment.translation_en.isnot(None),
            SubtitleSegment.translation_en != "",
        )
        .count()
    )

    print("\n📝 TRANSLATION STATUS")
    print("-" * 70)
    print(f"  Episodes with transcripts:     {total_with_transcript}")
    print(f"  Episodes needing translation: {len(episode_ids_needing)}")
    print(f"  Episodes fully translated:     {total_with_transcript - len(episode_ids_needing)}")
    print()
    print(f"  Total segments:                {total_segments}")
    print(f"  Segments translated:           {translated_segments}")
    print(f"  Segments missing translation:  {total_segments - translated_segments}")
    print()


def show_recurring(session, min_episodes=2, limit=20):
    """Show words that appear in multiple episodes (recurring vocabulary)."""

    recurring = (
        session.query(
            VocabularyItem.lemma,
            VocabularyItem.pos,
            func.count(EpisodeVocabulary.episode_id).label("ep_count"),
        )
        .join(EpisodeVocabulary)
        .group_by(VocabularyItem.id)
        .having(func.count(EpisodeVocabulary.episode_id) >= min_episodes)
        .order_by(func.count(EpisodeVocabulary.episode_id).desc())
        .limit(limit)
        .all()
    )
    print(f"\n🔄 RECURRING VOCABULARY (in ≥{min_episodes} episodes)")
    print("-" * 70)
    for lemma, pos, ep_count in recurring:
        print(f"  {lemma} ({pos}) - in {ep_count} episodes")
    print()


def main():
    parser = argparse.ArgumentParser(description="Inspect Dutch News Learner database")
    parser.add_argument("--episodes", action="store_true", help="List episodes")
    parser.add_argument("--vocab", action="store_true", help="List vocabulary")
    parser.add_argument("--recurring", action="store_true", help="Show recurring words")
    parser.add_argument(
        "--translation-status",
        action="store_true",
        help="Show translation status (episodes/segments needing translation)",
    )
    parser.add_argument("--episode-id", type=int, help="Filter vocabulary by episode ID")
    parser.add_argument("--top", type=int, default=20, help="Limit rows (default: 20)")
    parser.add_argument(
        "--db",
        default=None,
        help="Database URL (default: DATABASE_URL env var, then SQLite fallback)",
    )

    args = parser.parse_args()

    engine = get_engine(args.db)
    session = get_session(engine)

    # Default: show all
    if not any([args.episodes, args.vocab, args.recurring, args.translation_status]):
        show_episodes(session, limit=args.top)
        show_recurring(session, limit=args.top)
        show_vocabulary(session, limit=args.top, episode_id=args.episode_id)
    else:
        if args.translation_status:
            show_translation_status(session)
        if args.episodes:
            show_episodes(session, limit=args.top)
        if args.recurring:
            show_recurring(session, limit=args.top)
        if args.vocab:
            show_vocabulary(session, limit=args.top, episode_id=args.episode_id)

    session.close()


if __name__ == "__main__":
    main()
