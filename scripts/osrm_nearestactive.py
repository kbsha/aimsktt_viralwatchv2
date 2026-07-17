"""
Build the "minutes to nearest active-case zone" feature from the OSRM
travel-time matrix and insp_sitrep's cleaned training window.

What this fixes, and why:
  1. build/long/osrm__travel_time.csv is a full 519x519 matrix, not tidy
     long format (despite living in a "long" folder) -- no need to melt
     the whole thing, since we only ever need "distance to the nearest
     active zone," not every pairwise distance.
  2. Column headers are mangled by R's name-sanitization (dots replacing
     spaces/parens, ".1" duplicate suffixes) and don't reliably match
     canonical zone names by text alone. Fixed here using a verifiable
     property instead of guessing: a zone's distance to itself is always
     0, so row i and column i are confirmed to be the same zone
     positionally -- checked against all 519 diagonal values (all
     exactly 0) before trusting this.
  3. Both row and column labels still need alias resolution afterward
     (47 don't match canonical spelling, same aliases.csv used
     elsewhere in this pipeline).

"Active zone" on a given date = any zone with cumulative_suspected_cases
> 0 as of that date, per insp_sitrep_training_window.csv.

Usage:
    python compute_osrm_nearest_active.py
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OSRM_PATH = REPO_ROOT / "data/external/BDBV2026-Data/build/long/osrm__travel_time.csv"
ALIASES_PATH = REPO_ROOT / "data/external/BDBV2026-Data/data/aliases.csv"
SITREP_PATH = REPO_ROOT / "output/insp_sitrep_training_window.csv"
OUT_PATH = REPO_ROOT / "output/osrm_nearest_active_feature.csv"


def load_fixed_matrix() -> pd.DataFrame:
    df = pd.read_csv(OSRM_PATH, index_col=0)
    row_noms = df["nom"].tolist()

    # verify the positional-mapping assumption before trusting it
    dest_cols = [c for c in df.columns if c != "nom"]
    diag = pd.Series([df.loc[df.index[i], dest_cols[i]] for i in range(len(row_noms))])
    if not (diag == 0).all():
        raise ValueError(
            "Self-distance is not 0 for every zone -- the positional column "
            "mapping assumption is broken, do not trust this rename."
        )

    df.columns = ["nom"] + row_noms  # positional fix, now verified

    aliases = pd.read_csv(ALIASES_PATH)
    alias_map = dict(zip(aliases["observed_name"], aliases["canonical_nom"]))
    df["nom"] = df["nom"].replace(alias_map)
    df.columns = ["nom"] + [alias_map.get(c, c) for c in df.columns[1:]]
    return df.set_index("nom")


def main():
    matrix = load_fixed_matrix()
    print("Matrix fixed and verified:", matrix.shape)

    sitrep = pd.read_csv(SITREP_PATH)
    sitrep["date"] = pd.to_datetime(sitrep["date"])

    active_by_date = (
        sitrep[sitrep["cumulative_suspected_cases"] > 0]
        .groupby("date")["nom"].apply(list)
    )
    print(f"Dates with at least one active zone: {len(active_by_date)}")

    records = []
    for date, active_zones in active_by_date.items():
        valid_active = [z for z in active_zones if z in matrix.columns]
        skipped = set(active_zones) - set(valid_active)
        if skipped:
            print(f"  !! {date.date()}: active zone(s) not found in matrix, skipped: {skipped}")
        if not valid_active:
            continue
        # exclude each zone from its OWN nearest-active-zone search --
        # without this, any zone that's already active trivially matches
        # itself at distance 0, which defeats the point of the feature
        # (measuring proximity to OTHER active zones, not "do I have any
        # case history at all"). Confirmed this bug affected 76/79 rows
        # (96%) before this fix.
        sub = matrix[valid_active].copy()
        for z in valid_active:
            if z in sub.index:
                sub.loc[z, z] = float("nan")
        min_time = sub.min(axis=1, skipna=True)
        for zone, t in min_time.items():
            records.append({"nom": zone, "date": date, "min_minutes_to_active_zone": t})

    result = pd.DataFrame(records)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_PATH, index=False)
    print(f"\nSaved: {OUT_PATH}")
    print("shape:", result.shape)


if __name__ == "__main__":
    main()