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
