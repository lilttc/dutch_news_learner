#!/usr/bin/env python3
"""
Convert dutch_glosses.json to a SQLite database for memory-efficient lookups.

The JSON file (~63MB) expands to ~300MB when loaded into Python dicts,
which exceeds Render free tier's 512MB RAM limit. SQLite lets us query
individual words without loading everything into memory.

Usage:
    python scripts/convert_dictionary_to_sqlite.py

Input:  data/dictionary/dutch_glosses.json
Output: data/dictionary/dutch_glosses.db
"""

import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = PROJECT_ROOT / "data" / "dictionary" / "dutch_glosses.json"
DB_PATH = PROJECT_ROOT / "data" / "dictionary" / "dutch_glosses.db"


def convert():
    if not JSON_PATH.exists():
        print(f"Error: {JSON_PATH} not found. Run scripts/download_dictionary.py first.")
        sys.exit(1)

    print(f"Loading {JSON_PATH} ...")
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded {len(data)} lemmas. Converting to SQLite ...")

    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE glosses (
            lemma TEXT NOT NULL,
            pos TEXT NOT NULL,
            gloss TEXT,
            gloss_en TEXT,
            example TEXT,
            PRIMARY KEY (lemma, pos)
        )
    """)
    conn.execute("CREATE INDEX idx_glosses_lemma ON glosses(lemma)")

    rows = 0
    for lemma, value in data.items():
        key = lemma.lower().strip()
        if isinstance(value, str):
            # Legacy flat format: just a gloss string, no POS
            conn.execute(
                "INSERT OR IGNORE INTO glosses (lemma, pos, gloss) VALUES (?, ?, ?)",
                (key, "_DEFAULT", value),
            )
            rows += 1
        elif isinstance(value, dict):
            for pos, entry in value.items():
                if isinstance(entry, str):
                    conn.execute(
                        "INSERT OR IGNORE INTO glosses (lemma, pos, gloss) VALUES (?, ?, ?)",
                        (key, pos, entry),
                    )
                elif isinstance(entry, dict):
                    conn.execute(
                        "INSERT OR IGNORE INTO glosses (lemma, pos, gloss, gloss_en, example) VALUES (?, ?, ?, ?, ?)",
                        (key, pos, entry.get("gloss"), entry.get("gloss_en"), entry.get("example")),
                    )
                rows += 1

    conn.commit()
    conn.close()

    json_size = JSON_PATH.stat().st_size / (1024 * 1024)
    db_size = DB_PATH.stat().st_size / (1024 * 1024)
    print(f"Done. {rows} rows written.")
    print(f"JSON: {json_size:.1f} MB -> SQLite: {db_size:.1f} MB")
    print(f"Output: {DB_PATH}")


if __name__ == "__main__":
    convert()
