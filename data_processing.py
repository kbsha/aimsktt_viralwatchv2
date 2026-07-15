import os
import glob
import hashlib
import re
import pandas as pd
from sqlalchemy import create_engine, text

# 1. Fetch Aiven Connection String from Environment
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
    print("🔌 Connected successfully to your Cloud Aiven PostgreSQL database!")
else:
    engine = create_engine("sqlite:///data_test/viralwatch.db")
    print("📁 DATABASE_URL not found. Saving locally to data_test/viralwatch.db.")

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

    # Gather everything saved inside data_test
    all_files = glob.glob(os.path.join("data_test", "*"))
    processed_count = 0
    
    for file_path in all_files:
        filename = os.path.basename(file_path)
        name_lower = filename.lower()
        
        # Determine if file is targeted
        is_matched = (
            name_lower.startswith("insp") or
            name_lower.startswith("epi_cases") or
            name_lower.startswith("worldpop_") or
            name_lower.startswith("osrm_") or
            name_lower.startswith("cross_border") or
            name_lower.startswith("flowminder_short") or
            name_lower.startswith("grid3_healthsites") or
            name_lower.endswith(".shp")
        )
        
        if not is_matched:
            continue
            
        clean_name = (filename.lower()
                      .replace(".matrix.csv", "_matrix")
                      .replace(".csv", "")
                      .replace(".shp", "_shapefile")
                      .replace("__", "_")
                      .replace(".", "_")
                      .replace("-", "_"))
        
        # PostgreSQL limit safety: Truncate table names if they exceed 60 characters
        if len(clean_name) > 60:
            name_hash = hashlib.md5(clean_name.encode('utf-8')).hexdigest()[:6]
            clean_name = f"{clean_name[:50]}_{name_hash}"
        
        if any(name_lower.endswith(ext) for ext in [".shx", ".dbf", ".prj", ".cpg"]):
            continue

        print(f"📦 Re-building Table: '{clean_name}' from raw file...")
        
        try:
            if name_lower.endswith(".shp"):
                processed_df = process_shapefile(file_path)
            else:
                raw_df = pd.read_csv(file_path)
                processed_df = clean_dataframe(raw_df)
            
            # Standardize headers to lower_snake_case
            processed_df.columns = [clean_column_name(col) for col in processed_df.columns]
            
            # Save normal table to database
            processed_df.to_sql(clean_name, engine, if_exists='replace', index=False)
            print(f"✔ Table '{clean_name}' completely replaced.")
            processed_count += 1
            
        except Exception as e:
            print(f"❌ Failed to process '{filename}': {e}")
            
    print(f"🎉 Complete! All previous tables cleared; {processed_count} tables deployed successfully.")

if __name__ == "__main__":
    clean_and_sync()
