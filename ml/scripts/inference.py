import pandas as pd
import numpy as np
import joblib
from tensorflow import keras

def get_outbreak_prediction(input_data, model, scaler, model_type='rf'):
    """
    Takes raw input, scales it, prints the prediction directly to the screen,
    and returns a structured payload.
    """
    
    # 1. Scale the raw inputs using the saved training scaler
    scaled_input = scaler.transform(input_data)
    
    # 2. Extract the Probability based on the model type
    if model_type == 'rf':
        # Random Forest
        risk_probability = model.predict_proba(scaled_input)[0][1]
        
    elif model_type == 'keras':
        # Keras Deep Learning
        risk_probability = model.predict(scaled_input, verbose=0)[0][0]
        
    else:
        raise ValueError("model_type must be either 'rf' or 'keras'")

    # 3. Format the display probability
    display_string = f"{risk_probability * 100:.1f}%"

    # 4. PRINT DIRECTLY TO SCREEN
    print(f"\n--- {model_type.upper()} MODEL PREDICTION ---")
    print(f"Outbreak Probability: {display_string}")
    
    if risk_probability >= 0.5:
        print("Status: ⚠️ HIGH RISK (Threshold Exceeded)")
    else:
        print("Status: ✅ LOW RISK")
    print("----------------------------------\n")

    # 5. Return the structured payload
    return {
        # "probability_raw": float(risk_probability),               
        "probability_display": display_string,  
        # "is_high_risk": int(risk_probability >= 0.5)                               
    }


# ==========================================
# TEST IT ON YOUR SCREEN RIGHT NOW
# ==========================================

# Load your saved models
scaler = joblib.load('/content/models/feature_scaler.joblib')
rf_model = joblib.load('/content/models/random_forest_baseline.joblib')

# Create fake input data for a high-risk zone
test_input = pd.DataFrame(
    [[150, 4, 1200.5, 45.0]], 
    columns=['cumulative_confirmed_cases', 'days_since_first_case', 'pop_density', 'travel_time_to_epicenter']
)

# Run the function (This will trigger the print statements)
result = get_outbreak_prediction(test_input, rf_model, scaler, model_type='rf')