import os
import glob
import json
import pandas as pd
from transformers import pipeline
from tqdm import tqdm

from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "nlp", "ner")

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Loading NER model (dslim/bert-base-NER)...")
ner_pipeline = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple", device=-1)

files = [str(p) for p in Path(PROJECT_ROOT).rglob("*_en__daily.csv")]
print(f"Found {len(files)} English files for NER processing.")

for file_path in files:
    filename = os.path.basename(file_path)
    df = pd.read_csv(file_path)
    
    if df.shape[1] > 2:
        text_col = df.columns[2]
        valid_mask = df[text_col].notna() & (df[text_col] != "")
        
        def extract_entities(text):
            if not isinstance(text, str) or not text.strip():
                return "[]"
            try:
                # Truncate text to avoid token limit errors
                entities = ner_pipeline(text[:1500])
                formatted_entities = [{"type": e['entity_group'], "value": e['word'], "score": round(float(e['score']), 4)} for e in entities]
                return json.dumps(formatted_entities)
            except Exception as e:
                return json.dumps([{"error": str(e)}])
                
        # Apply only to valid rows
        tqdm.pandas(desc=f"NER: {filename[:30]}...")
        entities_col = df.loc[valid_mask, text_col].progress_apply(extract_entities)
        df.loc[valid_mask, 'ner_json'] = entities_col
    
    out_path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(out_path, index=False)

print("NER processing complete.")
