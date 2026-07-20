import pandas as pd
import sqlite3

print("1. Loading historical CSV data...")
# Point this to your actual CSV file
csv_path = "/content/final_ml_training_dataset.csv" 
df = pd.read_csv(csv_path)

# Ensure the date column is properly recognized
df['date'] = pd.to_datetime(df['date'])

print("2. Extracting the latest live data for each zone...")
# Sort all the data chronologically (oldest to newest)
df = df.sort_values(by='date')

# Drop all historical rows, keeping ONLY the absolute newest row for each health zone
# (Assuming your CSV has a column named 'health_zone' or 'zone_name')
current_live_data = df.drop_duplicates(subset=['health_zone'], keep='last')

# Rename the column to 'zone_name' to match the FastAPI script perfectly
current_live_data = current_live_data.rename(columns={'health_zone': 'zone_name'})

print(f"Isolated current data for {len(current_live_data)} health zones.")

print("3. Building the SQLite Database...")
# Connect to SQLite (this will automatically create the 'viralwatch.db' file)
conn = sqlite3.connect("viralwatch.db")

# Write the live data into a table named 'health_zones_current'
current_live_data.to_sql("health_zones_current", conn, if_exists="replace", index=False)

conn.close()
print("Database built successfully! The FastAPI can now read from 'viralwatch.db'.")