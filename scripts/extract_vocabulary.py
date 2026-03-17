#!/usr/bin/env python3
"""
Extract vocabulary from ingested episodes using spaCy NLP.

Processes subtitle segments for each episode: tokenizes, lemmatizes, filters by POS
(NOUN, VERB, ADJ, ADV), and stores vocabulary in VocabularyItem and EpisodeVocabulary tables.

Usage:
    python scripts/extract_vocabulary.py [--episode-id ID] [--all] [--init-db]

Examples:
    python scripts/extract_vocabulary.py --all          # Process all episodes
    python scripts/extract_vocabulary.py --max 3         # Process latest 3 episodes
"""

import argparse
import os
import sys
from datetime import datetime
from typing import Optional, Tuple

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.dictionary import get_lookup
from src.models import (
    Base,
    Episode,
    EpisodeVocabulary,
    VocabularyItem,
    _migrate_schema,
    get_engine,
    get_session,
    init_db,
)
from src.processing import VocabularyExtractor


def extract_vocabulary_for_episode(
    session,
    episode: Episode,
    extractor: VocabularyExtractor,
    replace_existing: bool = True,
) -> Tuple[int, int]:
    """
    Extract vocabulary from one episode and store in database.

    Args:
        session: SQLAlchemy session.
        episode: Episode with subtitle_segments loaded.
        extractor: VocabularyExtractor instance.
        replace_existing: If True, delete existing EpisodeVocabulary for this episode first.

    Returns:
        Tuple of (vocabulary_items_created, episode_vocabulary_rows_created).
    """
    segments = [
        {"text": seg.text, "start": seg.start_time}
        for seg in episode.subtitle_segments
    ]

    if not segments:
        return 0, 0

    vocab_dict = extractor.extract_from_segments(segments)

    if replace_existing:
        session.query(EpisodeVocabulary).filter_by(episode_id=episode.id).delete()

    items_created = 0
    rows_created = 0

    for lemma, data in vocab_dict.items():
        # Get or create VocabularyItem
        vocab_item = session.query(VocabularyItem).filter_by(lemma=lemma).first()
        if vocab_item is None:
            vocab_item = VocabularyItem(lemma=lemma, pos=data["pos"])
            session.add(vocab_item)
            session.flush()
            items_created += 1

        # Create EpisodeVocabulary link
        surface_forms_str = (
            "|".join(data.get("surface_forms", []))
            if data.get("surface_forms")
            else None
        )
        ep_vocab = EpisodeVocabulary(
            episode_id=episode.id,
            vocabulary_id=vocab_item.id,
            occurrence_count=data["count"],
            example_sentence=data["example_sentence"] or None,
            example_timestamp=data["example_timestamp"],
            surface_forms=surface_forms_str,
        )
        session.add(ep_vocab)
        rows_created += 1

    return items_created, rows_created


def run_extraction(
    max_episodes: Optional[int] = None,
    episode_id: Optional[int] = None,
    replace_existing: bool = True,
    db_path: str = "sqlite:///data/dutch_news.db",
) -> None:
    """
    Run vocabulary extraction on episodes in the database.

    Args:
        max_episodes: Process only the N most recent episodes (by published_at). None = all.
        episode_id: Process only this episode ID. Overrides max_episodes if set.
        replace_existing: If True, replace existing vocabulary for each episode.
        db_path: Database URL.
    """
    engine = get_engine(db_path)
    # Ensure vocabulary tables exist (create if missing, e.g. after model update)
    Base.metadata.create_all(engine, checkfirst=True)
    _migrate_schema(engine)
    session = get_session(engine)

    # Build query
    query = (
        session.query(Episode)
        .filter(Episode.transcript_fetched == True)
        .order_by(Episode.published_at.desc())
    )

    if episode_id is not None:
        query = query.filter(Episode.id == episode_id)
        episodes = query.all()
        if not episodes:
            print(f"❌ No episode found with id={episode_id}")
            session.close()
            return
    elif max_episodes is not None:
        episodes = query.limit(max_episodes).all()
    else:
        episodes = query.all()

    if not episodes:
        print("❌ No episodes with transcripts found. Run ingest_playlist.py first.")
        session.close()
        return

    print("=" * 70)
    print("Dutch News Learner — Vocabulary Extraction")
    print("=" * 70)
    print(f"Episodes to process: {len(episodes)}")

    # Load dictionary for separable verb recombination
    lookup = get_lookup()
    if lookup.is_loaded:
        print("Dictionary loaded — separable verb recombination enabled")
    else:
        print("Dictionary not found — separable verb recombination disabled")
        lookup = None
    print()

    extractor = VocabularyExtractor(dictionary_lookup=lookup)
    total_items = 0
    total_rows = 0

    for idx, episode in enumerate(episodes, 1):
        print(f"[{idx}/{len(episodes)}] {episode.title[:50]}...")
        print(f"  Episode ID: {episode.id} | Video: {episode.video_id}")

        # Eager-load segments
        episode.subtitle_segments  # Trigger lazy load

        try:
            items, rows = extract_vocabulary_for_episode(
                session, episode, extractor, replace_existing=replace_existing
            )
            session.commit()
            total_items += items
            total_rows += rows
            print(f"  ✅ Extracted {rows} vocabulary entries ({items} new lemmas)")
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            session.rollback()

        print()

    session.close()

    print("=" * 70)
    print("📊 EXTRACTION SUMMARY")
    print("=" * 70)
    print(f"Episodes processed: {len(episodes)}")
    print(f"EpisodeVocabulary rows: {total_rows}")
    print(f"New VocabularyItems: {total_items}")
    print()
    print("Next steps:")
    print("  1. Build learning interface (Phase 3)")
    print("  2. Add daily quiz (Phase 4)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract vocabulary from ingested episodes"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all episodes (default if no other limit given)",
    )
    parser.add_argument(
        "--max",
        type=int,
        metavar="N",
        help="Process only the N most recent episodes",
    )
    parser.add_argument(
        "--episode-id",
        type=int,
        metavar="ID",
        help="Process only this episode ID",
    )
    parser.add_argument(
        "--no-replace",
        action="store_true",
        help="Do not replace existing vocabulary (add to existing)",
    )
    parser.add_argument("--init-db", action="store_true", help="Initialize database first")
    parser.add_argument(
        "--db",
        default="sqlite:///data/dutch_news.db",
        help="Database URL",
    )

    args = parser.parse_args()

    if args.init_db:
        print("Initializing database...")
        init_db(args.db)
        print()

    max_episodes = args.max if args.max is not None else (None if args.all else 5)
    episode_id = args.episode_id

    run_extraction(
        max_episodes=max_episodes,
        episode_id=episode_id,
        replace_existing=not args.no_replace,
        db_path=args.db,
    )
