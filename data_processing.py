import os
import glob
import hashlib
import re
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from data_processing import clean_dataframe, join_insp_sitrep_csvs

# 1. Fetch Connection String from Environment
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
    """
    Standardizes column headers globally to lowercase separated by single underscores.
    """
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

    # --- 2. Determine raw data location dynamically ---
    data_dir = Path("data_test")
    if not data_dir.exists() or not any(data_dir.iterdir()):
        print("⚠️ 'data_test' directory not found or empty. Falling back to root workspace directory.")
        data_dir = Path(".")

    # --- 3. Zero-Loss Merge of individual INSP sitreps directly into PostgreSQL ---
    merged_output_path = data_dir / "insp_sitrep_merged.csv"
    
    try:
        print(f"🔗 Searching for INSP files in: {data_dir.resolve()}")
        raw_insp_files = list(data_dir.glob("insp_sitrep*.csv"))
        print(f"found raw INSP files: {[f.name for f in raw_insp_files]}")

        if len(raw_insp_files) > 0:
            print("🔗 Merging all individual INSP sitrep CSVs into a single wide table...")
            merged_df = join_insp_sitrep_csvs(input_dir=data_dir, output_path=merged_output_path)
            
            # Clean columns and insert directly here!
            print("🚀 Uploading 'insp_sitrep_merged' directly to DB...")
            merged_df = clean_dataframe(merged_df)
            merged_df.columns = [clean_column_name(col) for col in merged_df.columns]
            
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
        print(f"❌ Critical Merge / Upload failed: {e}")

    # 4. Gather files for standard DB sync (Skipping GRID3 and Cross Border)
    all_files = glob.glob(os.path.join(str(data_dir), "*"))
    processed_count = 0
    
    print(f"📂 Scanning files for regular uploads in {data_dir.resolve()}...")
    for file_path in all_files:
        filename = os.path.basename(file_path)
        name_lower = filename.lower()
        
        # Skip raw individual sitreps (we already merged them!)
        if name_lower.startswith("insp_sitrep__") and name_lower != "insp_sitrep_merged.csv":
            continue
            
        # Skip all shapefiles and spatial helper files completely
        if any(name_lower.endswith(ext) for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]):
            continue
            
        # Flexible substring matching - Removed 'grid3' and 'cross_border'
        is_matched = (
            "worldpop" in name_lower or
            "epi_cases" in name_lower or
            "osrm" in name_lower or
            "flowminder" in name_lower
        )
        
        if not is_matched:
            continue
            
        # Format clean, SQL-friendly table names
        clean_name = (filename.lower()
                      .replace(".matrix.csv", "_matrix")
                      .replace(".csv", "")
                      .replace("__", "_")
                      .replace(".", "_")
                      .replace("-", "_"))
        
        clean_name = re.sub(r'_+', '_', clean_name).strip('_')
        
        # PostgreSQL safety: Truncate table names if they exceed 60 characters
        if len(clean_name) > 60:
            name_hash = hashlib.md5(clean_name.encode('utf-8')).hexdigest()[:6]
            clean_name = f"{clean_name[:50]}_{name_hash}"

        print(f"📦 Re-building Table: '{clean_name}' from raw file: '{filename}'...")
        
        try:
            raw_df = pd.read_csv(file_path)
            processed_df = clean_dataframe(raw_df)
            
            # Standardize headers to lower_snake_case
            processed_df.columns = [clean_column_name(col) for col in processed_df.columns]
            
            # Save normal table to database using optimized batched inserting
            print(f"🚀 Uploading {len(processed_df)} rows to '{clean_name}'...")
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
            
    print(f"🎉 Complete! All matching non-spatial tables processed; {processed_count} extra tables deployed successfully.")

if __name__ == "__main__":
    clean_and_sync()
