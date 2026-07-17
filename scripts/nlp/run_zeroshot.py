import os
import glob
import pandas as pd
from transformers import pipeline
from tqdm import tqdm

INPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../BDBV2026-Data/data/public_health_response/processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../output/nlp/zeroshot"))

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Loading Zero-Shot model (valhalla/distilbart-mnli-12-3)...")
zero_shot_pipeline = pipeline("zero-shot-classification", model="valhalla/distilbart-mnli-12-3", device=-1)

# Dynamic class mapping based on pillar
PILLAR_CLASSES = {
    "community_engagement": ["rumor management", "sensitization", "radio broadcast", "community resistance"],
    "coordination": ["meeting", "strategic planning", "resource allocation", "partner coordination"],
    "infection_prevention_controle": ["decontamination", "safe burials", "training", "ppe distribution"],
    "laboratory": ["testing", "sample transport", "equipment breakdown", "stockout"],
    "logistics": ["vehicles and transport", "medical supplies", "infrastructure", "communication"],
    "management": ["patient admission", "patient discharge", "death", "bed capacity"],
    "monitoring": ["contact tracing", "active case search", "alert investigation", "point of entry screening"],
    "protection_sexual_exploitation_abuse": ["training", "reporting", "victim support", "awareness"],
    "security": ["armed attack", "roadblock", "kidnapping", "general instability"]
}

files = glob.glob(os.path.join(INPUT_DIR, "*_en__daily.csv"))
print(f"Found {len(files)} English files for Zero-Shot processing.")

for file_path in files:
    filename = os.path.basename(file_path)
    df = pd.read_csv(file_path)
    
    # Identify pillar from filename
    current_pillar = None
    for pillar in PILLAR_CLASSES.keys():
        if pillar in filename:
            current_pillar = pillar
            break
            
    if not current_pillar:
        print(f"Skipping {filename} - could not identify pillar.")
        continue
        
    candidate_labels = PILLAR_CLASSES[current_pillar]
    
    if df.shape[1] > 2:
        text_col = df.columns[2]
        valid_mask = df[text_col].notna() & (df[text_col] != "")
        
        def classify_text(text):
            if not isinstance(text, str) or not text.strip():
                return pd.Series([None, None])
            try:
                # Truncate text to avoid token limits
                res = zero_shot_pipeline(text[:1500], candidate_labels, multi_label=False)
                # Return the top predicted class and its score
                return pd.Series([res['labels'][0], res['scores'][0]])
            except Exception as e:
                return pd.Series([f"Error: {str(e)}", None])
                
        tqdm.pandas(desc=f"Zero-Shot: {filename[:30]}...")
        zs_df = df.loc[valid_mask, text_col].progress_apply(classify_text)
        zs_df.columns = ['zeroshot_class', 'zeroshot_score']
        
        df.loc[valid_mask, 'zeroshot_class'] = zs_df['zeroshot_class']
        df.loc[valid_mask, 'zeroshot_score'] = zs_df['zeroshot_score']
    
    out_path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(out_path, index=False)

print("Zero-Shot processing complete.")
