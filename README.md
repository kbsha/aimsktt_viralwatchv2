# aimsktt_viralwatch
by KB-Fenta and  lorrian
Here we can work on Linux & Shell for ML Workflows


creat bash 

Step 1 — Create your project repository structure

From your terminal:
```
mkdir aimsktt_viralwatch
cd aimsktt_viralwatch
```

Create folders:
```
mkdir -p data/{raw,processed,external}
mkdir -p notebooks
mkdir -p src
mkdir -p models
mkdir -p reports
mkdir -p scripts
mkdir -p tests
```

Your structure:
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
Step 2 — Create the Bash setup script

Create:
```
nano scripts/setup_project.sh
```

Save:

CTRL + O
ENTER
CTRL + X



Step 3 — Make the script executable
```
chmod +x scripts/setup_project.sh
```



Also check your Python environment on Windows

For your virtual environment, use:

Create:
```
python -m venv .venv
```
Activate:
```
.\.venv\Scripts\Activate.ps1
```
If PowerShell blocks activation, run:
```
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
Then activate again:
```
.\.venv\Scripts\Activate.ps1
```


Step 5 — Activate your environment every time

Linux:
```
source .venv/bin/activate
```
Check:
```
python --version
pip list
```
Deactivate:
```
deactivate
```

Step 6 — Create data download script

Create:
```
nano scripts/download_data.sh
```


Make executable:
```
chmod +x scripts/download_data.sh
```
Run:
```
./scripts/download_data.sh
```

Step 7 — Verify file integrity script

Create:
```
nano scripts/verify_files.sh
```

Run:
```
chmod +x scripts/verify_files.sh
./scripts/verify_files.sh
```


Step 8 — Create ML pipeline

Create:
```
nano src/train_model.py
```



Step 9 — Run ML training

Activate environment:
```
source .venv/bin/activate
```
Run:
```
python src/train_model.py
```
Output:

Loading data...
Training model...
Accuracy: 0.85
Model saved




Step 10 — Create one command pipeline

Create:
```
nano scripts/run_pipeline.sh
```


Make executable:
```
chmod +x scripts/run_pipeline.sh
```
Run everything:
```
./scripts/run_pipeline.sh
```



Final S3 Workflow

Your daily workflow becomes:
```
git checkout -b feature/ml-pipeline

source .venv/bin/activate

./scripts/run_pipeline.sh

git add .

git commit -m "Add ML pipeline and shell automation"

git push origin feature/ml-pipeline
```
Then create a Pull Request.

This covers the S3 requirements:
✅ Linux filesystem
✅ Bash scripting
✅ Pipes/redirection
✅ curl downloads
✅ Git repository cloning
✅ Integrity checking
✅ Python venv
✅ pip packages
✅ ML model training pipeline
✅ Reproducible workflow



