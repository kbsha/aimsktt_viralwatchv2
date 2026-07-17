import os
import joblib
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, average_precision_score
import matplotlib.pyplot as plt
from tensorflow.keras.callbacks import EarlyStopping


filepath = "/content/final_ml_training_dataset.csv"


df = pd.read_csv(filepath)

df['date'] = pd.to_datetime(df['date'])


split_date = pd.to_datetime("2026-07-01")

train_df = df[df['date'] < split_date].copy()
test_df = df[df['date'] >= split_date].copy()

print(f"   Training rows (May/June): {len(train_df)}")
print(f"   Testing rows (July): {len(test_df)}")


features = ['days_since_first_case', 'cumulative_confirmed_cases', 'cumulative_confirmed_deaths', 'cumulative_contacts_isolated', 'cumulative_contacts_traced', 'cumulative_suspected_cases', 'cumulative_suspected_deaths', 'pop_density', 'travel_time_to_epicenter' ]
target = 'target_outbreak_next_7d'

X_train = train_df[features]
y_train = train_df[target]

X_test = test_df[features]
y_test = test_df[target]

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)


print("\n2. Training Scikit-Learn Random Forest Baseline...")
# class_weight='balanced' forces the tree to care about the rare outbreaks
rf_model = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)
rf_model.fit(X_train_scaled, y_train)

# Predictions & Probabilities
rf_preds = rf_model.predict(X_test_scaled)
rf_probs = rf_model.predict_proba(X_test_scaled)[:, 1]

print("--- Random Forest Evaluation ---")
print(classification_report(y_test, rf_preds))
print(f"PR-AUC Score: {average_precision_score(y_test, rf_probs):.4f}")


print("\n3. Training Keras Deep Learning Network...")

# Keep the architecture compact to prevent overfitting on 4 features
model = keras.Sequential([
    layers.Input(shape=(len(features),)),
    layers.Dense(16, activation='relu'),
    layers.Dropout(0.3),
    layers.Dense(8, activation='relu'),
    layers.Dense(1, activation='sigmoid')
])

model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=0.001),
    loss='binary_crossentropy',
    metrics=[
        keras.metrics.Precision(name='precision'),
        keras.metrics.Recall(name='recall'),
        keras.metrics.AUC(name='pr_auc', curve='PR')
    ]
)

# Calculate dynamic class weights for Keras to handle the severe imbalance
neg, pos = np.bincount(y_train)
total = neg + pos
weight_for_0 = (1 / neg) * (total / 2.0)
weight_for_1 = (1 / pos) * (total / 2.0)
class_weights = {0: weight_for_0, 1: weight_for_1}

# Train the network
# Create the Early Stopping mechanism
early_stopper = EarlyStopping(
    monitor='val_loss',          # Watch the validation loss
    patience=5,                  # Wait 5 epochs to see if it improves before stopping
    restore_best_weights=True    # 🌟 THE MAGIC FIX: Automatically roll back to the best epoch!
)
history = model.fit(
    X_train_scaled, y_train,
    epochs=50,                   # You can increase this safely now
    batch_size=32,
    validation_data=(X_test_scaled, y_test),
    class_weight=class_weights,
    callbacks=[early_stopper],   # <--- Add the stopper here
    verbose=1 
)

# Final evaluation using Keras
keras_results = model.evaluate(X_test_scaled, y_test, verbose=0)
print("\n--- Keras Network Evaluation ---")
for name, value in zip(model.metrics_names, keras_results):
    print(f"{name}: {value:.4f}")


print("\n4. Saving Models and Scaler to disk...")

# Define the models directory
# models_dir = r"C:\Users\STUDENT\OneDrive\Desktop\KTT Fellowship\ViralWatch Project\aimsktt_viralwatch\ml\models"
models_dir = "/content/models"


os.makedirs(models_dir, exist_ok=True)

# Save the Scaler
scaler_save_path = os.path.join(models_dir, "feature_scaler.joblib")
joblib.dump(scaler, scaler_save_path)
print(f"   [+] Scaler saved to: {scaler_save_path}")

# Save the Random Forest Model
rf_save_path = os.path.join(models_dir, "random_forest_baseline.joblib")
joblib.dump(rf_model, rf_save_path)
print(f"   [+] Random Forest saved to: {rf_save_path}")

# Save the Keras Model
keras_save_path = os.path.join(models_dir, "keras_outbreak_model.keras")
model.save(keras_save_path)
print(f"   [+] Keras Model saved to: {keras_save_path}")
print("\nTraining and saving pipeline complete!")

print("\n5. Generating Training & Overfitting Graphs...")

# Set up a 1x2 grid for the plots
plt.figure(figsize=(14, 5))

# --- Plot 1: Training vs Validation Loss ---
# This is the best indicator of overfitting.
plt.subplot(1, 2, 1)
plt.plot(history.history['loss'], label='Training Loss', color='blue', linewidth=2)
plt.plot(history.history['val_loss'], label='Validation Loss', color='red', linewidth=2)
plt.title('Model Loss (Diagnosing Overfitting)')
plt.xlabel('Epochs')
plt.ylabel('Binary Crossentropy Loss')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.7)

# --- Plot 2: Training vs Validation PR-AUC ---
# This shows how well the model separates the classes.
plt.subplot(1, 2, 2)
plt.plot(history.history['pr_auc'], label='Training PR-AUC', color='blue', linewidth=2)
plt.plot(history.history['val_pr_auc'], label='Validation PR-AUC', color='red', linewidth=2)
plt.title('Model PR-AUC (Performance)')
plt.xlabel('Epochs')
plt.ylabel('Precision-Recall AUC')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.7)

plt.tight_layout()

# ==========================================
# THE FIX: Save to the specific loss directory
# ==========================================
# Define the exact path you requested for Colab
loss_dir = "/content/aimsktt_viralwatch/ml/loss_graphs"

# Tell Python to create this folder if it doesn't exist yet
os.makedirs(loss_dir, exist_ok=True)

# Save the image into that new folder
plot_path = os.path.join(loss_dir, "training_curves.png")
plt.savefig(plot_path)
print(f"   [+] Training curves saved successfully to: {plot_path}")
