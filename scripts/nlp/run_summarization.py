import os
import glob
import pandas as pd
from transformers import pipeline
from tqdm import tqdm

INPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../BDBV2026-Data/data/public_health_response/processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../output/nlp/summarization"))

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Loading Summarization model (sshleifer/distilbart-cnn-12-6)...")
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=-1)

files = glob.glob(os.path.join(INPUT_DIR, "*_en__daily.csv"))
print(f"Found {len(files)} English files for Summarization processing.")

for file_path in files:
    filename = os.path.basename(file_path)
    df = pd.read_csv(file_path)
    
    if df.shape[1] > 2:
        text_col = df.columns[2]
        valid_mask = df[text_col].notna() & (df[text_col] != "")
        
        def generate_summary(text):
            if not isinstance(text, str) or not text.strip():
                return ""
            # Too short to summarize effectively
            if len(text.split()) < 20: 
                return text
            try:
                # Dynamic length bounds to avoid model errors
                input_len = len(text.split())
                max_len = min(60, max(20, int(input_len * 0.6)))
                min_len = min(10, max_len - 5)
                
                # Truncate text to avoid token limits
                summary = summarizer(text[:2000], max_length=max_len, min_length=min_len, do_sample=False)
                return summary[0]['summary_text']
            except Exception as e:
                return f"Error: {str(e)}"
                
        tqdm.pandas(desc=f"Summarizing: {filename[:30]}...")
        summary_col = df.loc[valid_mask, text_col].progress_apply(generate_summary)
        df.loc[valid_mask, 'summary'] = summary_col
    
    out_path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(out_path, index=False)

print("Summarization processing complete.")
