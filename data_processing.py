import os
import re
import pandas as pd
import numpy as np

# Try to import geopandas for GIS files
try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

def remove_accents(series):
    """Strips French accents and title-cases names."""
    return (series.astype(str)
            .str.normalize('NFKD')
            .str.encode('ascii', errors='ignore')
            .str.decode('utf-8')
            .str.strip()
            .str.title())

def clean_dataframe(df):
    """Applies basic data cleaning and normalization to DataFrames."""
    # Convert headers to lowercase
    df.columns = df.columns.str.lower().str.strip()
    
    # Process & Standardize health_zone and province if present
    zone_cols = [c for c in df.columns if 'zone' in c or 'nom' in c]
    if zone_cols:
        col = zone_cols[0]
        df[col] = df[col].astype(str).str.replace(r"(?i)zone de sant(e|é)\s*", "", regex=True)
        df[col] = remove_accents(df[col])
    
    prov_cols = [c for c in df.columns if 'province' in c]
    if prov_cols:
        col = prov_cols[0]
        df[col] = remove_accents(df[col])

    return df

def process_shapefile(file_path):
    """Loads a shapefile using Geopandas."""
    if GEOPANDAS_AVAILABLE:
        print(f"🗺️ Spatial conversion: Reading {os.path.basename(file_path)}")
        gdf = gpd.read_file(file_path)
        if 'geometry' in gdf.columns:
            gdf['wkt_geometry'] = gdf['geometry'].apply(lambda geom: geom.wkt if geom else None)
            gdf = gdf.drop(columns=['geometry'])
        return clean_dataframe(pd.DataFrame(gdf))
    else:
        print("⚠️ Geopandas unavailable. Returning empty DataFrame.")
        return pd.DataFrame(columns=["health_zone", "province"])
