import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine

# 1. Fetch Aiven Connection String from Environment
DATABASE_URL = os.environ.get("DATABASE_URL")

# Set up SQL connection (Fallback to SQLite inside data_test/ if no cloud URL is configured)
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
    print("Connected successfully to your Cloud Aiven PostgreSQL database!")
else:
    engine = create_engine("sqlite:///data_test/viralwatch.db")
    print("DATABASE_URL not found. Saving locally to data_test/viralwatch.db.")

def clean_and_sync():
    print("Starting data cleaning and transformation...")
    
    # --- Table 1: Case Data & Rt Proxy ---
    cases_path = "data_test/BDBV2026_Cases_HA.csv"
    if os.path.exists(cases_path):
        df_cases = pd.read_csv(cases_path)
        
        # Clean columns and dates
        df_cases['date'] = pd.to_datetime(df_cases['date'])
        df_cases['health_zone'] = df_cases['health_zone'].str.strip().str.title()
        df_cases = df_cases.sort_values(by=['health_zone', 'date'])
        
        # Handle real-world downward case revisions
        df_cases['cumulative_cases'] = df_cases.groupby('health_zone')['cumulative_cases'].cummax()
        
        # Calculate Rolling 7-Day differences
        df_cases['new_cases_7d'] = df_cases.groupby('health_zone')['cumulative_cases'].diff(periods=7).fillna(0)
        df_cases['prev_cases_7d'] = df_cases.groupby('health_zone')['new_cases_7d'].shift(7).fillna(0)
        
        # Calculate Rt Proxy
        df_cases['rt_proxy'] = np.where(
            df_cases['prev_cases_7d'] > 0, 
            df_cases['new_cases_7d'] / df_cases['prev_cases_7d'], 
            0.0
        )
        
        # DB INSERTION 1: write to 'epidemic_trends'
        df_cases.to_sql('epidemic_trends', engine, if_exists='replace', index=False)
        print("✔ 'epidemic_trends' table written/updated in the database.")
    else:
        print("❌ Error: BDBV2026_Cases_HA.csv not found in data_test/")

    # --- Table 2: Static Covariates (IDP, CCVI, Mobility) ---
    covariate_files = {
        "idp_displacement.csv": "idp_displacement",
        "ccvi_vulnerability_index.csv": "ccvi_vulnerability",
        "flowminder_mobility.csv": "mobility_flows"
    }

    for csv_name, target_table in covariate_files.items():
        file_path = os.path.join("data_test", csv_name)
        if os.path.exists(file_path):
            df_cov = pd.read_csv(file_path)
            if 'health_zone' in df_cov.columns:
                df_cov['health_zone'] = df_cov['health_zone'].str.strip().str.title()
            
            # DB INSERTION 2: write to static tables
            df_cov.to_sql(target_table, engine, if_exists='replace', index=False)
            print(f"✔ '{target_table}' table written/updated in the database.")
        else:
            print(f"⚠️ Warning: {csv_name} not found in data_test/. Skipping table '{target_table}'.")

    print("🎉 Ingestion & Database sync complete!")

if __name__ == "__main__":
    clean_and_sync()
