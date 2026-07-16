import os
import glob
import hashlib
import re
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

# Safe explicit imports
from data_processing import clean_dataframe, join_insp_sitrep_csvs, join_flowminder_csvs, join_worldpop_csvs

# Fetch Connection String from Environment
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
    print("🔌 Connected successfully to your Cloud Aiven PostgreSQL database!")
else:
    engine = create_engine("sqlite:///viralwatch.db")
    print("📁 DATABASE_URL not found. Saving locally to viralwatch.db.")


def clean_column_name(col):
    """Standardizes column headers globally to lowercase separated by single underscores."""
    c = col.lower().strip()
    c = re.sub(r'[^a-z0-9_]', '_', c)
    c = re.sub(r'_+', '_', c)
    return c.strip('_')


def clean_and_sync():
    print("🔥 Starting complete database wipe-and-rebuild cycle...")
    
    if DATABASE_URL:
        try:
            with engine.begin() as conn:
                print("🧹 Dropping and recreating public schema...")
                conn.execute(text("DROP SCHEMA public CASCADE;"))
                conn.execute(text("CREATE SCHEMA public;"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
                print("✨ Schema successfully reset to empty!")
        except Exception as e:
            print(f"⚠️ Warning: Schema reset failed: {e}. Moving to standard table replacements.")

    # Determine raw data location dynamically
    data_dir = Path("data_test")
    if not data_dir.exists() or not any(data_dir.iterdir()):
        print("⚠️ 'data_test' directory not found or empty. Falling back to root workspace directory.")
        data_dir = Path(".")

    # --- 1. Zero-Loss Merge of individual INSP sitreps directly into PostgreSQL ---
    merged_insp_path = data_dir / "insp_sitrep_merged.csv"
    try:
        raw_insp_files = list(data_dir.glob("insp_sitrep*.csv"))
        if len(raw_insp_files) > 0:
            print("🔗 Merging all individual INSP sitrep CSVs into a single wide table...")
            merged_df = join_insp_sitrep_csvs(input_dir=data_dir, output_path=merged_insp_path)
            
            print("🚀 Uploading 'insp_sitrep_merged' directly to DB...")
            merged_df = clean_dataframe(merged_df)
            merged_df.columns = [clean_column_name(col) for col in merged_df.columns]
            
            # Intercept automated 'health_zone' translation back to exact 'nom' requirement
            if 'health_zone' in merged_df.columns:
                merged_df = merged_df.rename(columns={'health_zone': 'nom'})
            
            # Force 'nom' to be the first column in the DB output
            if 'nom' in merged_df.columns:
                cols = ['nom'] + [col for col in merged_df.columns if col != 'nom']
                merged_df = merged_df[cols]
            
            merged_df.to_sql(
                "insp_sitrep_merged", 
                engine, 
                if_exists='replace', 
                index=False,
                method='multi',
                chunksize=5000
            )
            print("✔ Table 'insp_sitrep_merged' successfully written to Database!")
        else:
            print("⚠️ No individual INSP files found to merge.")
    except Exception as e:
        print(f"❌ Critical INSP Merge failed: {e}")

    # --- 2. Flowminder Custom Aggregation Loop ---
    merged_flowminder_path = data_dir / "flowminder_merged.csv"
    try:
        raw_flowminder_files = list(data_dir.glob("flowminder*.csv"))
        if len(raw_flowminder_files) > 0:
            print("🔗 Custom aggregation on Flowminder files...")
            flow_df = join_flowminder_csvs(input_dir=data_dir, output_path=merged_flowminder_path)
            
            print("🚀 Uploading 'flowminder_merged' directly to DB...")
            flow_df = clean_dataframe(flow_df)
            flow_df.columns = [clean_column_name(col) for col in flow_df.columns]
            
            # Intercept automated 'health_zone' translation back to exact 'nom' requirement
            if 'health_zone' in flow_df.columns:
                flow_df = flow_df.rename(columns={'health_zone': 'nom'})
            
            # Force 'nom' to be the first column in the DB output
            if 'nom' in flow_df.columns:
                cols = ['nom'] + [col for col in flow_df.columns if col != 'nom']
                flow_df = flow_df[cols]
            
            flow_df.to_sql(
                "flowminder_merged", 
                engine, 
                if_exists='replace', 
                index=False,
                method='multi',
                chunksize=5000
            )
            print("✔ Table 'flowminder_merged' successfully written to Database!")
        else:
            print("⚠️ No Flowminder files found to merge.")
    except Exception as e:
        print(f"❌ Critical Flowminder Merge failed: {e}")

    # --- 3. WorldPop Custom Aggregation Loop ---
    merged_worldpop_path = data_dir / "worldpop_merged.csv"
    try:
        raw_worldpop_files = list(data_dir.glob("*worldpop*.csv"))
        if len(raw_worldpop_files) > 0:
            print("🔗 Custom aggregation on WorldPop files...")
            wp_df = join_worldpop_csvs(input_dir=data_dir, output_path=merged_worldpop_path)
            
            print("🚀 Uploading 'worldpop_merged' directly to DB...")
            wp_df = clean_dataframe(wp_df)
            wp_df.columns = [clean_column_name(col) for col in wp_df.columns]
            
            # Intercept automated 'health_zone' translation back to exact 'nom' requirement
            if 'health_zone' in wp_df.columns:
                wp_df = wp_df.rename(columns={'health_zone': 'nom'})
            
            # Force 'nom' to be the first column in the DB output
            if 'nom' in wp_df.columns:
                cols = ['nom'] + [col for col in wp_df.columns if col != 'nom']
                wp_df = wp_df[cols]
            
            wp_df.to_sql(
                "worldpop_merged", 
                engine, 
                if_exists='replace', 
                index=False,
                method='multi',
                chunksize=5000
            )
            print("✔ Table 'worldpop_merged' successfully written to Database!")
        else:
            print("⚠️ No WorldPop files found to merge.")
    except Exception as e:
        print(f"❌ Critical WorldPop Merge failed: {e}")

    # --- 4. Gather remaining files for standard DB sync ---
    all_files = glob.glob(os.path.join(str(data_dir), "*"))
    processed_count = 0
    
    print(f"📂 Scanning remaining files for standard uploads...")
    for file_path in all_files:
        filename = os.path.basename(file_path)
        name_lower = filename.lower()
        
        # Skip what is already merged or skipped
        if "insp_sitrep" in name_lower or "flowminder" in name_lower or "worldpop" in name_lower:
            continue
            
        # Flexible matching for other remaining tables (Skipping cross_border / grid3)
        is_matched = (
            "epi_cases" in name_lower or
            "osrm" in name_lower
        )
        
        if not is_matched:
            continue
            
        # Clean standard SQL table name
        clean_name = (filename.lower()
                      .replace(".matrix.csv", "_matrix")
                      .replace(".csv", "")
                      .replace("__", "_")
                      .replace(".", "_")
                      .replace("-", "_"))
        clean_name = re.sub(r'_+', '_', clean_name).strip('_')
        
        if len(clean_name) > 60:
            name_hash = hashlib.md5(clean_name.encode('utf-8')).hexdigest()[:6]
            clean_name = f"{clean_name[:50]}_{name_hash}"

        print(f"📦 Re-building Table: '{clean_name}' from raw file: '{filename}'...")
        
        try:
            raw_df = pd.read_csv(file_path)
            processed_df = clean_dataframe(raw_df)
            processed_df.columns = [clean_column_name(col) for col in processed_df.columns]
            
            # Intercept standard columns to match 'nom' first too if applicable
            if 'health_zone' in processed_df.columns:
                processed_df = processed_df.rename(columns={'health_zone': 'nom'})
                
            if 'nom' in processed_df.columns:
                cols = ['nom'] + [col for col in processed_df.columns if col != 'nom']
                processed_df = processed_df[cols]
            
            processed_df.to_sql(
                clean_name, 
                engine, 
                if_exists='replace', 
                index=False,
                method='multi',
                chunksize=5000
            )
            print(f"✔ Table '{clean_name}' completely replaced.")
            processed_count += 1
            
        except Exception as e:
            print(f"❌ Failed to process '{filename}': {e}")
            
    print(f"🎉 Complete! All database configurations synchronized safely.")

if __name__ == "__main__":
    clean_and_sync()
