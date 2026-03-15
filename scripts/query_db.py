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

from src.models import (
    Episode,
    EpisodeVocabulary,
    VocabularyItem,
    get_engine,
    get_session,
)


def show_episodes(session, limit=10):
    """List episodes with subtitle and vocabulary counts."""
    episodes = (
        session.query(Episode)
        .order_by(Episode.published_at.desc())
        .limit(limit)
        .all()
    )
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
        subq = (
            session.query(EpisodeVocabulary.vocabulary_id)
            .filter_by(episode_id=episode_id)
        )
        query = query.filter(VocabularyItem.id.in_(subq))
    items = query.limit(limit).all()
    print(f"\n📚 VOCABULARY (top {limit})" + (f" for episode {episode_id}" if episode_id else ""))
    print("-" * 70)
    for v in items:
        ep_count = session.query(EpisodeVocabulary).filter_by(vocabulary_id=v.id).count()
        total = (
            session.query(EpisodeVocabulary.occurrence_count)
            .filter_by(vocabulary_id=v.id)
        )
        total_count = sum(r[0] for r in total)
        trans = f" → {v.translation}" if v.translation else ""
        print(f"  {v.lemma} ({v.pos}){trans}")
        print(f"      In {ep_count} episodes, {total_count} occurrences")
    print()


def show_recurring(session, min_episodes=2, limit=20):
    """Show words that appear in multiple episodes (recurring vocabulary)."""
    from sqlalchemy import func

    recurring = (
        session.query(VocabularyItem.lemma, VocabularyItem.pos, func.count(EpisodeVocabulary.episode_id).label("ep_count"))
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
        print(f"  {lemma} ({pos}) — in {ep_count} episodes")
    print()


def main():
    parser = argparse.ArgumentParser(description="Inspect Dutch News Learner database")
    parser.add_argument("--episodes", action="store_true", help="List episodes")
    parser.add_argument("--vocab", action="store_true", help="List vocabulary")
    parser.add_argument("--recurring", action="store_true", help="Show recurring words")
    parser.add_argument("--episode-id", type=int, help="Filter vocabulary by episode ID")
    parser.add_argument("--top", type=int, default=20, help="Limit rows (default: 20)")
    parser.add_argument("--db", default="sqlite:///data/dutch_news.db", help="Database URL")

    args = parser.parse_args()

    engine = get_engine(args.db)
    session = get_session(engine)

    # Default: show all
    if not any([args.episodes, args.vocab, args.recurring]):
        show_episodes(session, limit=args.top)
        show_recurring(session, limit=args.top)
        show_vocabulary(session, limit=args.top, episode_id=args.episode_id)
    else:
        if args.episodes:
            show_episodes(session, limit=args.top)
        if args.recurring:
            show_recurring(session, limit=args.top)
        if args.vocab:
            show_vocabulary(session, limit=args.top, episode_id=args.episode_id)

    session.close()


if __name__ == "__main__":
    main()
