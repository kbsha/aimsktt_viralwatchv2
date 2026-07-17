import pandas as pd
import numpy as np


def load_population_density(filepath):
    df = pd.read_csv(filepath, header=None)
    
    if df.shape[1] == 3:
        df.columns = ['health_zone', 'date', 'pop_density']
        df = df[['health_zone', 'pop_density']].drop_duplicates()
    else:
        df.columns = ['health_zone', 'pop_density']
    

    df['health_zone'] = df['health_zone'].astype(str).str.strip("[]'\" ")
    df['pop_density'] = df['pop_density'].astype(str).str.strip("[]'\" ")
   
    df['pop_density'] = pd.to_numeric(df['pop_density'], errors='coerce').fillna(0)
    
    return df


def extract_distance_to_epicenter(matrix_filepath, epicenter_name="Bunia"):
    # Load matrix (first column is index, first row is headers)
    df_matrix = pd.read_csv(matrix_filepath, index_col=0)
    
    # Clean the index (origins) and columns (destinations) just in case they have brackets
    df_matrix.index = df_matrix.index.astype(str).str.strip("[]'\" ")
    df_matrix.columns = df_matrix.columns.astype(str).str.strip("[]'\" ")
    
    if epicenter_name in df_matrix.columns:
        df_distance = df_matrix[[epicenter_name]].reset_index()
        df_distance.columns = ['health_zone', 'travel_time_to_epicenter']
    else:
        raise ValueError(f"Could not find '{epicenter_name}' in the matrix columns.")
        
    return df_distance

# ==========================================
# 3. DATASET ASSEMBLER
# ==========================================
def assemble_master_dataset(df_cases, df_pop, df_travel):
    master_df = df_cases.copy()
    
    # Clean the base cases health_zone column to ensure a perfect match during merge
    master_df['health_zone'] = master_df['health_zone'].astype(str).str.strip("[]'\" ")
    
    # Merge Population & Travel Time
    master_df = pd.merge(master_df, df_pop, on='health_zone', how='left')
    master_df = pd.merge(master_df, df_travel, on='health_zone', how='left')
    
    # Fill missing static data (e.g., if a zone wasn't in the travel matrix)
    master_df['pop_density'] = master_df['pop_density'].fillna(0)
    master_df['travel_time_to_epicenter'] = master_df['travel_time_to_epicenter'].fillna(-1)
    
    return master_df

# ==========================================
# 4. TARGET VARIABLE CREATOR (ML LABELS)
# ==========================================
def create_target_variable(df):
    # Ensure data is sorted chronologically for each zone
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by=['health_zone', 'date']).reset_index(drop=True)
    
    # Calculate daily NEW cases (since 'value' is cumulative)
    df['new_cases_today'] = df.groupby('health_zone')['value'].diff().fillna(0)
    df.loc[df['new_cases_today'] < 0, 'new_cases_today'] = 0 
    
    # Look ahead 7 days to sum upcoming cases
    df['cases_next_7_days'] = df.groupby('health_zone')['new_cases_today'].transform(
        lambda x: x.shift(-7).rolling(window=7, min_periods=1).sum()
    )
    
    # Binarize the target: 1 if there will be cases, 0 if not
    df['target_outbreak_next_7d'] = (df['cases_next_7_days'] > 0).astype(int)
    
    # Drop rows at the very end of the timeline where we can't look 7 days into the future
    df = df.dropna(subset=['cases_next_7_days']).copy()
    
    # Drop intermediate columns used for calculation to keep the final dataset clean
    df = df.drop(columns=['new_cases_today', 'cases_next_7_days'])
    
    return df

# ==========================================
# 5. EXECUTION BLOCK
# ==========================================
if __name__ == "__main__":
    # Define your file paths based on your previous scripts
    base_dir = r"C:\Users\STUDENT\OneDrive\Desktop\KTT Fellowship\ViralWatch Project\aimsktt_viralwatch\ml\dataset"
    
    cases_filepath = rf"{base_dir}\days_since_first_case.csv"
    pop_filepath = rf"{base_dir}\worldpop__pop_density.csv"
    matrix_filepath = rf"{base_dir}\osrm__travel_time__static.matrix.csv"
    output_filepath = rf"{base_dir}\final_ml_training_dataset.csv"
    
    print("1. Loading datasets...")
    # Load the base dataset you created in the last step
    df_cases = pd.read_csv(cases_filepath)
    df_pop = load_population_density(pop_filepath)
    df_travel = extract_distance_to_epicenter(matrix_filepath, epicenter_name="Bunia")
    
    print("2. Assembling master dataset...")
    master_df = assemble_master_dataset(df_cases, df_pop, df_travel)
    
    print("3. Creating 7-day target variable...")
    final_df = create_target_variable(master_df)
    
    print("4. Saving final dataset...")
    final_df.to_csv(output_filepath, index=False)
    
    print(f"\nSuccess! Your ML training dataset is ready at:\n{output_filepath}")
    print("\nPreview of the final dataset:")
    print(final_df[['health_zone', 'date', 'value', 'days_since_first_case', 'target_outbreak_next_7d']].head(10))