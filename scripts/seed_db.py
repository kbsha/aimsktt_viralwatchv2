"""Build the snapshot the API serves, from the processed real-data files:
    data/processed/zones.geojson        (real Kivu health-zone boundaries)
    data/processed/zone_attributes.csv  (real pop / health-site / CCVI values)

Writes to SQLite by default. If the DATABASE_URL environment variable is set
(e.g. your Aiven Postgres URI), it seeds that Postgres database instead — so the
exact same command provisions both local dev and your Render/Aiven deployment.

  python scripts/seed_db.py                       # -> data/viralwatch.db (SQLite)
  DATABASE_URL="postgres://...:...@...:.../db?sslmode=require" \
      python scripts/seed_db.py                   # -> Postgres

The warning_score / next7d_prob here are a TRANSPARENT PLACEHOLDER derived from
real static vulnerability inputs (population density, CCVI socioeconomic
deprivation, health-site scarcity). They stand in for your trained model's
anomaly score + next-7-day classifier output — swap those in when ready.
Depends on: Python standard library (+ psycopg only when DATABASE_URL is set).
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "processed" / "zone_attributes.csv"
GEOJSON_PATH = ROOT / "data" / "processed" / "zones.geojson"
DB_PATH = ROOT / "data" / "viralwatch.db"
UPDATED = "2026-07-11"  # snapshot date from the INRB build (national INSP sitrep)

COLUMNS = [
    "zone", "province", "borders_rwanda", "warning_score", "next7d_prob",
    "pop_count", "pop_density", "healthsites", "ccvi_deprivation", "updated",
]


def _norm(values):
    """min-max normalise a list of floats to 0..1 (Nones -> 0)."""
    nums = [v for v in values if v is not None]
    lo, hi = (min(nums), max(nums)) if nums else (0.0, 1.0)
    rng = (hi - lo) or 1.0
    return [0.0 if v is None else (v - lo) / rng for v in values]


def load_rows():
    with CSV_PATH.open(encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))

    dens = _norm([float(r["pop_density"] or 0) for r in raw])
    ccvi = _norm([float(r["ccvi_deprivation"]) if r["ccvi_deprivation"] else None for r in raw])
    # health-site scarcity: fewer sites per 100k people -> higher risk
    scarcity = []
    for r in raw:
        pop = float(r["pop_count"] or 0)
        hs = float(r["healthsites"] or 0)
        per100k = (hs / pop * 100000) if pop else 0
        scarcity.append(per100k)
    scarcity = [1 - x for x in _norm(scarcity)]  # invert: scarce -> high

    rows = []
    for r, d, c, s in zip(raw, dens, ccvi, scarcity):
        # placeholder composite vulnerability index (stands in for model output)
        score = round(min(0.98, 0.45 * d + 0.35 * c + 0.20 * s), 3)
        prob = round(min(0.98, max(0.02, 0.1 + 0.85 * score)), 3)
        rows.append((
            r["zone"], r["province"], int(r["borders_rwanda"]), score, prob,
            float(r["pop_count"] or 0), round(float(r["pop_density"] or 0), 1),
            int(r["healthsites"] or 0),
            round(float(r["ccvi_deprivation"]), 3) if r["ccvi_deprivation"] else None,
            UPDATED,
        ))
    return rows


DDL_SQLITE = """
CREATE TABLE zones (
    zone TEXT PRIMARY KEY,
    province TEXT NOT NULL,
    borders_rwanda INTEGER NOT NULL,
    warning_score REAL NOT NULL,
    next7d_prob REAL NOT NULL,
    pop_count REAL NOT NULL,
    pop_density REAL NOT NULL,
    healthsites INTEGER NOT NULL,
    ccvi_deprivation REAL,
    updated TEXT NOT NULL
)"""

DDL_PG = DDL_SQLITE.replace("INTEGER", "INTEGER").replace("REAL", "DOUBLE PRECISION")


def seed_sqlite(rows):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(DDL_SQLITE)
    conn.executemany(
        f"INSERT INTO zones ({','.join(COLUMNS)}) VALUES ({','.join(['?']*len(COLUMNS))})",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"  SQLite: wrote {DB_PATH}  ({len(rows)} zones)")


def seed_postgres(rows, url):
    import psycopg  # only needed for the Postgres path
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS zones")
        cur.execute(DDL_PG)
        cur.executemany(
            f"INSERT INTO zones ({','.join(COLUMNS)}) VALUES ({','.join(['%s']*len(COLUMNS))})",
            rows,
        )
        conn.commit()
    print(f"  Postgres: seeded {len(rows)} zones")


def main():
    print("Building ViralWatch snapshot from real Kivu health-zone data...")
    rows = load_rows()
    url = os.environ.get("DATABASE_URL")
    if url:
        seed_postgres(rows, url)
    else:
        seed_sqlite(rows)
    print("Done.")


if __name__ == "__main__":
    main()
