"""SQLite access for the ViralWatch API.

The database is a *read-only snapshot* built by scripts/seed_db.py (or by your
real data pipeline). The API never writes to it, so it ships with the app and
works on Render's free tier without a managed database. See README.md.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

# data/viralwatch.db, resolved relative to the project root (one level above app/)
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "viralwatch.db"


def get_connection() -> sqlite3.Connection:
    """Open the snapshot DB in read-only mode.

    Using the ?mode=ro URI guarantees the API can never mutate the file, which
    is exactly what we want for a served snapshot.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. "
            "Build it first with:  python scripts/seed_db.py"
        )
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    return conn


def query(sql: str, params: tuple = ()) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None
