#!/usr/bin/env python3
"""
Check if the pipeline needs to run based on whether today's (or Friday's) episode is in the DB.

Used by GitHub Actions: run pipeline only when the expected episode is not yet ingested.
- Weekdays: check if an episode with published_at = today (UTC) exists
- Weekends: check if Friday's episode exists (NOS may not upload Sat/Sun)

Prints "true" if pipeline should run, "false" if episode already in DB.
Exit code 0 always (output used by workflow, not exit code).
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import func
from src.models import Episode, get_engine, get_session


def main():
    try:
        engine = get_engine()
        session = get_session(engine)

        now = datetime.utcnow()
        today = now.date()

        # Weekend (Sat=5, Sun=6): check for Friday's episode
        if now.weekday() == 5:  # Saturday → check Friday
            target_date = today - timedelta(days=1)
        elif now.weekday() == 6:  # Sunday → check Friday
            target_date = today - timedelta(days=2)
        else:
            target_date = today  # Weekday → check today

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
