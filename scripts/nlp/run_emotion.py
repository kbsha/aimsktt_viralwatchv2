import os
import glob
import json
import pandas as pd
from transformers import pipeline
from tqdm import tqdm

from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "nlp", "emotion")

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Loading Emotion model (j-hartmann/emotion-english-distilroberta-base)...")
emotion_pipeline = pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base", return_all_scores=False, device=-1)

files = [str(p) for p in Path(PROJECT_ROOT).rglob("*_en__daily.csv")]
print(f"Found {len(files)} English files for Emotion processing.")

for file_path in files:
    filename = os.path.basename(file_path)
    df = pd.read_csv(file_path)
    
    if df.shape[1] > 2:
        text_col = df.columns[2]
        valid_mask = df[text_col].notna() & (df[text_col] != "")
        
        def extract_emotion(text):
            if not isinstance(text, str) or not text.strip():
                return "{}"
            try:
                # Truncate text to avoid token limits
                res = emotion_pipeline(text[:1500])
                return json.dumps({"label": res[0]['label'], "score": round(float(res[0]['score']), 4)})
            except Exception as e:
                return json.dumps({"error": str(e)})
                
        tqdm.pandas(desc=f"Emotion: {filename[:30]}...")
        df.loc[valid_mask, 'emotion_json'] = df.loc[valid_mask, text_col].progress_apply(extract_emotion)
    
    out_path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(out_path, index=False)

print("Emotion processing complete.")
