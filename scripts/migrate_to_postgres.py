#!/usr/bin/env python3
"""
One-time migration: copy all data from local SQLite to cloud Postgres.

Reads from data/dutch_news.db (SQLite) and writes to DATABASE_URL (Postgres).
Safe to run multiple times — skips rows that already exist (matched by primary key).

Usage:
    python scripts/migrate_to_postgres.py              # full migration
    python scripts/migrate_to_postgres.py --dry-run    # preview without writing
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from src.models import Base, _migrate_schema

SQLITE_URL = "sqlite:///data/dutch_news.db"

TABLES_IN_ORDER = [
    "episodes",
    "subtitle_segments",
    "vocabulary_items",
    "episode_vocabulary",
    "user_vocabulary",
]


def count_rows(engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def fetch_all(engine, table: str) -> list[dict]:
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table}"))
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]


def insert_rows(pg_engine, table: str, rows: list[dict], dry_run: bool) -> int:
    """Insert rows into Postgres, skipping duplicates by primary key."""
    if not rows:
        return 0

    inspector = inspect(pg_engine)
    pk_cols = [col["name"] for col in inspector.get_pk_constraint(table).get("constrained_columns", [])]

    inserted = 0
    with pg_engine.begin() as conn:
        for row in rows:
            if pk_cols:
                pk_filter = " AND ".join(f"{col} = :{col}" for col in pk_cols)
                exists = conn.execute(
                    text(f"SELECT 1 FROM {table} WHERE {pk_filter}"), 
                    {col: row[col] for col in pk_cols}
                ).fetchone()
                if exists:
                    continue

            if dry_run:
                inserted += 1
                continue

            columns = ", ".join(row.keys())
            placeholders = ", ".join(f":{k}" for k in row.keys())
            conn.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"), row)
            inserted += 1

    return inserted


def reset_sequences(pg_engine, tables: list[str]):
    """Reset Postgres SERIAL sequences to max(id) + 1 so future inserts don't collide."""
    with pg_engine.begin() as conn:
        for table in tables:
            try:
                max_id = conn.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table}")).scalar()
                seq_name = f"{table}_id_seq"
                conn.execute(text(f"SELECT setval('{seq_name}', :val, true)"), {"val": max_id})
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite data to Postgres")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    pg_url = os.environ.get("DATABASE_URL")
    if not pg_url or not pg_url.startswith("postgresql"):
        print("❌ DATABASE_URL not set or not a Postgres URL.")
        print("   Set it in .env: DATABASE_URL=postgresql://...")
        sys.exit(1)

    sqlite_path = Path("data/dutch_news.db")
    if not sqlite_path.exists():
        print(f"❌ SQLite database not found: {sqlite_path}")
        sys.exit(1)

    print(f"📦 Source: {sqlite_path}")
    print(f"🐘 Target: Postgres (Neon)")
    if args.dry_run:
        print("🔍 DRY RUN — no data will be written\n")
    print()

    sqlite_engine = create_engine(SQLITE_URL, echo=False)
    pg_engine = create_engine(
        pg_url, echo=False,
        connect_args={"sslmode": "require"},
    )

    print("Creating Postgres schema...")
    Base.metadata.create_all(pg_engine)
    _migrate_schema(pg_engine)
    print("✅ Schema ready\n")

    for table in TABLES_IN_ORDER:
        sqlite_count = count_rows(sqlite_engine, table)
        pg_count_before = count_rows(pg_engine, table)

        rows = fetch_all(sqlite_engine, table)
        inserted = insert_rows(pg_engine, table, rows, dry_run=args.dry_run)

        pg_count_after = pg_count_before + inserted if args.dry_run else count_rows(pg_engine, table)

        status = "would insert" if args.dry_run else "inserted"
        print(
            f"  {table:25s}  SQLite: {sqlite_count:>5}  "
            f"Postgres before: {pg_count_before:>5}  "
            f"{status}: {inserted:>5}  "
            f"Postgres after: {pg_count_after:>5}"
        )

    if not args.dry_run:
        print("\nResetting Postgres sequences...")
        reset_sequences(pg_engine, TABLES_IN_ORDER)
        print("✅ Sequences reset")

    print("\n✅ Migration complete!" if not args.dry_run else "\n✅ Dry run complete!")


if __name__ == "__main__":
    main()
