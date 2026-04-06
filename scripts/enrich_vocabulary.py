#!/usr/bin/env python3
"""
Populate VocabularyItem.translation from the Dutch dictionary.

Requires: python scripts/download_dictionary.py (run once)

Usage:
    python scripts/enrich_vocabulary.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.dictionary import get_lookup
from src.models import VocabularyItem, get_engine, get_session


def main():
    parser = argparse.ArgumentParser(description="Enrich vocabulary with dictionary translations")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated")
    parser.add_argument("--db", default=None, help="Database URL (default: DATABASE_URL env var, then SQLite fallback)")
    args = parser.parse_args()

    lookup = get_lookup()
    if not lookup.is_loaded:
        print("Dictionary not loaded. Run: python scripts/download_dictionary.py")
        sys.exit(1)

    engine = get_engine(args.db)
    session = get_session(engine)

    items = session.query(VocabularyItem).all()
    updated = 0
    not_found = 0

    for item in items:
        entry = lookup.lookup_with_example(item.lemma, item.pos)
        # translation = English gloss (gloss_en), not the Dutch definition (gloss)
        gloss_en = entry.get("gloss_en") if entry else None
        if gloss_en:
            if not args.dry_run:
                item.translation = gloss_en
            updated += 1
        else:
            not_found += 1

    if not args.dry_run:
        session.commit()

    print(f"Vocabulary items: {len(items)}")
    print(f"Updated with translation: {updated}")
    print(f"Not in dictionary: {not_found}")
    if args.dry_run:
        print("(Dry run — no changes saved)")


if __name__ == "__main__":
    main()
