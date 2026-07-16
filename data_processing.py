import os
import re
from pathlib import Path
import pandas as pd
import numpy as np

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
                
    numeric_candidates = ['confirmed_cases', 'suspected_cases', 'deaths', 'recovered', 'cases', 'value']
    for col in df.columns:
        if col in numeric_candidates or df[col].astype(str).str.upper().isin(['ND', 'N/D', 'NULL']).any():
            df[col] = df[col].astype(str).replace(r'(?i)\b(nd|n/d|null|nan)\b', np.nan, regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df

def join_insp_sitrep_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    """
    Join all INSP SitRep CSV files on (nom, date) into a wide table.

    Each file contributes one metric column, named after the filename.
    Missing combinations remain as NaN.
    """
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
    """Join Flowminder files on geography key ('nom') to build a wide table with 'nom' first."""
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

    # Force 'nom' to be the first column
    cols = ['nom'] + [col for col in merged.columns if col != 'nom']
    merged = merged[cols]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged


def join_worldpop_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    """
    Finds WorldPop files (by looking for 'count' and 'density' in the filenames)
    and merges them into a single wide table. Force-orders 'nom' as the first column.
    """
    input_dir = Path(input_dir)
    output_path = Path(output_path)

    # Grab all CSV files in the folder
    all_csvs = list(input_dir.glob("*.csv"))
    
    count_file = None
    density_file = None

    # Search explicitly for "count" and "density" in filenames
    for f in all_csvs:
        name_lower = f.name.lower()
        if "density" in name_lower:
            density_file = f
        elif "count" in name_lower:
            count_file = f

    if not count_file and not density_file:
        raise FileNotFoundError(
            f"Could not locate WorldPop files in '{input_dir}'. "
            f"Expected one file with 'count' and one with 'density' in the filename."
        )

    def _extract_metric(file_path: Path, metric_name: str) -> pd.DataFrame:
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.lower().str.strip()
        
        # 1. Detect geography column ('nom' or 'zone')
        geo_col = None
        for col in df.columns:
            if any(k in col for k in ["zone", "nom", "health", "sante"]):
                geo_col = col
                break
        if not geo_col:
            geo_col = df.columns[0]  # Fallback to 1st column
            
        # 2. Detect numeric value column
        val_col = None
        for col in df.columns:
            if col != geo_col and any(k in col for k in ["value", "sum", "pop", "count", "density", "mean"]):
                val_col = col
                break
        if not val_col:
            remaining = [c for c in df.columns if c != geo_col]
            val_col = remaining[0] if remaining else None

        # 3. Build standardized DataFrame with clean headers
        if val_col:
            df_clean = df[[geo_col, val_col]].copy()
            df_clean.columns = ["nom", metric_name]
        else:
            df_clean = df[[geo_col]].copy()
            df_clean.columns = ["nom"]
            df_clean[metric_name] = np.nan
            
        return df_clean

    # Safely load the datasets
    df_count = _extract_metric(count_file, "count") if count_file else pd.DataFrame(columns=["nom", "count"])
    df_density = _extract_metric(density_file, "density") if density_file else pd.DataFrame(columns=["nom", "density"])

    # Perform outer merge
    if not df_count.empty and not df_density.empty:
        merged = pd.merge(df_count, df_density, on="nom", how="outer")
    elif not df_count.empty:
        merged = df_count
        merged["density"] = np.nan
    else:
        merged = df_density
        merged["count"] = np.nan

    # Force 'nom' to be the first column
    cols = ['nom'] + [col for col in merged.columns if col != 'nom']
    merged = merged[cols]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    print(f"💾 Merged WorldPop table created successfully at: {output_path}")
    
    return merged
