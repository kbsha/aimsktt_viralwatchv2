import os
import re
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text, inspect

from data_processing import (
    clean_dataframe,
    join_insp_sitrep_csvs,
    join_flowminder_csvs,
    compute_osrm_nearest_active,
    clean_and_merge_flowminder,
    merge_worldpop,
    create_training_table,
    trim_features,
    handle_missingness
)

# --- Database Engine Setup ---
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine("sqlite:///viralwatch.db")


# --- Local Paths ---
DATA_REPO_DIR = Path("BDBV2026-Data")
BUILD_LONG_DIR = DATA_REPO_DIR / "build" / "long"
BUILD_DIR = DATA_REPO_DIR / "build"

# Source configurations
OSRM_PATH = BUILD_LONG_DIR / "osrm__travel_time.csv"
ALIASES_PATH = DATA_REPO_DIR / "data" / "aliases.csv"
WP_COUNT_PATH = BUILD_LONG_DIR / "worldpop__pop_count.csv"
WP_DENSITY_PATH = BUILD_LONG_DIR / "worldpop__pop_density.csv"


def clean_column_name(col):
    """Sanitizes columns to safe, standardized database snake_case."""
    c = col.lower().strip()
    c = re.sub(r'[^a-z0-9_]', '_', c)
    c = re.sub(r'_+', '_', c)
    return c.strip('_')


def run_pipeline():
    workspace_root = Path(".").resolve()
    output_dir = workspace_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. Compile INSP Sitreps ---
    print("⏳ Compiling INSP Sitreps...")
    try:
        merged_sitrep_path = output_dir / "insp_sitrep_merged.csv"
        raw_sitrep = join_insp_sitrep_csvs(BUILD_LONG_DIR, merged_sitrep_path)
        
        for col in raw_sitrep.columns:
            if col not in ["nom", "date"]:
                raw_sitrep[col] = raw_sitrep[col].replace("ND", pd.NA)
                raw_sitrep[col] = pd.to_numeric(raw_sitrep[col], errors="coerce")

        zone_rows = raw_sitrep[raw_sitrep["nom"].notna()].copy()
        zone_rows = zone_rows[zone_rows["date"].notna()].copy()
        zone_rows.to_csv(output_dir / "insp_sitrep_zone_level_clean.csv", index=False)

        training_df = zone_rows[(zone_rows["date"] >= "2026-05-14") & (zone_rows["date"] <= "2026-05-29")].copy()
        training_df.to_csv(output_dir / "insp_sitrep_training_window.csv", index=False)
        print("✅ INSP Sitrep compilation completed.")
    except Exception as e:
        print(f"❌ INSP Sitrep failed: {e}")

    # --- 2. Calculate OSRM Nearest Active ---
    print("⏳ Processing travel matrices...")
    try:
        sitrep_path = output_dir / "insp_sitrep_training_window.csv"
        out_osrm_path = output_dir / "osrm_nearest_active_feature.csv"
        
        if sitrep_path.exists():
            compute_osrm_nearest_active(OSRM_PATH, ALIASES_PATH, sitrep_path, out_osrm_path)
            print("✅ Travel metrics compiled.")
    except Exception as e:
        print(f"❌ Travel metric calculation failed: {e}")

    # --- 3. Clean and Merge Flowminder ---
    print("⏳ Processing Flowminder data...")
    try:
        merged_flowminder_path = output_dir / "flowminder_merged.csv"
        join_flowminder_csvs(BUILD_LONG_DIR, merged_flowminder_path)
        clean_and_merge_flowminder(merged_flowminder_path, output_dir / "flowminder_clean.csv")
        print("✅ Flowminder pipeline finished.")
    except Exception as e:
        print(f"❌ Flowminder pipeline failed: {e}")

    # --- 4. Merge WorldPop ---
    print("⏳ Merging WorldPop parameters...")
    try:
        merge_worldpop(WP_COUNT_PATH, WP_DENSITY_PATH, output_dir / "worldpop_merged.csv")
        print("✅ WorldPop configuration finished.")
    except Exception as e:
        print(f"❌ WorldPop merging failed: {e}")

    # --- 5. Generate and Clean ML-Ready Training Tables ---
    print("\n⏳ Building training datasets...")
    try:
        sit_p = output_dir / "insp_sitrep_training_window.csv"
        osrm_p = output_dir / "osrm_nearest_active_feature.csv"
        flow_p = output_dir / "flowminder_clean.csv"
        wp_p = output_dir / "worldpop_merged.csv"
        
        # A. Join features in memory (CSVs will already have "nom" and "date" first)
        raw_table_path = output_dir / "training_table.csv"
        df_raw = create_training_table(sit_p, osrm_p, flow_p, wp_p, raw_table_path)
        
        # B. Apply feature trimming and missingness handling
        df_trimmed = trim_features(df_raw)
        df_final = handle_missingness(df_trimmed)
        
        # Ensure final CSV has "nom" and "date" first
        final_table_path = output_dir / "training_table_final.csv"
        df_final = df_final[["nom", "date"] + [c for c in df_final.columns if c not in ["nom", "date"]]]
        df_final.to_csv(final_table_path, index=False)

        # Prepare Raw DataFrame for SQL ingestion
        raw_db = clean_dataframe(df_raw.copy())
        raw_db.columns = [clean_column_name(c) for c in raw_db.columns]
        
        # Force "health_zone" first, "date" second
        db_cols_raw = ["health_zone", "date"] + [c for c in raw_db.columns if c not in ["health_zone", "date"]]
        raw_db = raw_db[db_cols_raw]

        # Prepare Final DataFrame for SQL ingestion
        final_db = clean_dataframe(df_final.copy())
        final_db.columns = [clean_column_name(c) for c in final_db.columns]
        
        # Force "health_zone" first, "date" second
        db_cols_final = ["health_zone", "date"] + [c for c in final_db.columns if c not in ["health_zone", "date"]]
        final_db = final_db[db_cols_final]
        
        raw_table_name = "training_table_raw"
        final_table_name = "training_table_final"

        # C. Secure DB Upload (SMART TRUNCATE & APPEND BOTH TABLES)
        with engine.begin() as conn:
            inspector = inspect(engine)
            
            # --- 1. Handle Raw Table ---
            if inspector.has_table(raw_table_name):
                print(f"🧹 Truncating existing rows in `{raw_table_name}`...")
                conn.exec_driver_sql(f"TRUNCATE TABLE {raw_table_name};")
                if_exists_raw = "append"
            else:
                print(f"🆕 `{raw_table_name}` does not exist. Creating it fresh...")
                if_exists_raw = "replace"

            print(f"📥 Loading data into `{raw_table_name}`...")
            raw_db.to_sql(
                name=raw_table_name,
                con=conn,
                if_exists=if_exists_raw,
                index=False
            )

            # --- 2. Handle Final Table ---
            if inspector.has_table(final_table_name):
                print(f"🧹 Truncating existing rows in `{final_table_name}`...")
                conn.exec_driver_sql(f"TRUNCATE TABLE {final_table_name};")
                if_exists_final = "append"
            else:
                print(f"🆕 `{final_table_name}` does not exist. Creating it fresh...")
                if_exists_final = "replace"

            print(f"📥 Loading clean data into `{final_table_name}`...")
            final_db.to_sql(
                name=final_table_name,
                con=conn,
                if_exists=if_exists_final,
                index=False
            )
            
        print(f"💾 Successfully synchronized both SQL tables with customized column sequence!")
        print(f"✅ Success! Active training window contains {len(df_final)} validated data points.")

    except Exception as e:
        print(f"❌ Generating training data outputs failed: {e}")


if __name__ == "__main__":
    run_pipeline()
