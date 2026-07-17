"""Data access for the ViralWatch API — works with either backend:

  * No DATABASE_URL  -> read-only SQLite snapshot at data/viralwatch.db
                        (ships with the app; great for local dev and a
                        zero-ops Render deploy).
  * DATABASE_URL set -> PostgreSQL (e.g. Aiven / Neon / Supabase / Render PG).
                        Set it as an env var on Render; the code switches
                        automatically.

Queries are written with '?' placeholders and translated to '%s' for Postgres,
so the endpoints don't care which backend is live.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "viralwatch.db"
DATABASE_URL = os.environ.get("DATABASE_URL")
IS_POSTGRES = bool(DATABASE_URL)


def _rows_from_sqlite(sql: str, params: tuple) -> list[dict]:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Build it with: python scripts/seed_db.py"
        )
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _rows_from_postgres(sql: str, params: tuple) -> list[dict]:
    import psycopg
    from psycopg.rows import dict_row

    pg_sql = sql.replace("?", "%s")
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(pg_sql, params)
            return cur.fetchall()


def query(sql: str, params: tuple = ()) -> list[dict]:
    return _rows_from_postgres(sql, params) if IS_POSTGRES else _rows_from_sqlite(sql, params)


def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None
