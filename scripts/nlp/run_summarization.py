import os
import glob
import json
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from tqdm import tqdm

INPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../BDBV2026-Data/data/public_health_response/processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../output/nlp/summarization"))

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Loading Summarization model (sshleifer/distilbart-cnn-12-6)...")
# Bypass pipeline() and load the tokenizer and model directly
tokenizer = AutoTokenizer.from_pretrained("sshleifer/distilbart-cnn-12-6")
model = AutoModelForSeq2SeqLM.from_pretrained("sshleifer/distilbart-cnn-12-6")

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
                return json.dumps({"summary": text})
            try:
                # Dynamic length bounds to avoid model errors
                input_len = len(text.split())
                max_len = min(60, max(20, int(input_len * 0.6)))
                min_len = min(10, max_len - 5)
                
                # Truncate text to avoid token limits
                inputs = tokenizer(text[:2000], return_tensors="pt", max_length=1024, truncation=True)
                summary_ids = model.generate(inputs["input_ids"], max_length=max_len, min_length=min_len, num_beams=2, early_stopping=True)
                summary_text = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
                return json.dumps({"summary": summary_text})
            except Exception as e:
                return json.dumps({"error": str(e)})
                
        tqdm.pandas(desc=f"Summarizing: {filename[:30]}...")
        summary_col = df.loc[valid_mask, text_col].progress_apply(generate_summary)
        df.loc[valid_mask, 'summary_json'] = summary_col
    
    out_path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(out_path, index=False)

print("Summarization processing complete.")