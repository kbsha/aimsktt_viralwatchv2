"""
Combined step 1 + 2: trim redundant/collinear features, then apply the
agreed missingness strategy, producing a fully complete (no-NaN) table
ready for the One-Class SVM.

=== STEP 1: trim redundant/collinear features ===
Only TRUE duplicates are dropped -- columns that are different
representations of the exact same underlying signal (r >= ~0.99, per
eda_correlation.py), not columns that are merely correlated but
conceptually distinct.

Groups collapsed, and which column was kept:
  - total_poe_hand_washing / passed / sanitised / screened (all r=1.0)
    -> kept total_poe_screened
  - total_poe_refused_hand_washing / refused_screening (r=1.0)
    -> kept total_poe_refused_screening
  - flowminder_short_trips__outflow_20260430/0507/0514/0521/0524
    (all r>=0.99 -- 5 dated snapshots of the same signal)
    -> kept the most recent, outflow_20260524
  - flowminder_short_trips__ituri_subscriber_days_prior/followup (r=0.998)
    -> kept followup (more recent)
  - flowminder_short_trips__nk_subscriber_days_prior/followup (r=0.994)
    -> kept followup (more recent)
Also drops the national_* leftover columns (structurally always-missing
in a zone-level table -- national totals only ever appeared on rows
already split into insp_sitrep_national_clean.csv).

=== STEP 2: missingness strategy ===
  1. Drop columns >70% missing -- too sparse to trust or usefully impute.
  2. Forward-fill cumulative_* columns per zone, ordered by date --
     matches INSP's own documented convention (carry the previous
     cumulative value forward when a day is ND).
  3. Drop rows where the target (new_suspected_cases) is missing -- the
     single biggest cut (218 -> 94 rows in testing). Cannot train on a
     missing target regardless of imputation strategy.
  4. Drop new_contacts_listed, cumulative_contacts_traced (secondary
     operational metrics) and cumulative_confirmed_deaths,
     new_suspected_deaths (tested dropping these columns vs. their rows
     -- dropping columns preserves 79 rows vs. 63; deaths aren't part of
     the core anomaly-detection signal and CFR is already covered
     separately by plot_insight_charts.py using the full-range file).
  5. Impute remaining Flowminder missingness with 0 -- defensible here
     specifically because missingness means "no measurable mobile-
     subscriber signal" (low cell-tower coverage zones).
  6. Drop any remaining rows with leftover NaN -- small final cleanup.

Usage:
    python prepare_final_table.py
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
IN_PATH = REPO_ROOT / "output" / "training_table.csv"
OUT_PATH = REPO_ROOT / "output" / "training_table_final.csv"

# --- step 1 config ---
COLLINEAR_DROP_COLS = [
    "total_poe_hand_washing", "total_poe_passed", "total_poe_sanitised",
    "total_poe_refused_hand_washing",
    "flowminder_short_trips__outflow_20260430",
    "flowminder_short_trips__outflow_20260507",
    "flowminder_short_trips__outflow_20260514",
    "flowminder_short_trips__outflow_20260521",
    "flowminder_short_trips__ituri_subscriber_days_prior_20260503",
    "flowminder_short_trips__nk_subscriber_days_prior_20260503",
]
NATIONAL_PREFIX = "national_"

# --- step 2 config ---
HIGH_MISSING_THRESHOLD = 0.70
TARGET_COL = "new_suspected_cases"
DROP_SECONDARY_COLS = [
    "new_contacts_listed", "cumulative_contacts_traced",
    "cumulative_confirmed_deaths", "new_suspected_deaths",
]
FLOWMINDER_PREFIX = "flowminder_short_trips__"


def trim_features(df: pd.DataFrame) -> pd.DataFrame:
    national_cols = [c for c in df.columns if c.startswith(NATIONAL_PREFIX)]
    all_drop = COLLINEAR_DROP_COLS + national_cols

    missing_from_df = [c for c in all_drop if c not in df.columns]
    if missing_from_df:
        raise ValueError(f"Expected columns not found -- check the table hasn't changed: {missing_from_df}")

    df = df.drop(columns=all_drop)
    print(f"[Step 1] Dropped {len(all_drop)} columns "
          f"({len(COLLINEAR_DROP_COLS)} collinear duplicates + {len(national_cols)} national leftovers)")
    print("[Step 1] shape:", df.shape)
    return df


def handle_missingness(df: pd.DataFrame) -> pd.DataFrame:
    high_missing = df.isna().mean() > HIGH_MISSING_THRESHOLD
    drop_cols = high_missing[high_missing].index.tolist()
    df = df.drop(columns=drop_cols)
    print(f"\n[Step 2.1] Dropped {len(drop_cols)} columns (>{HIGH_MISSING_THRESHOLD:.0%} missing): {drop_cols}")
    print("shape:", df.shape)

    cum_cols = [c for c in df.columns if c.startswith("cumulative_")]
    df = df.sort_values(["nom", "date"])
    df[cum_cols] = df.groupby("nom")[cum_cols].ffill()
    print(f"\n[Step 2.2] Forward-filled {len(cum_cols)} cumulative_* columns per zone")

    before = len(df)
    df = df[df[TARGET_COL].notna()].copy()
    print(f"\n[Step 2.3] Dropped rows with missing target ('{TARGET_COL}'): {before} -> {len(df)}")

    present_secondary = [c for c in DROP_SECONDARY_COLS if c in df.columns]
    df = df.drop(columns=present_secondary)
    print(f"\n[Step 2.4] Dropped secondary columns: {present_secondary}")

    flow_cols = [c for c in df.columns if c.startswith(FLOWMINDER_PREFIX)]
    n_filled = df[flow_cols].isna().sum().sum()
    df[flow_cols] = df[flow_cols].fillna(0)
    print(f"\n[Step 2.5] Imputed {n_filled} missing Flowminder values with 0 across {flow_cols}")

    before = len(df)
    remaining_missing = df.isna().sum()
    remaining_missing = remaining_missing[remaining_missing > 0]
    df = df.dropna()
    print(f"\n[Step 2.6] Final cleanup, dropped remaining NaN rows: {before} -> {len(df)}")
    if len(remaining_missing):
        print("  (columns with leftover missingness before this step):", remaining_missing.to_dict())

    return df


def main():
    df = pd.read_csv(IN_PATH, parse_dates=["date"])
    print("Loaded:", df.shape)

    df = trim_features(df)
    df = handle_missingness(df)
    df = df.sort_values("date", ascending=True) 
    df.to_csv(OUT_PATH, index=False)
    print(f"\nSaved: {OUT_PATH}")
    print("final shape:", df.shape)
    print("any NaN remaining?", df.isna().any().any())
    print("columns:", list(df.columns))


if __name__ == "__main__":
    main()
