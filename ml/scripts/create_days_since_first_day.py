import pandas as pd
import numpy as np

def calculate_days_since_first_case_no_header(filepath):

    df = pd.read_csv(filepath, header=None)

    df.columns = ['health_zone', 'date', 'value']
    

    df['date'] = df['date'].astype(str).str.strip("[]'\" ")
    df['value'] = df['value'].astype(str).str.strip("[]'\" ")
    

    df['date'] = pd.to_datetime(df['date'])
    df['value'] = pd.to_numeric(df['value'], errors='coerce').fillna(0).astype(int)
    

    positive_cases = df[df['value'] > 0]
    

    first_case_dates = positive_cases.groupby('health_zone')['date'].min().reset_index()
    first_case_dates.rename(columns={'date': 'first_case_date'}, inplace=True)
    

    df = pd.merge(df, first_case_dates, on='health_zone', how='left')
    

    df['days_since_first_case'] = (df['date'] - df['first_case_date']).dt.days
    
  
    df['days_since_first_case'] = df['days_since_first_case'].fillna(0)
    df.loc[df['days_since_first_case'] < 0, 'days_since_first_case'] = 0
    
   
    df['days_since_first_case'] = df['days_since_first_case'].astype(int)
    
 
    df.drop(columns=['first_case_date'], inplace=True)
    
    return df

csv_file_path = r"C:\Users\STUDENT\OneDrive\Desktop\KTT Fellowship\ViralWatch Project\aimsktt_viralwatch\ml\dataset\insp_sitrep__cumulative_confirmed_cases.csv"


feature_df = calculate_days_since_first_case_no_header(csv_file_path)

output_filepath = r"C:\Users\STUDENT\OneDrive\Desktop\KTT Fellowship\ViralWatch Project\aimsktt_viralwatch\ml\dataset\days_since_first_case.csv"
feature_df = calculate_days_since_first_case_no_header(csv_file_path)

feature_df.to_csv(output_filepath, index=False)

print(f"Success! The new CSV file has been saved to: {output_filepath}")