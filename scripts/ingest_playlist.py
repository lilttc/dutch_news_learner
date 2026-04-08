#!/usr/bin/env python3
"""
Ingest a YouTube playlist: fetch videos and transcripts, store in database.

Usage:
    python scripts/ingest_playlist.py [--playlist-id ID] [--max-videos N] [--init-db]

Uses default playlist "Drie onderwerpen in makkelijke taal" if --playlist-id not given.
"""

import argparse
import os
import sys
from datetime import datetime

# Add project root to path (scripts/ -> project root)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from src.config import DEFAULT_PLAYLIST_ID, PLAYLIST_SOURCE
from src.ingestion import YouTubePlaylistFetcher, YouTubeTranscriptFetcher
from src.models import Episode, SubtitleSegment, get_engine, get_session, init_db


def ingest_playlist(
    playlist_id: str,
    source: str = PLAYLIST_SOURCE,
    max_videos: int = None,
    skip_existing: bool = True,
    reverse: bool = True,
    db_path: str | None = None,
):
    """
    Ingest a YouTube playlist into the database.

    Args:
        playlist_id: YouTube playlist ID
        source: Content source identifier
        max_videos: Max videos to process (None = all)
        skip_existing: Skip videos already in database
        reverse: Process latest episodes first (recommended for news)
        db_path: Database URL
    """
    print("=" * 70)
    print("Dutch News Learner - Ingesting Playlist")
    print(f"Playlist ID: {playlist_id}")
    print(f"Source: {source}")
    if reverse:
        print("Order: REVERSE (latest episodes first)")
    print("=" * 70)
    print()

    playlist_fetcher = YouTubePlaylistFetcher()
    transcript_fetcher = YouTubeTranscriptFetcher()
    engine = get_engine(db_path)
    session = get_session(engine)

    # Fetch playlist videos
    print("📋 Fetching playlist videos...")
    videos = playlist_fetcher.fetch_playlist_videos(playlist_id, max_results=None)
    print(f"✅ Found {len(videos)} videos")

    if not videos:
        print("❌ No videos found. Check playlist ID and YOUTUBE_API_KEY.")
        session.close()
        return

    if reverse:
        print("🔄 Reversing order (latest first)...")
        videos = list(reversed(videos))

    if max_videos:
        videos = videos[:max_videos]
        print(f"📊 Processing {len(videos)} videos (limit: {max_videos})")

    # Filter out videos already in DB (one query instead of N)
    if skip_existing:
        video_ids = [v["video_id"] for v in videos]
        existing_ids = {
            r[0]
            for r in session.query(Episode.video_id).filter(Episode.video_id.in_(video_ids)).all()
        }
        videos_to_process = [v for v in videos if v["video_id"] not in existing_ids]
        skipped_count = len(videos) - len(videos_to_process)
        print(f"⏭️  Skipping {skipped_count} already in database")
    else:
        videos_to_process = videos
        skipped_count = 0

    print()

    success_count = 0
    failed_count = 0

    for idx, video_data in enumerate(videos_to_process, 1):
        video_id = video_data["video_id"]
        title = video_data["title"]

        print(f"[{idx}/{len(videos_to_process)}] {title[:60]}...")
        print(f"  Video ID: {video_id}")

        existing = session.query(Episode).filter_by(video_id=video_id).first()

        try:
            transcript_result = transcript_fetcher.fetch_transcript(video_id, include_metadata=True)

            if not transcript_result:
                print("  ❌ FAILED: No transcript available")
                failed_count += 1
                print()
                continue

            segments = transcript_result["segments"]
            metadata = transcript_result["metadata"]

            print(f"  ✅ Transcript: {len(segments)} segments ({metadata['language_code']})")

            # Create or update episode
            published_at = datetime.fromisoformat(video_data["published_at"].replace("Z", "+00:00"))

            if existing:
                episode = existing
                episode.title = title
                episode.description = video_data.get("description", "")
                episode.updated_at = datetime.utcnow()
                # Delete old segments
                session.query(SubtitleSegment).filter_by(video_id=video_id).delete()
            else:
                episode = Episode(
                    video_id=video_id,
                    title=title,
                    description=video_data.get("description", ""),
                    published_at=published_at,
                    position=video_data["position"],
                    thumbnail_url=video_data.get("thumbnail_url", ""),
                    source=source,
                )
                session.add(episode)

            episode.transcript_fetched = True
            episode.transcript_language = metadata["language_code"]
            episode.transcript_is_generated = metadata["is_generated"]

            session.flush()  # Get episode.id for segments

            for seg in segments:
                segment_record = SubtitleSegment(
                    episode_id=episode.id,
                    video_id=video_id,
                    text=seg["text"],
                    start_time=seg["start"],
                    duration=seg["duration"],
                    end_time=seg["start"] + seg["duration"],
                )
                session.add(segment_record)

            session.commit()
            print(f"  💾 SAVED: {len(segments)} segments")
            success_count += 1

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            session.rollback()
            failed_count += 1

        print()

    session.close()

    # Summary
    print("=" * 70)
    print("📊 INGESTION SUMMARY")
    print("=" * 70)
    print(f"✅ Success: {success_count} videos")
    print(f"⏭️  Skipped: {skipped_count} videos")
    print(f"❌ Failed:  {failed_count} videos")
    print()

    if success_count > 0:
        print("🎉 Ingestion complete!")
        print()
        print("Next steps:")
        print("  1. Run vocabulary extraction (Phase 2)")
        print("  2. Start the learning app (Phase 3)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest YouTube playlist for Dutch News Learner")
    parser.add_argument(
        "--playlist-id",
        default=DEFAULT_PLAYLIST_ID,
        help=f"YouTube playlist ID (default: {DEFAULT_PLAYLIST_ID})",
    )
    parser.add_argument(
        "--source",
        default=PLAYLIST_SOURCE,
        help="Content source identifier",
    )
    parser.add_argument("--max-videos", type=int, help="Max videos to ingest")
    parser.add_argument("--force", action="store_true", help="Re-ingest existing videos")
    parser.add_argument(
        "--reverse",
        action="store_true",
        default=True,
        help="Process latest episodes first (default: True)",
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

    ingest_playlist(
        playlist_id=args.playlist_id,
        source=args.source,
        max_videos=args.max_videos,
        skip_existing=not args.force,
        reverse=args.reverse,
        db_path=args.db,
    )
