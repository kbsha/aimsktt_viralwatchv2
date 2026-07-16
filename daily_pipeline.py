import os
import glob
import hashlib
import re
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

from data_processing import (
    clean_dataframe, 
    join_insp_sitrep_csvs, 
    join_flowminder_csvs, 
    join_worldpop_csvs, 
    compute_osrm_nearest_active
)

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine("sqlite:///viralwatch.db")


def clean_column_name(col):
    c = col.lower().strip()
    c = re.sub(r'[^a-z0-9_]', '_', c)
    c = re.sub(r'_+', '_', c)
    return c.strip('_')


def find_path_fallback(target_filename: str, preferred_path: Path) -> Path:
    if preferred_path.exists():
        return preferred_path
    
    workspace_root = Path(".").resolve()
    for parent in [workspace_root] + list(workspace_root.parents):
        for p in parent.rglob(target_filename):
            if p.is_file():
                return p
                
    return preferred_path


def clean_and_sync():
    if DATABASE_URL:
        try:
            with engine.begin() as conn:
                conn.execute(text("DROP SCHEMA public CASCADE;"))
                conn.execute(text("CREATE SCHEMA public;"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        except Exception:
            pass

    # Remote OSRM URL
    OSRM_PATH = "https://raw.githubusercontent.com/INRB-UMIE/BDBV2026-Data/main/build/matrix/osrm__travel_time__static.matrix.csv"
    
    workspace_root = Path(".").resolve()
    
    # Establish data_test as the directory for all local read/write operations
    data_dir = workspace_root / "data_test"
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)

    # 1. We look for the input sitrep file directly inside data_test/
    SITREP_PATH = find_path_fallback("insp_sitrep_training_window.csv", data_dir / "insp_sitrep_training_window.csv")
    
    # 2. We save the output features directly inside data_test/
    OUT_PATH = data_dir / "osrm_nearest_active_feature.csv"

    # --- 1. Custom OSRM Calculation Feature Generation & DB Upload ---
    try:
        if SITREP_PATH.exists():
            osrm_df = compute_osrm_nearest_active(OSRM_PATH, SITREP_PATH, OUT_PATH)
            
            # Post-Process & Normalize Columns
            osrm_df = clean_dataframe(osrm_df)
            osrm_df.columns = [clean_column_name(col) for col in osrm_df.columns]
            
            # Direct Write straight to Database
            osrm_df.to_sql("osrm_nearest_active_feature", engine, if_exists='replace', index=False)
    except Exception as e:
        print(f"❌ OSRM upload failed: {e}")

    # --- 2. INSP Merge ---
    try:
        if len(list(data_dir.glob("insp_sitrep*.csv"))) > 0:
            merged_df = join_insp_sitrep_csvs(input_dir=data_dir, output_path=data_dir / "insp_sitrep_merged.csv")
            merged_df = clean_dataframe(merged_df)
            merged_df.columns = [clean_column_name(col) for col in merged_df.columns]
            
            merged_df.to_sql("insp_sitrep_merged", engine, if_exists='replace', index=False)
    except Exception as e:
        print(f"❌ INSP upload failed: {e}")

    # --- 3. Flowminder ---
    try:
        if len(list(data_dir.glob("flowminder*.csv"))) > 0:
            flow_df = join_flowminder_csvs(input_dir=data_dir, output_path=data_dir / "flowminder_merged.csv")
            flow_df = clean_dataframe(flow_df)
            flow_df.columns = [clean_column_name(col) for col in flow_df.columns]
            
            flow_df.to_sql("flowminder_merged", engine, if_exists='replace', index=False)
    except Exception as e:
        print(f"❌ Flowminder upload failed: {e}")

    # --- 4. WorldPop ---
    try:
        if len(list(data_dir.glob("*worldpop*.csv"))) > 0:
            wp_df = join_worldpop_csvs(input_dir=data_dir, output_path=data_dir / "worldpop_merged.csv")
            wp_df = clean_dataframe(wp_df)
            wp_df.columns = [clean_column_name(col) for col in wp_df.columns]

            wp_df.to_sql("worldpop_merged", engine, if_exists='replace', index=False)
    except Exception as err:
        print(f"❌ WorldPop upload failed: {err}")


if __name__ == "__main__":
    clean_and_sync()
