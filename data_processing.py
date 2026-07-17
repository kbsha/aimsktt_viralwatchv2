import os
import re
from pathlib import Path
import pandas as pd
import numpy as np

# --- Configuration Constants ---
COLUMN_TRANSLATIONS = {
    "date_notification": "date",
    "date_rapport": "date",
    "jour": "date",
    "zone_de_sante": "health_zone",
    "zone_sante": "health_zone",
    "nom_zone": "health_zone",
    "nom_sante": "health_zone",
    "nom": "health_zone",
    "province": "province",
    "cas_confirmes": "confirmed_cases",
    "cas_suspects": "suspected_cases",
    "deces": "deaths",
    "gueris": "recovered"
}

STATUS_TRANSLATIONS = {
    "oui": "yes", "non": "no", "vrai": "true", "faux": "false",
    "suspect": "suspected", "confirme": "confirmed", "decede": "deceased"
}

DROP_SUFFIXES = ("__static", ".matrix")
KEEP_FLOWMINDER_PREFIX = "flowminder_short_trips__"

# --- ML Trimming & Missingness Config ---
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
HIGH_MISSING_THRESHOLD = 0.70
TARGET_COL = "new_suspected_cases"
DROP_SECONDARY_COLS = [
    "new_contacts_listed", "cumulative_contacts_traced",
    "cumulative_confirmed_deaths", "new_suspected_deaths",
]


def remove_accents(series: pd.Series) -> pd.Series:
    """Standardizes text by stripping French accents and title-casing names."""
    return (series.astype(str)
            .str.normalize('NFKD')
            .str.encode('ascii', errors='ignore')
            .str.decode('utf-8')
            .str.strip()
            .str.title())


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Applies standard data cleaning and normalization to DataFrames."""
    if df.empty:
        return df
    df.columns = df.columns.str.lower().str.strip()
    df = df.rename(columns=COLUMN_TRANSLATIONS)
    
    zone_cols = [c for c in df.columns if 'zone' in c or 'health_zone' in c]
    if zone_cols:
        col = zone_cols[0]
        df[col] = df[col].astype(str).str.replace(r"(?i)zone de sant(e|é)\s*", "", regex=True)
        df[col] = remove_accents(df[col])
    
    prov_cols = [c for c in df.columns if 'province' in c]
    if prov_cols:
        col = prov_cols[0]
        df[col] = remove_accents(df[col])
    
    if 'date' in df.columns:
        df['date'] = df['date'].astype(str).str.replace(r'[\[\]\'"\s]', '', regex=True)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        if zone_cols:
            df = df.sort_values(by=[zone_cols[0], 'date'])
            
    for col in df.columns:
        if df[col].dtype == 'object' and col not in zone_cols and col not in prov_cols:
            cleaned_series = df[col].astype(str).str.lower().str.strip()
            cleaned_series = (cleaned_series.str.normalize('NFKD')
                              .str.encode('ascii', errors='ignore')
                              .str.decode('utf-8'))
            if cleaned_series.isin(STATUS_TRANSLATIONS.keys()).any():
                df[col] = cleaned_series.replace(STATUS_TRANSLATIONS).str.title()
                
    numeric_candidates = ['confirmed_cases', 'suspected_cases', 'deaths', 'recovered', 'cases', 'value', 'count', 'density']
    for col in df.columns:
        if col in numeric_candidates or df[col].astype(str).str.upper().isin(['ND', 'N/D', 'NULL']).any():
            df[col] = df[col].astype(str).replace(r'(?i)\b(nd|n/d|null|nan)\b', np.nan, regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def join_insp_sitrep_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    """Join all individual INSP SitRep CSV files on (nom, date) into a wide table."""
    input_dir = Path(input_dir)
    output_path = Path(output_path)

    csv_files = sorted(input_dir.glob("insp_sitrep*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No insp_sitrep*.csv files found in {input_dir}")

    frames: list[pd.DataFrame] = []
    skipped_files: list[str] = []

    for csv_path in csv_files:
        with csv_path.open("r", encoding="utf-8") as handle:
            first_line = handle.readline().strip().split(",")

        if len(first_line) >= 2 and first_line[0].strip().lower() == "nom" and first_line[1].strip().lower() == "date":
            df = pd.read_csv(csv_path)
        else:
            df = pd.read_csv(csv_path, header=None)
            if df.shape[1] >= 3:
                df = df.iloc[:, :3].copy()
                df.columns = ["nom", "date", "value"]
            else:
                print(f"Skipping {csv_path.name}: expected at least 3 columns")
                skipped_files.append(csv_path.name)
                continue

        if {"nom", "date"}.difference(df.columns):
            print(f"Skipping {csv_path.name}: missing required columns")
            skipped_files.append(csv_path.name)
            continue

        value_columns = [column for column in df.columns if column not in {"nom", "date"}]
        if len(value_columns) != 1:
            raise ValueError(f"{csv_path.name} must contain exactly one value column; found {value_columns}")

        metric_name = csv_path.stem.split("__")[1] if len(csv_path.stem.split("__")) >= 2 else value_columns[0]
        frame = df[["nom", "date", value_columns[0]]].copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame.rename(columns={value_columns[0]: metric_name}, inplace=True)
        frames.append(frame)

    if not frames:
        raise RuntimeError(f"No frames to merge. Skipped files: {skipped_files}")

    merged = frames[0]
    for frame in frames[1:]:
        merged = pd.merge(merged, frame, on=["nom", "date"], how="outer")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged


def _read_flowminder_frame(csv_path: Path) -> pd.DataFrame | None:
    """Read one Flowminder CSV as a two-column geography/value frame."""
    with csv_path.open("r", encoding="utf-8") as handle:
        first_line = handle.readline().strip().split(",")

    header_row = (
        len(first_line) >= 2
        and first_line[0].strip().lower() in {"nom", "zone_de_sante", "zone_sante", "zone"}
        and first_line[1].strip().lower() in {"value", "inflow", "outflow", "date"}
    )

    if header_row:
        frame = pd.read_csv(csv_path)
    else:
        frame = pd.read_csv(csv_path, header=None)
        if frame.shape[1] < 2:
            return None
        frame = frame.iloc[:, :2].copy()
        frame.columns = ["nom", "value"]

    if frame.shape[1] < 2:
        return None

    frame = frame.iloc[:, :2].copy()
    frame.columns = ["nom", "value"]
    return frame


def join_flowminder_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    """Join individual Flowminder CSVs on geographical key ('nom') into a wide DataFrame."""
    input_dir = Path(input_dir)
    output_path = Path(output_path)

    csv_files = sorted(input_dir.glob("flowminder*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No flowminder*.csv files found in {input_dir}")

    frames: list[pd.DataFrame] = []
    skipped_files: list[str] = []

    for csv_path in csv_files:
        frame = _read_flowminder_frame(csv_path)
        if frame is None:
            print(f"Skipping {csv_path.name}: expected at least 2 columns")
            skipped_files.append(csv_path.name)
            continue

        feature_name = csv_path.stem
        feature_frame = frame[["nom", "value"]].copy()
        feature_frame.rename(columns={"value": feature_name}, inplace=True)
        frames.append(feature_frame)

    if not frames:
        raise RuntimeError(f"No frames to merge. Skipped files: {skipped_files}")

    merged = frames[0]
    join_col = "nom"
    for frame in frames[1:]:
        merged = pd.merge(merged, frame, on=join_col, how="outer")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged


def load_fixed_matrix(osrm_path: Path, aliases_path: Path) -> pd.DataFrame:
    """Loads OSRM Matrix, applies positional diag-0 validation and resolves aliases."""
    df = pd.read_csv(osrm_path, index_col=0)
    row_noms = df["nom"].tolist()
    dest_cols = [c for c in df.columns if c != "nom"]
    
    diag = pd.Series([df.loc[df.index[i], dest_cols[i]] for i in range(len(row_noms))])
    if not (diag == 0).all():
         raise ValueError("Self-distance is not 0 for every zone! Positional columns alignment broken.")

    df.columns = ["nom"] + row_noms
    
    try:
        aliases = pd.read_csv(aliases_path)
        alias_map = dict(zip(aliases["observed_name"], aliases["canonical_nom"]))
        df["nom"] = df["nom"].replace(alias_map)
        df.columns = ["nom"] + [alias_map.get(c, c) for c in df.columns[1:]]
    except Exception as e:
        print(f"⚠️ Alias resolution skipped or failed: {e}")

    return df.set_index("nom")


def compute_osrm_nearest_active(osrm_path: Path, aliases_path: Path, sitrep_path: Path, out_path: Path) -> pd.DataFrame:
    """Calculates travel time from every zone to its nearest active-case counterpart."""
    matrix = load_fixed_matrix(osrm_path, aliases_path)
    sitrep = pd.read_csv(sitrep_path)
    sitrep["date"] = pd.to_datetime(sitrep["date"])

    active_by_date = (
        sitrep[sitrep["cumulative_suspected_cases"] > 0]
        .groupby("date")["nom"].apply(list)
    )

    records = []
    for date, active_zones in active_by_date.items():
        valid_active = [z for z in active_zones if z in matrix.columns]
        if not valid_active:
            continue
        min_time = matrix[valid_active].min(axis=1)
        for zone, t in min_time.items():
            records.append({"nom": zone, "date": date, "min_minutes_to_active_zone": t})

    result = pd.DataFrame(records)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_path, index=False)
    return result


def clean_and_merge_flowminder(flow_merged_path: Path, out_path: Path) -> pd.DataFrame:
    """Cleans Flowminder DataFrame by dropping static duplicated fields."""
    df = pd.read_csv(flow_merged_path)
    
    for col in df.columns:
        if col != "nom":
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
    keep_cols = ["nom"] + [
        c for c in df.columns
        if c.startswith(KEEP_FLOWMINDER_PREFIX) and not c.endswith(DROP_SUFFIXES)
    ]
    clean_df = df[keep_cols].copy()
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(out_path, index=False)
    return clean_df


def merge_worldpop(pop_count_path: Path, pop_density_path: Path, out_path: Path) -> pd.DataFrame:
    """Merges WorldPop count & density files."""
    df_count = pd.read_csv(pop_count_path, header=None, names=["nom", "pop_count"], encoding="utf-8-sig")
    df_density = pd.read_csv(pop_density_path, header=None, names=["nom", "pop_density"], encoding="utf-8-sig")
    
    merged = pd.merge(df_count, df_density, on="nom", how="outer")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)
    return merged


def create_training_table(sitrep_path: Path, osrm_path: Path, flow_path: Path, worldpop_path: Path, out_path: Path) -> pd.DataFrame:
    """Left-joins cleaned data features on sitrep's (nom, date) index anchor."""
    sitrep = pd.read_csv(sitrep_path, parse_dates=["date"])
    osrm = pd.read_csv(osrm_path, parse_dates=["date"])
    flow = pd.read_csv(flow_path)
    wp = pd.read_csv(worldpop_path)

    df = sitrep.merge(osrm, on=["nom", "date"], how="left")
    df = df.merge(flow, on="nom", how="left")
    df = df.merge(wp, on="nom", how="left")

    # Force "nom" (health zone) and "date" to be the first two columns
    first_cols = ["nom", "date"]
    remaining_cols = [col for col in df.columns if col not in first_cols]
    df = df[first_cols + remaining_cols]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return df


def trim_features(df: pd.DataFrame) -> pd.DataFrame:
    """Trims collinear/redundant and national summary features."""
    national_cols = [c for c in df.columns if c.startswith(NATIONAL_PREFIX)]
    all_drop = COLLINEAR_DROP_COLS + national_cols

    missing_from_df = [c for c in all_drop if c not in df.columns]
    if missing_from_df:
        raise ValueError(f"Expected columns not found: {missing_from_df}")

    return df.drop(columns=all_drop)


def handle_missingness(df: pd.DataFrame) -> pd.DataFrame:
    """Implements missingness cleanup, forward-fills, and specific-imputation strategies."""
    # 1. Drop highly sparse columns
    high_missing = df.isna().mean() > HIGH_MISSING_THRESHOLD
    drop_cols = high_missing[high_missing].index.tolist()
    df = df.drop(columns=drop_cols)

    # 2. Forward fill cumulative variables per zone
    cum_cols = [c for c in df.columns if c.startswith("cumulative_")]
    df = df.sort_values(["nom", "date"])
    df[cum_cols] = df.groupby("nom")[cum_cols].ffill()

    # 3. Drop rows missing the target variable
    df = df[df[TARGET_COL].notna()].copy()

    # 4. Drop minor operational variables
    present_secondary = [c for c in DROP_SECONDARY_COLS if c in df.columns]
    df = df.drop(columns=present_secondary)

    # 5. Impute Flowminder signal loss with 0
    flow_cols = [c for c in df.columns if c.startswith(KEEP_FLOWMINDER_PREFIX)]
    df[flow_cols] = df[flow_cols].fillna(0)

    # 6. Drop remaining NaN rows
    df = df.dropna()
    return df.sort_values("date", ascending=True)
