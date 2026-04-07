#!/usr/bin/env python3
"""
Populate VocabularyItem.translation from the Dutch dictionary (English gloss).

By default, only fills items with no translation yet (incremental).
Use --all to overwrite all items (e.g. after updating the dictionary).

Requires: python scripts/download_dictionary.py (run once)

Usage:
    python scripts/enrich_vocabulary.py            # Only items missing a translation
    python scripts/enrich_vocabulary.py --all      # Overwrite all items
    python scripts/enrich_vocabulary.py --dry-run  # Preview without saving
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import or_

from src.dictionary import get_lookup
from src.models import VocabularyItem, get_engine, get_session


def main():
    parser = argparse.ArgumentParser(description="Enrich vocabulary with dictionary translations")
    parser.add_argument("--all", action="store_true", help="Overwrite all items, not just those missing a translation")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated")
    parser.add_argument("--db", default=None, help="Database URL (default: DATABASE_URL env var, then SQLite fallback)")
    args = parser.parse_args()

    lookup = get_lookup()
    if not lookup.is_loaded:
        print("Dictionary not loaded. Run: python scripts/download_dictionary.py")
        sys.exit(1)

    engine = get_engine(args.db)
    session = get_session(engine)

    query = session.query(VocabularyItem)
    if not args.all:
        query = query.filter(
            or_(VocabularyItem.translation.is_(None), VocabularyItem.translation == "")
        )
    items = query.all()

    updated = 0
    not_found = 0

    for item in items:
        entry = lookup.lookup_with_example(item.lemma, item.pos)
        # Use English gloss (gloss_en), not the Dutch definition (gloss)
        gloss_en = entry.get("gloss_en") if entry else None
        if gloss_en:
            if not args.dry_run:
                item.translation = gloss_en
            updated += 1
        else:
            not_found += 1

    if not args.dry_run:
        session.commit()

    mode = "all items" if args.all else "items missing translation"
    print(f"Vocabulary items ({mode}): {len(items)}")
    print(f"Updated with translation: {updated}")
    print(f"Not in dictionary: {not_found}")
    if args.dry_run:
        print("(Dry run — no changes saved)")


if __name__ == "__main__":
    main()
