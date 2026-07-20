import pandas as pd
import numpy as np
import joblib
from tensorflow import keras
import os

def get_outbreak_prediction(input_data, model, scaler, model_type='rf'):
    """
    Takes raw input, scales it, prints the prediction directly to the screen,
    and returns a structured payload.
    """
    # 1. Scale the raw inputs using the saved training scaler
    scaled_input = scaler.transform(input_data)
    
    # 2. Extract the Probability based on the model type
    if model_type == 'rf':
        risk_probability = model.predict_proba(scaled_input)[0][1]
    elif model_type == 'keras':
        risk_probability = model.predict(scaled_input, verbose=0)[0][0]
    else:
        raise ValueError("model_type must be either 'rf' or 'keras'")

    # 3. Format the display probability
    display_string = f"{risk_probability * 100:.1f}%"

    print(f"Outbreak Probability: {display_string}")
    if risk_probability >= 0.5:
        print("Status: HIGH RISK ")
    else:
        print("Status: LOW RISK")

    return {
        "probability_display": display_string,  
    }

# ==========================================
# BULK INFERENCE ON TEST SET
# ==========================================

print("1. Loading saved models and scaler...")
scaler = joblib.load('/content/aimsktt_viralwatch/ml/models/feature_scaler.joblib')
rf_model = joblib.load('/content/aimsktt_viralwatch/ml/models/random_forest_baseline.joblib')

print("2. Loading dataset and extracting the test set (July 2026)...")
filepath = "/content/aimsktt_viralwatch/ml/dataset/final_ml_training_dataset.csv"
df = pd.read_csv(filepath)
df['date'] = pd.to_datetime(df['date'])

# Isolate the test set just like the training script did
split_date = pd.to_datetime("2026-07-01")
test_df = df[df['date'] >= split_date].copy()

# Ensure we use the exact same 9 features the model was trained on
features = [
    'days_since_first_case', 'cumulative_confirmed_cases', 'cumulative_confirmed_deaths', 
    'cumulative_contacts_isolated', 'cumulative_contacts_traced', 'cumulative_suspected_cases', 
    'cumulative_suspected_deaths', 'pop_density', 'travel_time_to_epicenter'
]

X_test = test_df[features]

print("3. Scaling features and running predictions...")
# Scale the features using the loaded scaler
X_test_scaled = scaler.transform(X_test)

# Get probabilities for the entire test set at once
test_probabilities = rf_model.predict_proba(X_test_scaled)[:, 1]

print("4. Saving results to CSV...")
results_df = test_df.copy()
results_df['predicted_probability_next_7d'] = np.round(test_probabilities, 2)
# results_df['predicted_probability_next_7d'] = test_probabilities
results_df['probability_display'] = (results_df['predicted_probability_next_7d'] * 100).round(1).astype(str) + '%'

# Define the output path and save

output_csv_path = "/content/aimsktt_viralwatch/ml/results/test_set_outbreak_predictions.csv"
os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
results_df.to_csv(output_csv_path, index=False)

print(f" [+] Success! Test set predictions saved to: {output_csv_path}")

print("\nPreview of the saved predictions:")
print(results_df[['date', 'target_outbreak_next_7d', 'predicted_probability_next_7d', 'probability_display']].head())