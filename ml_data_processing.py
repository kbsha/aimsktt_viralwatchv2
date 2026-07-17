import os
import re
from pathlib import Path
import pandas as pd
import numpy as np

# --- Helper Normalization Rules (Consistent with data_processing.py) ---
def clean_text_column(series: pd.Series) -> pd.Series:
    """Removes stray brackets, quotes, normalized spaces, and title-cases names."""
    return (series.astype(str)
            .str.replace(r"[\[\]'\" ]", "", regex=True)
            .str.strip()
            .str.title())


def calculate_days_since_first_case(cases_df: pd.DataFrame) -> pd.DataFrame:
    """Calculates chronological days elapsed since a health zone logged its first case."""
    df = cases_df.copy()
    if df.shape[1] == 3:
        df.columns = ['health_zone', 'date', 'value']
    else:
        # Fallback if structure varies
        df.columns = ['health_zone', 'date', 'value'] + list(df.columns[3:])

    df['health_zone'] = clean_text_column(df['health_zone'])
    df['date'] = pd.to_datetime(df['date'].astype(str).str.replace(r"[\[\]'\" ]", "", regex=True), errors='coerce')
    df['value'] = pd.to_numeric(df['value'], errors='coerce').fillna(0).astype(int)
    
    # Identify dates where a positive confirmed case occurred
    positive_cases = df[df['value'] > 0]
    first_case_dates = positive_cases.groupby('health_zone')['date'].min().reset_index()
    first_case_dates.rename(columns={'date': 'first_case_date'}, inplace=True)
    
    df = pd.merge(df, first_case_dates, on='health_zone', how='left')
    
    # Compute relative days delta
    df['days_since_first_case'] = (df['date'] - df['first_case_date']).dt.days
    df['days_since_first_case'] = df['days_since_first_case'].fillna(0)
    df.loc[df['days_since_first_case'] < 0, 'days_since_first_case'] = 0
    df['days_since_first_case'] = df['days_since_first_case'].astype(int)
    
    df.drop(columns=['first_case_date'], inplace=True)
    return df


def load_population_density(filepath: Path | str) -> pd.DataFrame:
    """Loads and formats WorldPop density metrics safely."""
    df = pd.read_csv(filepath, header=None)
    
    if df.shape[1] == 3:
        df.columns = ['health_zone', 'date', 'pop_density']
        df = df[['health_zone', 'pop_density']].drop_duplicates()
    else:
        df.columns = ['health_zone', 'pop_density']
    
    df['health_zone'] = clean_text_column(df['health_zone'])
    df['pop_density'] = pd.to_numeric(df['pop_density'], errors='coerce').fillna(0)
    return df


def extract_distance_to_epicenter(matrix_filepath: Path | str, epicenter_name: str = "Bunia") -> pd.DataFrame:
    """Extracts positional travel time durations relative to a defined outbreak epicenter."""
    # Load wide-format matrix with the first column as index
    df_matrix = pd.read_csv(matrix_filepath, index_col=0)
    
    # Safely clean row index and column dimensions
    df_matrix.index = clean_text_column(pd.Series(df_matrix.index, index=df_matrix.index))
    df_matrix.columns = [clean_text_column(pd.Series([col])).iloc[0] for col in df_matrix.columns]
    
    epicenter_clean = epicenter_name.strip().title()
    if epicenter_clean in df_matrix.columns:
        # Reset the index to turn index labels into 'health_zone'
        df_distance = df_matrix[[epicenter_clean]].reset_index()
        df_distance.columns = ['health_zone', 'travel_time_to_epicenter']
    else:
        raise ValueError(f"Could not locate the epicenter column '{epicenter_clean}' inside the OSRM matrix.")
        
    return df_distance


def assemble_model_data(df_cases: pd.DataFrame, df_pop: pd.DataFrame, df_travel: pd.DataFrame) -> pd.DataFrame:
    """Left-joins temporal sitrep metrics with spatial population and travel boundaries."""
    master_df = df_cases.copy()
    master_df['health_zone'] = clean_text_column(master_df['health_zone'])
    
    master_df = pd.merge(master_df, df_pop, on='health_zone', how='left')
    master_df = pd.merge(master_df, df_travel, on='health_zone', how='left')
    
    master_df['pop_density'] = master_df['pop_density'].fillna(0)
    master_df['travel_time_to_epicenter'] = master_df['travel_time_to_epicenter'].fillna(-1)
    return master_df


def create_target_variable(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates forward looking window aggregations to binarize risk labels."""
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by=['health_zone', 'date']).reset_index(drop=True)
    
    # Extract absolute daily delta metric from cumulative baseline
    df['new_cases_today'] = df.groupby('health_zone')['value'].diff().fillna(0)
    df.loc[df['new_cases_today'] < 0, 'new_cases_today'] = 0 
    
    # Calculate case threshold counts over a 7-day rolling window
    df['cases_next_7_days'] = df.groupby('health_zone')['new_cases_today'].transform(
        lambda x: x.shift(-7).rolling(window=7, min_periods=1).sum()
    )
    
    # Binarize label: 1 implies outbreak confirmed, 0 implies dormant
    df['target_outbreak_next_7d'] = (df['cases_next_7_days'] > 0).astype(int)
    
    # Drop records that fall short of the forward looking window scope
    df = df.dropna(subset=['cases_next_7_days']).copy()
    df = df.drop(columns=['new_cases_today', 'cases_next_7_days'])
    return df
