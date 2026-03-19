#!/usr/bin/env python3
"""
Check if the pipeline needs to run based on:
1. Time window: 6pm–8pm Amsterdam (CEST/CET) — skips outside this window
2. Episode status: today's (or Friday's) episode not yet in DB

Used by GitHub Actions. Prints "true" if pipeline should run, "false" to skip.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import func
from src.models import Episode, get_engine, get_session

AMSTERDAM = ZoneInfo("Europe/Amsterdam")
WINDOW_START = 18  # 6pm
WINDOW_END = 20    # 8pm


def main():
    try:
        # 1. Time window: only run between 6pm–8pm Amsterdam (handles CEST/CET automatically)
        amsterdam_now = datetime.now(AMSTERDAM)
        if amsterdam_now.hour < WINDOW_START or amsterdam_now.hour >= WINDOW_END:
            print("false")  # Outside 6pm–8pm Amsterdam
            return

        engine = get_engine()
        session = get_session(engine)

        # Use Amsterdam date for "today" (weekend logic) — episode dates from YouTube are typically UTC
        today_ams = amsterdam_now.date()

        # Weekend (Sat=5, Sun=6): check for Friday's episode
        if amsterdam_now.weekday() == 5:  # Saturday → check Friday
            target_date = today_ams - timedelta(days=1)
        elif amsterdam_now.weekday() == 6:  # Sunday → check Friday
            target_date = today_ams - timedelta(days=2)
        else:
            target_date = today_ams  # Weekday → check today

        # Check if any episode has published_at on target_date
        count = (
            session.query(Episode)
            .filter(
                Episode.transcript_fetched == True,
                func.date(Episode.published_at) == target_date,
            )
            .count()
        )

        session.close()

        if count > 0:
            print("false")  # Episode exists, skip pipeline
        else:
            print("true")   # Episode missing, run pipeline
    except Exception:
        # On error (e.g. DB connection), run pipeline to be safe
        print("true")


if __name__ == "__main__":
    main()
