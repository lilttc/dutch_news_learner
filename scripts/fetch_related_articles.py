#!/usr/bin/env python3
"""
Fetch related NOS articles for each episode's topics using DuckDuckGo search.

For each topic keyword (from Episode.topics), searches nos.nl for recent articles
and stores the top results (title + URL + snippet) in Episode.related_articles
as JSON. This gives learners direct links to real Dutch news articles about the
episode's topics.

No API keys required — uses the ddgs (DuckDuckGo Search) library.

Usage:
    python scripts/fetch_related_articles.py              # Episodes with topics but no articles
    python scripts/fetch_related_articles.py --all        # Re-fetch for all episodes
    python scripts/fetch_related_articles.py --max 5      # Latest 5 episodes
    python scripts/fetch_related_articles.py --episode-id 427
    python scripts/fetch_related_articles.py --dry-run    # Preview without saving
"""

import argparse
import json
import random
import sys
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from ddgs import DDGS

from src.models import Episode, _migrate_schema, get_engine, get_session

RESULTS_PER_TOPIC = 3
BASE_DELAY_SECONDS = 3.0
MAX_RETRIES = 3


def search_nos_articles(
    query: str,
    num_results: int = RESULTS_PER_TOPIC,
    timelimit: str | None = None,
) -> list[dict]:
    """
    Search for NOS articles via DuckDuckGo, restricted to nos.nl.

    Uses the Netherlands region for better Dutch results and retries with
    exponential backoff when rate-limited.

    Args:
        query: Search query (topic keyword).
        num_results: Maximum number of results to return.
        timelimit: Date filter — standard ("d","w","m","y") or Google cdr format
                   like "cdr:1,cd_min:MM/DD/YYYY,cd_max:MM/DD/YYYY".

    Returns:
        List of {title, url, snippet} dicts.
    """
    site_query = f"site:nos.nl {query}"

    for attempt in range(MAX_RETRIES):
        try:
            raw_results = list(
                DDGS().text(
                    site_query,
                    region="nl-nl",
                    timelimit=timelimit,
                    max_results=num_results,
                )
            )
            results = []
            for item in raw_results:
                url = item.get("href", "")
                if "nos.nl" not in url:
                    continue
                results.append({
                    "title": item.get("title", ""),
                    "url": url,
                    "snippet": item.get("body", ""),
                })
            return results

        except Exception as e:
            err_str = str(e)
            is_rate_limit = (
                "error sending request" in err_str
                or "Ratelimit" in err_str
                or "DecodeError" in err_str
            )
            if is_rate_limit and attempt < MAX_RETRIES - 1:
                backoff = BASE_DELAY_SECONDS * (2 ** attempt) + random.uniform(1, 3)
                print(f"(rate-limited, waiting {backoff:.0f}s)...", end=" ", flush=True)
                time.sleep(backoff)
                continue

            if "No results found" in err_str:
                return []

            print(f"⚠ Search error: {e}")
            return []

    return []


def fetch_articles_for_episode(
    episode: Episode,
    dry_run: bool = False,
) -> list[dict] | None:
    """
    Fetch related NOS articles for one episode's topics.

    Returns list of article dicts or None on failure.
    """
    topics = episode.topics
    if not topics or not topics.strip():
        return None

    topic_list = [t.strip() for t in topics.split("|") if t.strip()]
    if not topic_list:
        return None

    # Build date range: episode date ± 7 days
    timelimit = None
    if episode.published_at:
        dt = episode.published_at.date() if hasattr(episode.published_at, "date") else episode.published_at
        start = dt - timedelta(days=7)
        end = dt + timedelta(days=7)
        timelimit = f"cdr:1,cd_min:{start.month:02d}/{start.day:02d}/{start.year},cd_max:{end.month:02d}/{end.day:02d}/{end.year}"

    all_articles = []
    for i, topic in enumerate(topic_list):
        if dry_run:
            print(f"    Would search: {topic!r}")
            continue

        print(f"    Searching: {topic!r}...", end=" ", flush=True)
        articles = search_nos_articles(topic, timelimit=timelimit)
        for article in articles:
            article["topic"] = topic
        all_articles.extend(articles)
        print(f"{len(articles)} results")

        if i < len(topic_list) - 1:
            delay = BASE_DELAY_SECONDS + random.uniform(0.5, 2.0)
            time.sleep(delay)

    return all_articles if not dry_run else None


def main():
    parser = argparse.ArgumentParser(
        description="Fetch related NOS articles for episode topics"
    )
    parser.add_argument("--all", action="store_true", help="Re-fetch for all episodes with topics")
    parser.add_argument("--max", type=int, metavar="N", help="Process only N most recent episodes")
    parser.add_argument("--episode-id", type=int, metavar="ID", help="Process only this episode")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--db", default=None, help="Database URL (default: DATABASE_URL env var, then SQLite fallback)")
    args = parser.parse_args()

    engine = get_engine(args.db)
    _migrate_schema(engine)
    session = get_session(engine)

    query = (
        session.query(Episode)
        .filter(Episode.transcript_fetched == True)  # noqa: E712
        .filter(Episode.topics.isnot(None))
        .filter(Episode.topics != "")
        .order_by(Episode.published_at.desc())
    )

    if args.episode_id:
        query = query.filter(Episode.id == args.episode_id)
    elif not args.all:
        query = query.filter(
            (Episode.related_articles.is_(None)) | (Episode.related_articles == "")
        )

    if args.max:
        episodes = query.limit(args.max).all()
    else:
        episodes = query.all()

    if not episodes:
        print("No episodes need article fetching.")
        sys.exit(0)

    print("=" * 60)
    print("Dutch News Learner — Fetch Related Articles")
    print("=" * 60)
    mode = "incremental (missing articles only)" if not args.all else "all episodes with topics"
    print(f"Episodes: {len(episodes)} ({mode})")
    if args.dry_run:
        print("(Dry run — no changes)")
    print()

    total_articles = 0
    for ep_idx, ep in enumerate(episodes):
        title_display = ep.title[:50] if ep.title else "(no title)"
        print(f"[{ep.id}] {title_display}...")
        print(f"  Topics: {ep.topics}")

        articles = fetch_articles_for_episode(ep, dry_run=args.dry_run)
        if articles is not None:
            ep.related_articles = json.dumps(articles, ensure_ascii=False)
            total_articles += len(articles)
            if not args.dry_run:
                session.commit()
        print()

        if ep_idx < len(episodes) - 1 and not args.dry_run:
            time.sleep(random.uniform(1.0, 2.0))

    print("=" * 60)
    print(f"Total articles fetched: {total_articles}")
    if not args.dry_run:
        print("Restart the app to see article links in Related Reading.")


if __name__ == "__main__":
    main()
