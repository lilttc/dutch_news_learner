#!/usr/bin/env python3
"""Quick check of active connections and locks on Neon."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv()
from src.models import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    print("=== Active connections ===")
    rows = conn.execute(
        text("""
        SELECT pid, state, wait_event_type, wait_event,
               left(query, 150) as query,
               now() - query_start as duration
        FROM pg_stat_activity
        WHERE datname = current_database()
        ORDER BY query_start
    """)
    ).fetchall()
    if not rows:
        print("(none)")
    for r in rows:
        print(f"PID={r[0]} state={r[1]} wait={r[2]}:{r[3]} dur={r[5]}")
        print(f"  query: {r[4]}")
        print()

    print("=== Blocked queries ===")
    blocked = conn.execute(
        text("""
        SELECT blocked.pid AS blocked_pid,
               blocked.query AS blocked_query,
               blocking.pid AS blocking_pid,
               blocking.query AS blocking_query
        FROM pg_stat_activity blocked
        JOIN pg_locks blocked_locks ON blocked.pid = blocked_locks.pid
        JOIN pg_locks blocking_locks ON blocked_locks.locktype = blocking_locks.locktype
            AND blocked_locks.relation = blocking_locks.relation
            AND blocked_locks.pid != blocking_locks.pid
        JOIN pg_stat_activity blocking ON blocking_locks.pid = blocking.pid
        WHERE NOT blocked_locks.granted
    """)
    ).fetchall()
    if not blocked:
        print("(none)")
    for r in blocked:
        print(f"Blocked PID={r[0]}: {r[1][:100]}")
        print(f"  BY PID={r[2]}: {r[3][:100]}")
        print()
