#!/usr/bin/env python3
"""
Check if the pipeline needs to run: are there playlist videos not yet in the DB?

Compares YouTube playlist videos against DB (episodes with transcript_fetched).
If any playlist video is missing or not fully ingested → run pipeline.
No time window or date filter - runs whenever the workflow is triggered.

Used by GitHub Actions. Prints "true" if pipeline should run, "false" to skip.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.config import DEFAULT_PLAYLIST_ID
from src.ingestion import YouTubePlaylistFetcher
from src.models import Episode, get_engine, get_session


def main():
    try:
        # Fetch playlist videos (newest first; check up to 100)
        fetcher = YouTubePlaylistFetcher()
        videos = fetcher.fetch_playlist_videos(DEFAULT_PLAYLIST_ID, max_results=100)
        if not videos:
            print("true")  # Can't fetch playlist - run pipeline to be safe
            return

        playlist_video_ids = [v["video_id"] for v in videos]

        # Which of these are already in DB with transcript?
        engine = get_engine()
        session = get_session(engine)
        existing = {
            r[0]
            for r in session.query(Episode.video_id)
            .filter(
                Episode.video_id.in_(playlist_video_ids),
                Episode.transcript_fetched == True,
            )
            .all()
        }
        session.close()

        missing = [vid for vid in playlist_video_ids if vid not in existing]
        if missing:
            print("true")  # Episodes missing, run pipeline
        else:
            print("false")  # All up to date, skip
    except Exception:
        print("true")  # On error, run pipeline to be safe


if __name__ == "__main__":
    main()
