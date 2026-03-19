#!/usr/bin/env python3
"""
Extract vocabulary from ingested episodes using spaCy NLP.

Processes subtitle segments for each episode: tokenizes, lemmatizes, filters by POS
(NOUN, VERB, ADJ, ADV), and stores vocabulary in VocabularyItem and EpisodeVocabulary tables.

By default, only processes episodes that have transcripts but no vocabulary yet (incremental).
Use --all to re-process all episodes, or --max N to limit scope.

Usage:
    python scripts/extract_vocabulary.py                 # Only episodes missing vocabulary (incremental)
    python scripts/extract_vocabulary.py --all          # Process all episodes
    python scripts/extract_vocabulary.py --max 3       # Limit to 3 most recent (within scope)
"""

import argparse
import os
import sys
import time
from datetime import datetime
from typing import Optional, Tuple

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

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

    t0 = time.time()
    vocab_dict = extractor.extract_from_segments(segments)
    print(f"    NLP done: {len(vocab_dict)} lemmas ({time.time()-t0:.1f}s)", flush=True)

    if replace_existing:
        t1 = time.time()
        session.query(EpisodeVocabulary).filter_by(episode_id=episode.id).delete()
        print(f"    DELETE done ({time.time()-t1:.1f}s)", flush=True)

    items_created = 0
    rows_created = 0

    t2 = time.time()
    for lemma, data in vocab_dict.items():
        vocab_item = session.query(VocabularyItem).filter_by(lemma=lemma).first()
        if vocab_item is None:
            vocab_item = VocabularyItem(lemma=lemma, pos=data["pos"])
            session.add(vocab_item)
            session.flush()
            items_created += 1

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
    print(f"    DB inserts done: {rows_created} rows ({time.time()-t2:.1f}s)", flush=True)

    return items_created, rows_created


def run_extraction(
    max_episodes: Optional[int] = None,
    episode_id: Optional[int] = None,
    replace_existing: bool = True,
    incremental: bool = True,
    db_path: str | None = None,
) -> None:
    """
    Run vocabulary extraction on episodes in the database.

    Args:
        max_episodes: Process only the N most recent episodes (by published_at). None = all in scope.
        episode_id: Process only this episode ID. Overrides other filters if set.
        replace_existing: If True, replace existing vocabulary for each episode.
        incremental: If True (default), only process episodes that have no vocabulary yet.
        db_path: Database URL (default: DATABASE_URL env var, then SQLite).
    """
    engine = get_engine(db_path)
    # Ensure vocabulary tables exist (create if missing, e.g. after model update)
    Base.metadata.create_all(engine, checkfirst=True)
    _migrate_schema(engine)
    session = get_session(engine)

    # Build query: episodes with transcripts, newest first
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
    else:
        # Incremental: only episodes that have no episode_vocabulary rows
        if incremental:
            episodes_with_vocab = session.query(EpisodeVocabulary.episode_id).distinct()
            query = query.filter(~Episode.id.in_(episodes_with_vocab))
        if max_episodes is not None:
            query = query.limit(max_episodes)
        episodes = query.all()

    if not episodes:
        msg = "No episodes need vocabulary extraction." if incremental else "No episodes with transcripts found."
        print(f"❌ {msg} Run ingest_playlist.py first.")
        session.close()
        return

    print("=" * 70)
    print("Dutch News Learner — Vocabulary Extraction")
    print("=" * 70)
    mode = "incremental (missing vocabulary only)" if incremental else "all episodes"
    print(f"Episodes to process: {len(episodes)} ({mode})")

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

        print(f"  Loading segments...", flush=True)
        episode.subtitle_segments  # Trigger lazy load
        print(f"  Segments loaded: {len(episode.subtitle_segments)}", flush=True)

        try:
            print(f"  Running spaCy + extraction...", flush=True)
            items, rows = extract_vocabulary_for_episode(
                session, episode, extractor, replace_existing=replace_existing
            )
            print(f"  Committing to database...", flush=True)
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
        help="Process all episodes (re-process even those with vocabulary)",
    )
    parser.add_argument(
        "--max",
        type=int,
        metavar="N",
        help="Limit to N most recent episodes (within incremental or all scope)",
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
        default=None,
        help="Database URL (default: DATABASE_URL env var, then SQLite fallback)",
    )

    args = parser.parse_args()

    if args.init_db:
        print("Initializing database...")
        init_db(args.db)
        print()

    run_extraction(
        max_episodes=args.max,
        episode_id=args.episode_id,
        replace_existing=not args.no_replace,
        incremental=not args.all,
        db_path=args.db,
    )
