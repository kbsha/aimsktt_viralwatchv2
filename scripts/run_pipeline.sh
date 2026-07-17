# #!/bin/bash

# set -e


# echo "Starting ML pipeline"


# ./scripts/download_data.sh


# ./scripts/verify_files.sh


# python src/train_model.py


# echo "Pipeline completed"
cat << 'EOF' > scripts/download_data.sh
#!/bin/bash

set -e

REPO_URL="https://github.com/INRB-UMIE/BDBV2026-Data.git"
REPO_DIR="BDBV2026-Data"

echo "=== 1. Scaffolding Test Directory ==="
mkdir -p data_test

echo "=== 2. Cloning/Updating INRB-UMIE Repository ==="
if [ ! -d "$REPO_DIR" ]; then
    echo "Cloning the repository..."
    git clone --depth 1 "$REPO_URL"
else
    echo "Repository already exists. Pulling latest..."
    git -C "$REPO_DIR" pull
fi

echo "=== 3. Organizing Ingested Data into data_test/ ==="
# Copies raw CSV files directly to data_test/
cp "$REPO_DIR"/data/*.csv data_test/ 2>/dev/null || cp "$REPO_DIR"/*.csv data_test/

echo "=== 4. Fetching WHO Bulletins into data_test/ ==="
curl -L -s -o data_test/DON602.html "https://www.who.int/emergencies/disease-outbreak-news/item/DON602"
curl -L -s -o data_test/DON603.html "https://www.who.int/emergencies/disease-outbreak-news/item/DON603"

echo "=== 5. Verifying Integrity ==="
if [ -f "data_test/BDBV2026_Cases_HA.csv" ]; then
    echo "✔ Ingestion verification successful! All files are in data_test/"
else
    echo "❌ INGESTION ERROR: Core files missing from data_test/" >&2
    exit 1
fi
EOF
