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


def load_fixed_matrix(osrm_path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(osrm_path, index_col=0)
    
    if df.empty or (len(df.columns) < 2 and "version" in str(df.index[0])):
         raise ValueError("The resolved OSRM file is a Git LFS placeholder instead of real data.")

    row_noms = df["nom"].tolist()

    dest_cols = [c for c in df.columns if c != "nom"]
    diag = pd.Series([df.loc[df.index[i], dest_cols[i]] for i in range(len(row_noms))])
    if not (diag == 0).all():
        raise ValueError("Self-distance is not 0 for every zone!")

    df.columns = ["nom"] + row_noms
    return df.set_index("nom")


def compute_osrm_nearest_active(osrm_path: str | Path, sitrep_path: Path, out_path: Path = None) -> pd.DataFrame:
    matrix = load_fixed_matrix(osrm_path)
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
    
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(out_path, index=False)
        
    return result


def join_insp_sitrep_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    input_dir = Path(input_dir)
    output_path = Path(output_path)
    csv_files = sorted(input_dir.glob("insp_sitrep*.csv"))
    if not csv_files:
        return pd.DataFrame(columns=["nom", "date"])

    frames = []
    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path)
            df.columns = df.columns.str.lower().str.strip()
            cols_to_drop = [col for col in df.columns if col in ['unnamed: 0', 'index']]
            if cols_to_drop:
                df = df.drop(columns=cols_to_drop)

            rename_map = {}
            for col in df.columns:
                if col in ['nom', 'zone_sante', 'zone_de_sante', 'nom_zone', 'health_zone']:
                    rename_map[col] = 'nom'
                elif col in ['date', 'jour', 'date_rapport', 'date_notification']:
                    rename_map[col] = 'date'
            
            df = df.rename(columns=rename_map)
            if 'nom' not in df.columns and len(df.columns) > 0:
                df.rename(columns={df.columns[0]: 'nom'}, inplace=True)
            if 'date' not in df.columns and len(df.columns) > 1:
                df.rename(columns={df.columns[1]: 'date'}, inplace=True)

            if 'nom' not in df.columns or 'date' not in df.columns:
                continue

            df['date'] = df['date'].astype(str).str.strip()
            value_columns = [col for col in df.columns if col not in ['nom', 'date']]
            
            if not value_columns:
                df[f"has_data_{csv_path.stem}"] = 1
                value_columns = [f"has_data_{csv_path.stem}"]

            file_prefix = csv_path.stem.split("__")[1] if len(csv_path.stem.split("__")) >= 2 else csv_path.stem
            for col in value_columns:
                if col in ['value', 'cases', 'count', 'valeur', 'nd']:
                    df.rename(columns={col: file_prefix}, inplace=True)

            frames.append(df)
        except Exception as e:
            print(f"❌ Failed to parse {csv_path.name}: {e}")

    if not frames:
        return pd.DataFrame(columns=["nom", "date"])

    merged = frames[0]
    for i, frame in enumerate(frames[1:], start=1):
        merged = pd.merge(merged, frame, on=["nom", "date"], how="outer", suffixes=('', f'_dup_{i}'))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged


def join_flowminder_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    input_dir = Path(input_dir)
    output_path = Path(output_path)
    csv_files = sorted(input_dir.glob("flowminder*.csv"))
    if not csv_files:
        raise FileNotFoundError("No flowminder files.")

    frames = []
    for csv_path in csv_files:
        df = pd.read_csv(csv_path)
        df.columns = [str(c).lower().strip() for c in df.columns]
        geo_col = df.columns[0]
        val_col = df.columns[1] if len(df.columns) > 1 else None
        
        if val_col:
            df_clean = df[[geo_col, val_col]].copy()
            df_clean.columns = ["nom", csv_path.stem]
            frames.append(df_clean)

    if not frames:
        raise ValueError("No valid flowminder frames.")

    merged = frames[0]
    for frame in frames[1:]:
        merged = pd.merge(merged, frame, on="nom", how="outer")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged


def join_worldpop_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    input_dir = Path(input_dir)
    output_path = Path(output_path)
    all_csvs = list(input_dir.glob("*.csv"))
    
    count_file, density_file = None, None
    for f in all_csvs:
        name = f.name.lower()
        if "density" in name:
            density_file = f
        elif "count" in name:
            count_file = f

    def _extract_metric(file_path: Path, metric_name: str) -> pd.DataFrame:
        df = pd.read_csv(file_path)
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        geo_col = None
        for col in df.columns:
            if any(k in col for k in ["zone", "nom", "health", "sante"]):
                geo_col = col
                break
        if not geo_col:
            geo_col = df.columns[0]
            
        val_col = None
        for col in df.columns:
            if col != geo_col and any(k in col for k in ["value", "sum", "pop", "count", "density", "mean"]):
                val_col = col
                break
        if not val_col and len(df.columns) > 1:
            val_col = df.columns[1]

        if val_col:
            df_clean = df[[geo_col, val_col]].copy()
            df_clean.columns = ["nom", metric_name]
        else:
            df_clean = pd.DataFrame(columns=["nom", metric_name])
            df_clean["nom"] = df[geo_col]
            df_clean[metric_name] = np.nan
        return df_clean

    df_count = _extract_metric(count_file, "count") if count_file else pd.DataFrame(columns=["nom", "count"])
    df_density = _extract_metric(density_file, "density") if density_file else pd.DataFrame(columns=["nom", "density"])

    if not df_count.empty and not df_density.empty:
        merged = pd.merge(df_count, df_density, on="nom", how="outer")
    elif not df_count.empty:
        merged = df_count
        merged["density"] = np.nan
    else:
        merged = df_density
        merged["count"] = np.nan

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged
