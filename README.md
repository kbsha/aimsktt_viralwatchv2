The whole project is now live on https://viralwatch.onrender.com/
with full docker image

# Incremental Data Update Pipeline

## Overview

ViralWatch implements an **incremental data update pipeline** to continuously integrate new outbreak information from the **INRB-UMIE/BDBV2026-Data repository**.

Instead of reprocessing the complete outbreak dataset whenever new reports become available, the pipeline identifies only **new or modified records**, applies the existing data-cleaning rules, updates the processed dataset, refreshes the database, and generates new outbreak risk predictions.

This design enables ViralWatch to operate as a **near real-time viral haemorrhagic fever early-warning system**.

---

# Data Pipeline Architecture

```text
INRB-UMIE BDBV2026 Repository
              |
              | Automatic update check
              ↓
      New Raw Outbreak Data
              |
              | Detect new/changed records
              ↓
     Incremental Cleaning Pipeline
              |
              | Append + Update
              ↓
      Processed Clean Dataset
              |
              ↓
        SQLite Database
              |
              ↓
      Machine Learning Models
              |
              ↓
        FastAPI Backend
              |
              ↓
   Cross-Border Risk Dashboard
```

---

# Data Organization

ViralWatch maintains a structured data lifecycle with three main data layers:

```text
data/
│
├── external/
│   └── BDBV2026-Data/
│       └── Original INRB-UMIE outbreak dataset
│
├── raw/
│   └── incoming/
│       └── Newly downloaded outbreak updates
│
└── processed/
    └── outbreak_clean.csv
        └── Analysis-ready outbreak dataset
```

## Data Layer Description

| Data Layer           | Purpose                                                                                            |
| -------------------- | -------------------------------------------------------------------------------------------------- |
| `data/external/`     | Stores the original outbreak dataset obtained from INRB-UMIE. This source data remains unchanged.  |
| `data/raw/incoming/` | Temporary storage location for newly collected outbreak updates before processing.                 |
| `data/processed/`    | Contains cleaned and validated data used by analytics, machine learning models, and the dashboard. |

---

# Incremental Update Workflow

## 1. Identify Existing Processed Data

The pipeline first loads the previously processed outbreak dataset:

```
data/processed/outbreak_clean.csv
```

Example:

| Date       | Health Zone | Confirmed Cases | Deaths |
| ---------- | ----------- | --------------- | ------ |
| 2026-07-13 | Goma        | 100             | 20     |
| 2026-07-13 | Beni        | 50              | 10     |

The latest processed date is extracted:

```text
Last processed date:
2026-07-13
```

This date is used as the reference point for detecting new outbreak information.

---

# 2. Retrieve Latest Outbreak Data

The pipeline checks the INRB repository for new updates.

```bash
cd data/external/BDBV2026-Data

git pull
```

Example:

Previous dataset:

```
2026-07-13 outbreak report
```

New dataset:

```
2026-07-14 outbreak report
```

Detected update:

```
New records available:
2026-07-14
```

---

# 3. Detect New or Modified Records

The pipeline compares incoming data with the existing processed dataset.

Example implementation:

```python
import pandas as pd

existing_data = pd.read_csv(
    "data/processed/outbreak_clean.csv"
)

latest_data = pd.read_csv(
    "data/external/BDBV2026-Data/latest.csv"
)

last_date = existing_data["date"].max()

new_records = latest_data[
    latest_data["date"] > last_date
]

print(new_records)
```

Output:

```text
New outbreak records:

2026-07-14 | Goma  | 120 cases
2026-07-14 | Beni  | 60 cases
```

---

# 4. Apply Data Cleaning Rules

New outbreak records go through the same preprocessing pipeline used during initial dataset preparation.

Cleaning operations include:

* Standardizing health-zone names.
* Converting date formats.
* Removing duplicate records.
* Handling missing values.
* Correcting inconsistent data formats.

Example:

```python
new_records["health_zone"] = (
    new_records["health_zone"]
    .str.strip()
    .str.lower()
)

new_records["date"] = pd.to_datetime(
    new_records["date"]
)
```

---

# 5. Update Processed Dataset

Cleaned records are merged with historical outbreak data.

```python
updated_dataset = pd.concat(
    [
        existing_data,
        new_records
    ]
)

updated_dataset = updated_dataset.drop_duplicates()
```

Updated dataset:

Before:

```text
2026-07-13 | Goma | 100 cases
```

After:

```text
2026-07-13 | Goma | 100 cases
2026-07-14 | Goma | 120 cases
```

The final dataset is saved:

```python
updated_dataset.to_csv(
    "data/processed/outbreak_clean.csv",
    index=False
)
```

---

# 6. Database Synchronization

After processing, the updated dataset refreshes the ViralWatch database.

```text
Processed Dataset
        |
        ↓
 SQLite Database
        |
        ↓
 FastAPI Backend
        |
        ↓
 Dashboard
```

The database stores:

* Health-zone information.
* Daily outbreak statistics.
* Engineered epidemiological features.
* Model predictions.
* Risk scores.

---

# 7. Machine Learning Prediction Update

Whenever new outbreak data is available:

1. Feature engineering is executed.
2. Machine learning models process updated information.
3. Risk predictions are regenerated.
4. Dashboard indicators are refreshed.

Example output:

| Health Zone | Risk Level |
| ----------- | ---------- |
| Goma        | High       |
| Rutshuru    | High       |
| Beni        | Medium     |
| Bukavu      | Low        |

---

# Automated Daily Update

The update pipeline can run automatically using Linux Cron.

Edit scheduled jobs:

```bash
crontab -e
```

Add:

```bash
0 8 * * * /home/sitanu/viralwatch/scripts/update_pipeline.sh
```

This executes the update process every day at **08:00 AM**.

Automated workflow:

```text
1. Pull latest INRB outbreak data
2. Detect new records
3. Clean incoming data
4. Update processed dataset
5. Synchronize database
6. Generate risk predictions
7. Refresh dashboard
```

---

# Live Demonstration

For the final demonstration, run:

```bash
./scripts/update_pipeline.sh
```

Expected output:

```text
✓ Checking INRB repository updates
✓ New outbreak records detected
✓ Data cleaning completed
✓ Processed dataset updated
✓ Database synchronized
✓ Risk predictions generated
✓ Dashboard refreshed
```

The dashboard displays updated cross-border outbreak risk information covering:

* North Kivu health zones
* South Kivu health zones
* Border regions connected to Rwanda

---

# Benefits of Incremental Updating

The incremental pipeline provides:

✅ Faster data processing compared with full dataset rebuilding

✅ Continuous outbreak surveillance capability

✅ Reliable handling of changing epidemiological information

✅ Updated machine learning predictions

✅ Near real-time dashboard monitoring

✅ Scalable architecture for future outbreak sources

---

## Summary

The ViralWatch incremental update pipeline creates a reliable bridge between outbreak data collection, machine learning prediction, and public-health decision support.

By continuously integrating new information while preserving historical records, ViralWatch provides an efficient foundation for early detection and cross-border viral haemorrhagic fever monitoring.









Day 2 we are working on ML pipiline 

Save this as Setup_project_v2_with_full_pipline.sh in the directory where you want the project, then run:
```
chmod +x Setup_project_v2_with_full_pipline.sh
./Setup_project_v2_with_full_pipline.sh
```
After running it, your project will look like:

```
BDBV2026-Project/
│
├── dashboard/
│   ├── app.py
│   ├── assets/
│   └── components/
│       ├── charts.py
│       ├── maps.py
│       └── tables.py
│
├── data/
│   ├── external/
│   ├── processed/
│   └── raw/
│
├── models/
│
├── notebooks/
│
├── reports/
│   ├── figures/
│   └── final_report.md
│
├── scripts/
│   ├── download_data.sh
│   ├── preprocess_data.sh
│   └── train_model.sh
│
├── src/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── preprocess.py
│   ├── features.py
│   ├── target.py
│   ├── sklearn_model.py
│   ├── keras_model.py
│   ├── evaluate.py
│   └── plots.py
│
├── tests/
│
├── train.py
├── requirements.txt
├── README.md
└── .venv/

```

Update  requirements.txt and  README.md









# ViralWatch
ViralWatch is a five-day capstone project for KTT Fellows designed to create an end-to-end AI early-warning system for the 2026 Bundibugyo virus outbreak in the Democratic Republic of the Congo and Uganda. The system aims to close the critical response gap by detecting outbreak signals weeks earlier than traditional laboratory confirmation.

## Key Project Components:
Data Pipeline: The team integrates various public datasets—including INRB-UMIE outbreak reports and WHO Disease Outbreak News—to create a reproducible data flow.


**Machine Learning & NLP**: The system employs supervised classifiers to predict case onset, a One-Class SVM to detect anomalous pre-outbreak reporting patterns, and NLP pipelines (using Hugging Face) to extract health alerts from official WHO bulletins.

**Infrastructure**: The project serves data via a FastAPI backend and displays it on a cross-border watchlist dashboard, focusing specifically on North Kivu and South Kivu zones bordering Rwanda.


## Evaluation Criteria:

The project is assessed based on engineering quality, data and machine learning rigor, the anomaly detection proof point (specifically catching signals before the May 15 confirmation), and the successful execution of a live demo.

# Project structure:
```
BDBV2026-Project/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── external/
│
├── notebooks/
├── src/
├── models/
├── reports/
├── scripts/
├── tests/
│
├── requirements.txt
└── .venv/
```




Day 3 Tasks 


1. creating proper venv , to the proper deployment for next step 
2. with Dashbord Draft for final deployment 
3. prepAR THE DAtaset and analayz ther data , visuallize 

So whAT WE DO IS 


Early-warning dashboard for the 2026 Bundibugyo virus outbreak, with a
cross-border watchlist focused on **North Kivu and South Kivu** health zones
bordering Rwanda.

**Stack:** FastAPI (API + static serving) · SQLite read-only snapshot ·
Leaflet choropleth (free, no API key) · deployable to Render's free tier.

> ⚠️ This repo ships with **synthetic demo data** FOR NOW UNTILE WE GET REAL DATA  FROM OUR TEAM DATA PIPILINE TEAM WITH API KEY 



so it runs end-to-end out of
> the box. The zone names and coordinates are real (Kivu), but the case counts,
> scores, and polygon shapes are placeholders. See **[Swapping in real data](#5-swap-in-real-data)**.

---

## 1. What you get

| Endpoint | What it returns |
|---|---|
| `GET /earlywarning` | All health zones ranked by anomaly/early-warning score (the watchlist) |
| `GET /predict/{zone}` | Next-7-day case probability + features for one zone |
| `GET /briefing` | NLP-extracted situation summary from the latest DON bulletin |
| `GET /geojson` | Health-zone polygons with the current score joined on (feeds the map) |
| `GET /health` | Liveness probe (for Render / uptime pingers) |
| `GET /` | The dashboard (map + watchlist + briefing) |
| `GET /docs` | Auto-generated Swagger UI |

The dashboard, the ranked watchlist, and the situation briefing all read from
those endpoints. Click any zone on the map or in the table to see its
next-7-day probability.

---

## 2. Run it locally (≈2 minutes)

Prerequisites: **Python 3.11+**.

```bash
# 1. create + activate a virtual environment
python -m venv .venv

# macOS / Linux / Git Bash:
source .venv/bin/activate
# Windows PowerShell:
#   .\.venv\Scripts\Activate.ps1
#   (if activation is blocked once:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned)

# 2. install runtime deps
pip install -r requirements.txt

# 3. build the read-only data snapshot (DB + GeoJSON)
python scripts/seed_db.py

# 4. start the server
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000** for the dashboard and
**http://127.0.0.1:8000/docs** for the API docs.

> The DB is already committed, so step 3 is optional locally — but run it any
> time you want to regenerate the snapshot.

---

## 3. Project layout

```
aimsktt_viralwatch/
├── app/                    # the FastAPI service
│   ├── main.py             #   endpoints + serves the dashboard
│   ├── database.py         #   read-only SQLite connection
│   ├── models.py           #   Pydantic response schemas (power /docs)
│   └── nlp.py              #   lightweight DON bulletin extractor
├── dashboard/              # the frontend (served by FastAPI at /)
│   ├── index.html
│   ├── style.css
│   └── app.js              #   Leaflet map + watchlist + briefing
├── data/
│   ├── viralwatch.db       #   read-only snapshot the API serves (committed)
│   ├── processed/
│   │   └── zones.geojson   #   zone boundaries (PLACEHOLDER squares for now)
│   └── don/
│       └── DON603_SAMPLE.txt   # replace with real WHO DON text
├── scripts/
│   ├── seed_db.py          #   builds viralwatch.db + zones.geojson
│   └── shapefile_to_geojson.py  # HDX shapefile -> real GeoJSON
├── models/                 # drop your trained classifier.joblib here
├── notebooks/              # your Day-2..Day-4 analysis notebooks
├── requirements.txt        # runtime (minimal — what Render installs)
├── requirements-dev.txt    # pandas/geopandas/sklearn for building data
└── render.yaml             # Render Blueprint (one-click deploy)
```

This service sits alongside the ML code your team keeps in `src/` — the API just
reads the snapshot your pipeline produces.

---

## 6. Google Maps instead of Leaflet?

Leaflet is used here because it's free, needs no API key or billing account, and
is the standard tool for admin-boundary choropleths. If you specifically want
Google Maps, its Maps JavaScript API can render the same GeoJSON via its Data
layer — but note Google now requires a billing account (credit card) even inside
the free tier, and retired the old universal $200 credit in March 2025. Since
ViralWatch is an academic crisis-response tool, you'd qualify for Google's
public-program map credits, but that's a "later" step and buys nothing for the
demo.

---






Tommorow  task will be 


we will build actual ML model to include to our main located in    

 # --- plug in our  real model here -------------------------------------
From app folder main.py 


and also actual real time dATABASE 

.
.
.


And the database is now active 


its fully deployed on render 

with all the full map intgrated for dahsbord 
