#!/usr/bin/env python3
"""
Terminate stuck Postgres connections (ALTER TABLE, long-running DELETEs, idle transactions).

Use when check_locks.py shows a deadlock of old migrations blocking extraction.
Safe to run — only kills other backends, not the current connection.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv; load_dotenv()
from src.models import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    my_pid = conn.execute(text("SELECT pg_backend_pid()")).scalar()
    print(f"Our PID: {my_pid} (will not terminate)")

    # Find stuck: ALTER TABLE, long-running DELETE, or idle-in-transaction > 5 min
    rows = conn.execute(text("""
        SELECT pid, state, left(query, 80) as query, now() - query_start as duration
        FROM pg_stat_activity
        WHERE datname = current_database()
          AND pid != :my_pid
          AND (
            query ILIKE '%ALTER TABLE%'
            OR (query ILIKE '%DELETE FROM episode_vocabulary%' AND state = 'active')
            OR (state = 'idle in transaction' AND now() - query_start > interval '5 minutes')
          )
    """), {"my_pid": my_pid}).fetchall()

    if not rows:
        print("No stuck connections found.")
        sys.exit(0)

    print(f"\nTerminating {len(rows)} stuck connection(s):")
    for r in rows:
        print(f"  PID {r[0]} ({r[3]}): {r[2][:60]}...")
        try:
            conn.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": r[0]})
            conn.commit()
            print(f"    -> terminated")
        except Exception as e:
            print(f"    -> failed: {e}")

    print("\nDone. Run extract_vocabulary.py again.")
