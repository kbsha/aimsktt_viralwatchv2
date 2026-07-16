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
    force_nom_first,
    compute_osrm_nearest_active
)

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
    print("🔌 Connected successfully to your Cloud database!")
else:
    engine = create_engine("sqlite:///viralwatch.db")
    print("📁 DATABASE_URL not found. Saving locally to viralwatch.db.")


def clean_column_name(col):
    c = col.lower().strip()
    c = re.sub(r'[^a-z0-9_]', '_', c)
    c = re.sub(r'_+', '_', c)
    return c.strip('_')


def find_dbdv2026_root() -> Path:
    """
    Scans upwards and downwards from current path to locate 'BDBV2026-Data' directory.
    """
    current = Path(".").resolve()
    
    # Search upwards
    for parent in [current] + list(current.parents):
        for candidate_name in ["BDBV2026-Data", "DBDV2026-Data"]:
            candidate = parent / candidate_name
            if candidate.exists() and candidate.is_dir():
                return candidate
            
    # Search downwards
    for candidate_name in ["*BDBV2026-Data", "*DBDV2026-Data"]:
        for path in current.rglob(candidate_name):
            if path.is_dir():
                return path
            
    # Fallback default expectation
    return current / "data/external/BDBV2026-Data"


def find_path_fallback(target_filename: str, preferred_path: Path) -> Path:
    """If the target file is not at the preferred path, scan the project directory to find it."""
    if preferred_path.exists():
        return preferred_path
    
    # Deep search workspace
    for p in Path(".").resolve().rglob(target_filename):
        return p
        
    return preferred_path


def clean_and_sync():
    print("🔥 Starting database sync cycle...")
    
    if DATABASE_URL:
        try:
            with engine.begin() as conn:
                print("🧹 Dropping and recreating public schema...")
                conn.execute(text("DROP SCHEMA public CASCADE;"))
                conn.execute(text("CREATE SCHEMA public;"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        except Exception as e:
            print(f"⚠️ Schema reset warning: {e}")

    # Root location search for external data
    bdbv_root = find_dbdv2026_root()
    print(f"📁 Resolved BDBV2026-Data root directory at: {bdbv_root}")
    
    # Direct targeted path to build/matrix/osrm__travel_time__static.matrix.csv
    PREFERRED_OSRM_PATH = bdbv_root / "build/matrix/osrm__travel_time__static.matrix.csv"
    PREFERRED_ALIASES_PATH = bdbv_root / "data/aliases.csv"
    
    # Resolve absolute paths with dynamic fallbacks if folders are moved
    OSRM_PATH = find_path_fallback("osrm__travel_time__static.matrix.csv", PREFERRED_OSRM_PATH)
    ALIASES_PATH = find_path_fallback("aliases.csv", PREFERRED_ALIASES_PATH)
    
    # Locate training window sitrep
    workspace_root = Path(".").resolve()
    SITREP_PATH = find_path_fallback("insp_sitrep_training_window.csv", workspace_root / "output/insp_sitrep_training_window.csv")
    OUT_PATH = workspace_root / "output/osrm_nearest_active_feature.csv"
    
    data_dir = workspace_root / "data_test"
    if not data_dir.exists() or not any(data_dir.iterdir()):
        data_dir = workspace_root

    # --- 1. Custom OSRM Calculation Feature Generation & Upload ---
    print(f"🔎 OSRM Path: {OSRM_PATH} (Exists: {OSRM_PATH.exists()})")
    print(f"🔎 Aliases Path: {ALIASES_PATH} (Exists: {ALIASES_PATH.exists()})")
    print(f"🔎 Sitrep Path: {SITREP_PATH} (Exists: {SITREP_PATH.exists()})")
    
    try:
        if OSRM_PATH.exists() and ALIASES_PATH.exists() and SITREP_PATH.exists():
            print("🗺️ Running custom OSRM nearest active-zone calculation...")
            osrm_df = compute_osrm_nearest_active(OSRM_PATH, ALIASES_PATH, SITREP_PATH, OUT_PATH)
            
            # Post-Process for Database Injection (Force 'nom' First)
            osrm_df = clean_dataframe(osrm_df)
            osrm_df.columns = [clean_column_name(col) for col in osrm_df.columns]
            osrm_df = force_nom_first(osrm_df)
            
            print(f"📋 'osrm_nearest_active_feature' columns right before SQL: {list(osrm_df.columns)}")
            osrm_df.to_sql("osrm_nearest_active_feature", engine, if_exists='replace', index=False)
            print("✔ Custom table 'osrm_nearest_active_feature' successfully saved in DB!")
        else:
            print(f"❌ OSRM files or Sitrep missing. Skipped processing.")
    except Exception as e:
        print(f"❌ OSRM feature calculation or upload failed: {e}")

    # --- 2. INSP Merge ---
    try:
        if len(list(data_dir.glob("insp_sitrep*.csv"))) > 0:
            merged_df = join_insp_sitrep_csvs(input_dir=data_dir, output_path=data_dir / "insp_sitrep_merged.csv")
            merged_df = clean_dataframe(merged_df)
            merged_df.columns = [clean_column_name(col) for col in merged_df.columns]
            merged_df = force_nom_first(merged_df)
            
            print(f"📋 'insp_sitrep_merged' columns right before SQL: {list(merged_df.columns)}")
            merged_df.to_sql("insp_sitrep_merged", engine, if_exists='replace', index=False)
    except Exception as e:
        print(f"❌ INSP upload failed: {e}")

    # --- 3. Flowminder ---
    try:
        if len(list(data_dir.glob("flowminder*.csv"))) > 0:
            flow_df = join_flowminder_csvs(input_dir=data_dir, output_path=data_dir / "flowminder_merged.csv")
            flow_df = clean_dataframe(flow_df)
            flow_df.columns = [clean_column_name(col) for col in flow_df.columns]
            flow_df = force_nom_first(flow_df)
            
            print(f"📋 'flowminder_merged' columns right before SQL: {list(flow_df.columns)}")
            flow_df.to_sql("flowminder_merged", engine, if_exists='replace', index=False)
    except Exception as e:
        print(f"❌ Flowminder upload failed: {e}")

    # --- 4. WorldPop ---
    try:
        if len(list(data_dir.glob("*worldpop*.csv"))) > 0:
            wp_df = join_worldpop_csvs(input_dir=data_dir, output_path=data_dir / "worldpop_merged.csv")
            wp_df = clean_dataframe(wp_df)
            wp_df.columns = [clean_column_name(col) for col in wp_df.columns]
            wp_df = force_nom_first(wp_df)
            
            print(f"📋 'worldpop_merged' columns right before SQL: {list(wp_df.columns)}")
            wp_df.to_sql("worldpop_merged", engine, if_exists='replace', index=False)
    except Exception as e:
        print(f"❌ WorldPop upload failed: {e}")

    print("🎉 Sync completed successfully!")

if __name__ == "__main__":
    clean_and_sync()
