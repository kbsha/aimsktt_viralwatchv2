import os
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
    df_matrix = pd.read_csv(matrix_filepath, index_col=0)
    
    df_matrix.index = df_matrix.index.astype(str).str.strip("[]'\" ")
    df_matrix.columns = df_matrix.columns.astype(str).str.strip("[]'\" ")
    
    if epicenter_name in df_matrix.columns:
        df_distance = df_matrix[[epicenter_name]].reset_index()
        df_distance.columns = ['health_zone', 'travel_time_to_epicenter']
    else:
        raise ValueError(f"Could not find '{epicenter_name}' in the matrix columns.")
        
    return df_distance


def load_and_clean_sitrep_file(filepath, value_column_name):
    """
    Loads an INSP sitrep CSV, cleans the health_zone strings, 
    standardizes dates, and renames the cumulative 'value' column.
    """
    df = pd.read_csv(filepath)
    
    # Standardize column names
    df.columns = [col.lower().strip() for col in df.columns]
    
    # Clean text columns
    df['health_zone'] = df['health_zone'].astype(str).str.strip("[]'\" ")
    
    # ---------------------------------------------------------
    # THE FIX: Clean the date string before parsing it
    # ---------------------------------------------------------
    df['date'] = df['date'].astype(str).str.strip("[]'\" ")
    
    # Use format='mixed' and dayfirst=True to silence the warning and parse safely
    df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=True, errors='coerce')
    
    # Clean and rename value column
    df[value_column_name] = pd.to_numeric(df['value'], errors='coerce').fillna(0)
    
    # Keep only what we need to merge
    return df[['health_zone', 'date', value_column_name]]



def assemble_master_dataset(df_cases, df_pop, df_travel, additional_dfs):
    master_df = df_cases.copy()
    
    # Clean baseline health_zone & date
    master_df['health_zone'] = master_df['health_zone'].astype(str).str.strip("[]'\" ")
    master_df['date'] = pd.to_datetime(master_df['date'])
    
    # 1. Merge all the new dynamic time-series features on BOTH health_zone and date
    for col_name, df_feature in additional_dfs.items():
        print(f"   [+] Merging dynamic feature: {col_name}...")
        master_df = pd.merge(master_df, df_feature, on=['health_zone', 'date'], how='left')
        master_df[col_name] = master_df[col_name].fillna(0)
    
    # 2. Merge static Population & Travel Time on health_zone only
    print("   [+] Merging static geographic features...")
    master_df = pd.merge(master_df, df_pop, on='health_zone', how='left')
    master_df = pd.merge(master_df, df_travel, on='health_zone', how='left')
    
    # Fill missing static data
    master_df['pop_density'] = master_df['pop_density'].fillna(0)
    master_df['travel_time_to_epicenter'] = master_df['travel_time_to_epicenter'].fillna(-1)
    if 'value' in master_df.columns:
        master_df = master_df.drop(columns=['value'])
        
    return master_df
    


# ==========================================
# 3. TARGET VARIABLE CREATOR (ML LABELS)
# ==========================================
def create_target_variable(df):
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by=['health_zone', 'date']).reset_index(drop=True)
    
    # Calculate daily NEW cases (since 'cumulative_confirmed_cases' is cumulative)
    df['new_cases_today'] = df.groupby('health_zone')['cumulative_confirmed_cases'].diff().fillna(0)
    df.loc[df['new_cases_today'] < 0, 'new_cases_today'] = 0 
    
    # Look ahead 7 days to sum upcoming cases
    df['cases_next_7_days'] = df.groupby('health_zone')['new_cases_today'].transform(
        lambda x: x.shift(-7).rolling(window=7, min_periods=1).sum()
    )
    
    # Binarize target
    df['target_outbreak_next_7d'] = (df['cases_next_7_days'] > 0).astype(int)
    
    # Drop rows at the end where we can't look 7 days ahead
    df = df.dropna(subset=['cases_next_7_days']).copy()
    df = df.drop(columns=['new_cases_today', 'cases_next_7_days'])
    
    return df



if __name__ == "__main__":
    # If running in Google Colab, change this to your folder path, e.g., "/content/"
    base_dir = "/content/aimsktt_viralwatch/ml/dataset"
    
    # Define file paths
    days_since_filepath = os.path.join(base_dir, "days_since_first_case.csv")
    pop_filepath = os.path.join(base_dir, "worldpop__pop_density.csv")
    matrix_filepath = os.path.join(base_dir, "osrm__travel_time__static.matrix.csv")
    output_filepath = os.path.join(base_dir, "final_ml_training_dataset.csv")
    
    print("1. Loading static and baseline datasets...")
    df_cases = pd.read_csv(days_since_filepath)
    df_pop = load_population_density(pop_filepath)
    df_travel = extract_distance_to_epicenter(matrix_filepath, epicenter_name="Bunia")
    
    # 2. Define and load all the new time-series feature files
    print("2. Loading and cleaning new sitrep feature files...")
    additional_features = {
        "cumulative_confirmed_cases": os.path.join(base_dir, "insp_sitrep__cumulative_confirmed_cases.csv"),
        "cumulative_confirmed_deaths": os.path.join(base_dir, "insp_sitrep__cumulative_confirmed_deaths.csv"),
        "cumulative_contacts_isolated": os.path.join(base_dir, "insp_sitrep__cumulative_contacts_isolated.csv"),
        "cumulative_contacts_traced": os.path.join(base_dir, "insp_sitrep__cumulative_contacts_traced.csv"),
        "cumulative_suspected_cases": os.path.join(base_dir, "insp_sitrep__cumulative_suspected_cases.csv"),
        "cumulative_suspected_deaths": os.path.join(base_dir, "insp_sitrep__cumulative_suspected_deaths.csv")
    }
    
    loaded_features = {}
    for column_name, file_path in additional_features.items():
        if os.path.exists(file_path):
            loaded_features[column_name] = load_and_clean_sitrep_file(file_path, column_name)
        else:
            print(f"   [!] Warning: Could not find {file_path}. Skipping.")

    print("3. Assembling master dataset with new features...")
    master_df = assemble_master_dataset(df_cases, df_pop, df_travel, loaded_features)
    
    print("4. Creating 7-day target variable...")
    final_df = create_target_variable(master_df)
    
    print("5. Saving final dataset...")
    final_df.to_csv(output_filepath, index=False)
    
    print(f"\nSuccess! Your expanded ML training dataset is ready at:\n{output_filepath}")
    print("\nPreview of the final dataset columns:")
    print(final_df.columns.tolist())
    print("\nFirst few rows preview:")
    print(final_df.head(5))
# import pandas as pd
# import numpy as np


# def load_population_density(filepath):
#     df = pd.read_csv(filepath, header=None)
    
#     if df.shape[1] == 3:
#         df.columns = ['health_zone', 'date', 'pop_density']
#         df = df[['health_zone', 'pop_density']].drop_duplicates()
#     else:
#         df.columns = ['health_zone', 'pop_density']
    

#     df['health_zone'] = df['health_zone'].astype(str).str.strip("[]'\" ")
#     df['pop_density'] = df['pop_density'].astype(str).str.strip("[]'\" ")
   
#     df['pop_density'] = pd.to_numeric(df['pop_density'], errors='coerce').fillna(0)
    
#     return df


# def extract_distance_to_epicenter(matrix_filepath, epicenter_name="Bunia"):
#     # Load matrix (first column is index, first row is headers)
#     df_matrix = pd.read_csv(matrix_filepath, index_col=0)
    
#     # Clean the index (origins) and columns (destinations) just in case they have brackets
#     df_matrix.index = df_matrix.index.astype(str).str.strip("[]'\" ")
#     df_matrix.columns = df_matrix.columns.astype(str).str.strip("[]'\" ")
    
#     if epicenter_name in df_matrix.columns:
#         df_distance = df_matrix[[epicenter_name]].reset_index()
#         df_distance.columns = ['health_zone', 'travel_time_to_epicenter']
#     else:
#         raise ValueError(f"Could not find '{epicenter_name}' in the matrix columns.")
        
#     return df_distance

# # ==========================================
# # 3. DATASET ASSEMBLER
# # ==========================================
# def assemble_master_dataset(df_cases, df_pop, df_travel):
#     master_df = df_cases.copy()
    
#     # Clean the base cases health_zone column to ensure a perfect match during merge
#     master_df['health_zone'] = master_df['health_zone'].astype(str).str.strip("[]'\" ")
    
#     # Merge Population & Travel Time
#     master_df = pd.merge(master_df, df_pop, on='health_zone', how='left')
#     master_df = pd.merge(master_df, df_travel, on='health_zone', how='left')
    
#     # Fill missing static data (e.g., if a zone wasn't in the travel matrix)
#     master_df['pop_density'] = master_df['pop_density'].fillna(0)
#     master_df['travel_time_to_epicenter'] = master_df['travel_time_to_epicenter'].fillna(-1)
    
#     return master_df

# # ==========================================
# # 4. TARGET VARIABLE CREATOR (ML LABELS)
# # ==========================================
# def create_target_variable(df):
#     # Ensure data is sorted chronologically for each zone
#     df['date'] = pd.to_datetime(df['date'])
#     df = df.sort_values(by=['health_zone', 'date']).reset_index(drop=True)
    
#     # Calculate daily NEW cases (since 'value' is cumulative)
#     df['new_cases_today'] = df.groupby('health_zone')['value'].diff().fillna(0)
#     df.loc[df['new_cases_today'] < 0, 'new_cases_today'] = 0 
    
#     # Look ahead 7 days to sum upcoming cases
#     df['cases_next_7_days'] = df.groupby('health_zone')['new_cases_today'].transform(
#         lambda x: x.shift(-7).rolling(window=7, min_periods=1).sum()
#     )
    
#     # Binarize the target: 1 if there will be cases, 0 if not
#     df['target_outbreak_next_7d'] = (df['cases_next_7_days'] > 0).astype(int)
    
#     # Drop rows at the very end of the timeline where we can't look 7 days into the future
#     df = df.dropna(subset=['cases_next_7_days']).copy()
    
#     # Drop intermediate columns used for calculation to keep the final dataset clean
#     df = df.drop(columns=['new_cases_today', 'cases_next_7_days'])
    
#     return df

# # ==========================================
# # 5. EXECUTION BLOCK
# # ==========================================
# if __name__ == "__main__":
#     # Define your file paths based on your previous scripts
#     base_dir = r"C:\Users\STUDENT\OneDrive\Desktop\KTT Fellowship\ViralWatch Project\aimsktt_viralwatch\ml\dataset"
    
#     cases_filepath = rf"{base_dir}\days_since_first_case.csv"
#     pop_filepath = rf"{base_dir}\worldpop__pop_density.csv"
#     matrix_filepath = rf"{base_dir}\osrm__travel_time__static.matrix.csv"
#     output_filepath = rf"{base_dir}\final_ml_training_dataset.csv"
    
#     print("1. Loading datasets...")
#     # Load the base dataset you created in the last step
#     df_cases = pd.read_csv(cases_filepath)
#     df_pop = load_population_density(pop_filepath)
#     df_travel = extract_distance_to_epicenter(matrix_filepath, epicenter_name="Bunia")
    
#     print("2. Assembling master dataset...")
#     master_df = assemble_master_dataset(df_cases, df_pop, df_travel)
    
#     print("3. Creating 7-day target variable...")
#     final_df = create_target_variable(master_df)
    
#     print("4. Saving final dataset...")
#     final_df.to_csv(output_filepath, index=False)
    
#     print(f"\nSuccess! Your ML training dataset is ready at:\n{output_filepath}")
#     print("\nPreview of the final dataset:")
#     print(final_df[['health_zone', 'date', 'value', 'days_since_first_case', 'target_outbreak_next_7d']].head(10))