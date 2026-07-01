#!/usr/bin/env python3
"""
Evaluate semantic-search retrieval quality against a hand-labeled Q&A set.

Loads question/expected-episode pairs from tests/data/episode_qa_eval.json,
runs retrieval for each question, and reports whether the expected episode
appears in the top-N results. This is what turns "I added RAG" into
"I measured retrieval at X/N".

Requires: OPENAI_API_KEY in .env, and a Postgres database with pgvector +
populated Episode.embedding columns (run scripts/embed_episodes.py first).

Usage:
    python scripts/run_eval.py
    python scripts/run_eval.py --dataset tests/data/episode_qa_eval.json --top-n 3
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.models import _migrate_schema, get_engine, get_session
from src.rag import is_semantic_search_available, search_episodes

DEFAULT_DATASET = Path(__file__).resolve().parent.parent / "tests" / "data" / "episode_qa_eval.json"


def matches(episode, case: dict) -> bool:
    if case.get("expected_video_id") and episode.video_id == case["expected_video_id"]:
        return True
    contains = case.get("expected_title_contains")
    if contains and contains.lower() in (episode.title or "").lower():
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Evaluate semantic-search retrieval quality")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--top-n", type=int, default=3, help="Count a hit if the expected episode is in top N"
    )
    parser.add_argument("--db", default=None, help="Database URL (default: DATABASE_URL env var)")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set. Add it to .env")
        sys.exit(1)

    if not args.dataset.exists():
        print(f"Error: dataset not found at {args.dataset}")
        sys.exit(1)

    cases = json.loads(args.dataset.read_text())
    if not cases:
        print("Error: dataset is empty")
        sys.exit(1)
    if any(c.get("question", "").startswith("REPLACE_ME") for c in cases):
        print(
            f"Error: {args.dataset} still contains placeholder questions. "
            "Replace them with real questions grounded in your ingested episodes first."
        )
        sys.exit(1)

    engine = get_engine(args.db)
    _migrate_schema(engine)
    session = get_session(engine)

    if not is_semantic_search_available(session):
        print("Semantic search requires Postgres + pgvector; cannot run eval on SQLite.")
        sys.exit(1)

    print("=" * 60)
    print("Dutch News Learner - Retrieval Evaluation")
    print("=" * 60)
    print(f"Dataset: {args.dataset} ({len(cases)} questions) | top-{args.top_n}")
    print()

    hits = 0
    for i, case in enumerate(cases, 1):
        question = case["question"]
        results = search_episodes(session, question, limit=args.top_n)
        hit = any(matches(ep, case) for ep in results)
        hits += hit
        status = "✓" if hit else "✗"
        print(f"{status} [{i}/{len(cases)}] {question}")
        if not hit:
            found = ", ".join(ep.title[:40] for ep in results) or "(no results)"
            expected = case.get("expected_title_contains") or case.get("expected_video_id")
            print(f"    expected: {expected}")
            print(f"    got: {found}")

    print()
    accuracy = 100 * hits / len(cases)
    print(f"Retrieval accuracy: {hits}/{len(cases)} ({accuracy:.0f}%) in top-{args.top_n}")


if __name__ == "__main__":
    main()
