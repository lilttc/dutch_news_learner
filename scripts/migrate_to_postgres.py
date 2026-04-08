#!/usr/bin/env python3
"""
One-time migration: copy all data from local SQLite to cloud Postgres.

Reads from data/dutch_news.db (SQLite) and writes to DATABASE_URL (Postgres).
Safe to run multiple times - skips rows that already exist (matched by primary key).

Uses batch inserts (500 rows/batch) and pre-fetches existing PKs to avoid
per-row round-trips to the remote database.

Usage:
    python scripts/migrate_to_postgres.py              # full migration
    python scripts/migrate_to_postgres.py --dry-run    # preview without writing
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from psycopg2.extras import execute_values
from sqlalchemy import create_engine, inspect, text

from src.models import Base, _migrate_schema

SQLITE_URL = "sqlite:///data/dutch_news.db"

BATCH_SIZE = 500

BOOL_COLUMNS = {
    "episodes": {"transcript_fetched", "transcript_is_generated"},
}

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


def get_existing_pks(engine, table: str, pk_col: str) -> set:
    """Fetch all existing primary keys in one query."""
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT {pk_col} FROM {table}"))
        return {row[0] for row in result.fetchall()}


def coerce_booleans(table: str, rows: list[dict]) -> list[dict]:
    """Convert SQLite integer booleans (0/1) to Python bool for Postgres."""
    cols = BOOL_COLUMNS.get(table)
    if not cols:
        return rows
    for row in rows:
        for col in cols:
            if col in row and row[col] is not None:
                row[col] = bool(row[col])
    return rows


def insert_batch(conn, table: str, rows: list[dict]):
    """Insert rows using psycopg2 execute_values for true multi-row INSERT."""
    if not rows:
        return
    columns = list(rows[0].keys())
    col_str = ", ".join(columns)

    raw_conn = conn.connection.dbapi_connection
    with raw_conn.cursor() as cur:
        execute_values(
            cur,
            f"INSERT INTO {table} ({col_str}) VALUES %s",
            argslist=[tuple(r[c] for c in columns) for r in rows],
            page_size=BATCH_SIZE,
        )


def migrate_table(sqlite_engine, pg_engine, table: str, dry_run: bool) -> tuple[int, int, int]:
    """Migrate one table. Returns (sqlite_count, pg_before, inserted)."""
    sqlite_count = count_rows(sqlite_engine, table)
    pg_before = count_rows(pg_engine, table)

    inspector = inspect(pg_engine)
    pk_cols = inspector.get_pk_constraint(table).get("constrained_columns", [])
    pk_col = pk_cols[0] if pk_cols else "id"

    existing_pks = get_existing_pks(pg_engine, table, pk_col)

    rows = fetch_all(sqlite_engine, table)
    new_rows = [r for r in rows if r.get(pk_col) not in existing_pks]
    new_rows = coerce_booleans(table, new_rows)

    if dry_run or not new_rows:
        return sqlite_count, pg_before, len(new_rows)

    with pg_engine.begin() as conn:
        for i in range(0, len(new_rows), BATCH_SIZE):
            batch = new_rows[i : i + BATCH_SIZE]
            insert_batch(conn, table, batch)

    return sqlite_count, pg_before, len(new_rows)


def reset_sequences(pg_engine, tables: list[str]):
    """Reset Postgres SERIAL sequences to max(id) + 1 so future inserts don't collide."""
    with pg_engine.begin() as conn:
        for table in tables:
            try:
                max_id = conn.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table}")).scalar()
                seq_name = f"{table}_id_seq"
                conn.execute(
                    text(f"SELECT setval('{seq_name}', :val, true)"),
                    {"val": max_id},
                )
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite data to Postgres")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    pg_url = os.environ.get("DATABASE_URL")
    if not pg_url or not pg_url.startswith("postgresql"):
        print("DATABASE_URL not set or not a Postgres URL.")
        print("   Set it in .env: DATABASE_URL=postgresql://...")
        sys.exit(1)

    sqlite_path = Path("data/dutch_news.db")
    if not sqlite_path.exists():
        print(f"SQLite database not found: {sqlite_path}")
        sys.exit(1)

    print(f"Source: {sqlite_path}")
    print("Target: Postgres (Neon)")
    if args.dry_run:
        print("DRY RUN - no data will be written")
    print()

    sqlite_engine = create_engine(SQLITE_URL, echo=False)
    pg_engine = create_engine(
        pg_url,
        echo=False,
        connect_args={"sslmode": "require"},
    )

    print("Creating Postgres schema...")
    Base.metadata.create_all(pg_engine)
    _migrate_schema(pg_engine)
    print("Schema ready\n")

    total_inserted = 0
    t0 = time.time()

    for table in TABLES_IN_ORDER:
        t_start = time.time()
        sqlite_count, pg_before, inserted = migrate_table(
            sqlite_engine, pg_engine, table, dry_run=args.dry_run
        )
        elapsed = time.time() - t_start
        total_inserted += inserted

        pg_after = pg_before + inserted
        verb = "would insert" if args.dry_run else "inserted"
        print(
            f"  {table:25s}  SQLite: {sqlite_count:>6}  "
            f"PG before: {pg_before:>6}  "
            f"{verb}: {inserted:>6}  "
            f"PG after: {pg_after:>6}  "
            f"({elapsed:.1f}s)"
        )

    if not args.dry_run and total_inserted > 0:
        print("\nResetting Postgres sequences...")
        reset_sequences(pg_engine, TABLES_IN_ORDER)
        print("Sequences reset")

    total_time = time.time() - t0
    label = "Dry run" if args.dry_run else "Migration"
    print(f"\n{label} complete! ({total_inserted} rows, {total_time:.1f}s)")


if __name__ == "__main__":
    main()
