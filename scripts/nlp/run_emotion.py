import os
import glob
import pandas as pd
from transformers import pipeline
from tqdm import tqdm

INPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../BDBV2026-Data/data/public_health_response/processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../output/nlp/emotion"))

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Loading Emotion model (j-hartmann/emotion-english-distilroberta-base)...")
emotion_pipeline = pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base", return_all_scores=False, device=-1)

files = glob.glob(os.path.join(INPUT_DIR, "*_en__daily.csv"))
print(f"Found {len(files)} English files for Emotion processing.")

for file_path in files:
    filename = os.path.basename(file_path)
    df = pd.read_csv(file_path)
    
    if df.shape[1] > 2:
        text_col = df.columns[2]
        valid_mask = df[text_col].notna() & (df[text_col] != "")
        
        def extract_emotion(text):
            if not isinstance(text, str) or not text.strip():
                return pd.Series([None, None])
            try:
                # Truncate text to avoid token limits
                res = emotion_pipeline(text[:1500])
                return pd.Series([res[0]['label'], res[0]['score']])
            except Exception as e:
                return pd.Series([f"Error: {str(e)}", None])
                
        tqdm.pandas(desc=f"Emotion: {filename[:30]}...")
        emotion_df = df.loc[valid_mask, text_col].progress_apply(extract_emotion)
        emotion_df.columns = ['emotion_label', 'emotion_score']
        
        df.loc[valid_mask, 'emotion_label'] = emotion_df['emotion_label']
        df.loc[valid_mask, 'emotion_score'] = emotion_df['emotion_score']
    
    out_path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(out_path, index=False)

print("Emotion processing complete.")
