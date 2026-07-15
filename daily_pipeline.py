import os
import glob
import hashlib
import re
import pandas as pd
from sqlalchemy import create_engine, text
from data_processing import clean_dataframe, process_shapefile

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
    Standardizes column headers globally to match exact patterns:
    nom, poesmean, daily_passengersmean, weekly_passengerspoe_names, count, density
    separating components strictly with a single underscore.
    """
    c = col.lower().strip()
    
    # Catch any geography/name columns and map them strictly to 'nom'
    if c in ['health_zone', 'nom_zone', 'nom', 'zone', 'zone_de_sante', 'zone_sante', 'nom_sante']:
        return 'nom'
    if 'weekly' in c or 'week' in c:
        return 'weekly_passengerspoe_names'
    if 'daily' in c or 'day' in c:
        return 'daily_passengersmean'
    if 'poes' in c or 'poe' in c:
        return 'poesmean'
    if 'density' in c:
        return 'density'
    if 'count' in c or 'pop' in c:
        return 'count'
        
    # Standard cleanup fallbacks
    c = re.sub(r'[^a-z0-9_]', '_', c)
    c = re.sub(r'_+', '_', c)
    return c.strip('_')

def reorder_columns(df):
    """
    Reorders a DataFrame to guarantee the ultimate ordering:
    1st: Geographic Keys (nom, province)
    2nd: Count / Flow columns (count, poesmean, daily_passengersmean, weekly_passengerspoe_names)
    3rd: Density columns (density)
    """
    cols = list(df.columns)
    
    # 1. Nom/Geographic Keys (prioritize 'nom' then 'province')
    key_cols = [c for c in ['nom', 'province'] if c in cols]
    # Fallback to catch other key-like columns just in case
    key_cols += [c for c in cols if c not in key_cols and ('zone' in c or 'province' in c)]
    
    # 2. Count / Flow / Metric Columns
    count_cols = [
        c for c in cols 
        if c not in key_cols and (
            'count' in c or 
            'mean' in c or 
            'passenger' in c or 
            'weekly' in c or 
            'daily' in c or
            'poes' in c
        )
    ]
    
    # 3. Density Columns
    density_cols = [c for c in cols if 'density' in c and c not in key_cols and c not in count_cols]
    
    # Remaining columns
    other_cols = [c for c in cols if c not in key_cols and c not in count_cols and c not in density_cols]
    
    # Strictly structured ordering
    ordered_cols = key_cols + count_cols + density_cols + other_cols
    return df[ordered_cols]

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
    
    # Structure to hold WorldPop files for merging
    worldpop_dfs = {"count": None, "density": None}
    
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

        # Dynamic Route: Group WorldPop Components
        if name_lower.startswith("worldpop_"):
            try:
                print(f"🌍 Reading WorldPop Component: '{filename}'")
                raw_df = pd.read_csv(file_path)
                processed_df = clean_dataframe(raw_df)
                
                if "density" in name_lower:
                    worldpop_dfs["density"] = processed_df
                else:
                    worldpop_dfs["count"] = processed_df
                continue 
            except Exception as e:
                print(f"❌ Failed to extract WorldPop segment '{filename}': {e}")
                continue

        print(f"📦 Re-building Table: '{clean_name}' from raw file...")
        
        try:
            if name_lower.endswith(".shp"):
                processed_df = process_shapefile(file_path)
            else:
                raw_df = pd.read_csv(file_path)
                processed_df = clean_dataframe(raw_df)
            
            # Special processing for individual crossborder files
            if name_lower.startswith("cross_border"):
                # 1. Clean and rename headers
                processed_df.columns = [clean_column_name(col) for col in processed_df.columns]
                # 2. Reorder columns using the standardized names
                processed_df = reorder_columns(processed_df)
            
            # Save normal table to database
            processed_df.to_sql(clean_name, engine, if_exists='replace', index=False)
            print(f"✔ Table '{clean_name}' completely replaced.")
            processed_count += 1
            
        except Exception as e:
            print(f"❌ Failed to process '{filename}': {e}")

    # ==========================================
    # Dynamic Join: Merge & Order WorldPop
    # ==========================================
    if worldpop_dfs["count"] is not None or worldpop_dfs["density"] is not None:
        try:
            print("🔗 Merging and formatting WorldPop dataframes...")
            
            # Clean component headers first to ensure keys match
            if worldpop_dfs["count"] is not None:
                worldpop_dfs["count"].columns = [clean_column_name(col) for col in worldpop_dfs["count"].columns]
            if worldpop_dfs["density"] is not None:
                worldpop_dfs["density"].columns = [clean_column_name(col) for col in worldpop_dfs["density"].columns]
            
            if worldpop_dfs["count"] is not None and worldpop_dfs["density"] is not None:
                common_keys = ['nom', 'province']
                # Safeguard if province is missing
                common_keys = [k for k in common_keys if k in worldpop_dfs["count"].columns and k in worldpop_dfs["density"].columns]
                if not common_keys:
                    common_keys = [worldpop_dfs["count"].columns[0]]
                
                merged_worldpop = pd.merge(
                    worldpop_dfs["count"], 
                    worldpop_dfs["density"], 
                    on=common_keys, 
                    how="outer", 
                    suffixes=('_count', '_density')
                )
            else:
                merged_worldpop = worldpop_dfs["count"] if worldpop_dfs["count"] is not None else worldpop_dfs["density"]
            
            # 1. Clean headers to standardize names first
            merged_worldpop.columns = [clean_column_name(col) for col in merged_worldpop.columns]
            # 2. Reorder columns so 'nom' is positioned first
            merged_worldpop = reorder_columns(merged_worldpop)
            
            merged_worldpop.to_sql("worldpop_nom_count_density", engine, if_exists='replace', index=False)
            print("✔ Table 'worldpop_nom_count_density' successfully built (correct columns ordered!).")
            processed_count += 1
        except Exception as e:
            print(f"❌ Failed to join combined WorldPop table: {e}")
            
    print(f"🎉 Complete! All previous tables cleared; {processed_count} tables deployed successfully.")

if __name__ == "__main__":
    clean_and_sync()
