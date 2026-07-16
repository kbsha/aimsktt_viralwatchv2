# #!/bin/bash

# set -e

# echo "================================="
# echo "aimsktt_viralwatch2 ML Project Setup"
# echo "================================="


# PROJECT_DIR=$(pwd)


# echo "[1/6] Creating directories..."

# mkdir -p data/raw/who_pdfs
# mkdir -p data/external
# mkdir -p data/processed
# mkdir -p models
# mkdir -p reports
# mkdir -p notebooks
# mkdir -p src
# mkdir -p tests


# echo "[2/6] Cloning INRB-UMIE/BDBV2026-Data..."

# if [ ! -d "data/BDBV2026-Data" ]; then

# git clone \
# https://github.com/INRB-UMIE/BDBV2026-Data.git \
# data/BDBV2026-Data

# else

# echo "Repository already exists"

# fi


# echo "[3/6] Downloading WHO Disease Outbreak News PDFs..."


# curl -L \
# "https://www.who.int/emergencies/disease-outbreak-news" \
# -o data/raw/who_pdfs/who_outbreak_page.html



# echo "[4/6] Checking downloaded files..."

# FILE="data/raw/who_pdfs/who_outbreak_page.html"


# if [ -s "$FILE" ]
# then
#     echo "Download successful"
# else
#     echo "Download failed"
#     exit 1
# fi



# echo "[5/6] Creating Python virtual environment..."

# python3 -m venv .venv


# echo "[6/6] Installing Python packages..."

# source .venv/bin/activate


# python -m pip install --upgrade pip


# pip install -r requirements.txt


# echo ""
# echo "================================="
# echo "Setup completed successfully"
# echo "================================="
#!/bin/bash
set -e
trap 'echo "❌ Error occurred at line $LINENO"; exit 1' ERR

echo "=== Starting ML pipeline ==="

# Define directories
RAW_DIR="data/raw"
PROCESSED_DIR="data/processed"
EXTERNAL_DIR="data/external"
MODELS_DIR="models"
NOTEBOOKS_DIR="notebooks"
SRC_DIR="src"
LOG_DIR="logs"

# Scaffold ML project structure
echo "=== 1. Scaffolding Project Structure ==="
mkdir -p $RAW_DIR $PROCESSED_DIR $EXTERNAL_DIR $MODELS_DIR $NOTEBOOKS_DIR $SRC_DIR $LOG_DIR tests configs docs

# Check if Git LFS is installed
echo "=== 2. Checking Git LFS ==="
if command -v git-lfs >/dev/null 2>&1; then
    echo "✔ Git LFS is installed."
    git lfs install
else
    echo "⚠ Git LFS not found. Large files may not be cloned correctly."
fi

# Clone or update external data repo
REPO_URL="https://github.com/INRB-UMIE/BDBV2026-Data.git"
REPO_DIR="$EXTERNAL_DIR/BDBV2026-Data"

echo "=== 3. Cloning/Updating INRB-UMIE Repository ==="
if [ ! -d "$REPO_DIR" ]; then
    echo "Cloning the repository..."
    git clone --depth 1 "$REPO_URL" "$REPO_DIR"
else
    echo "Repository already exists. Pulling latest..."
    git -C "$REPO_DIR" pull
fi

# Copy outbreak CSVs into raw data
echo "=== 4. Organizing Raw Data ==="
cp "$REPO_DIR"/data/*.csv "$RAW_DIR"/ 2>/dev/null || cp "$REPO_DIR"/*.csv "$RAW_DIR"/

# Download WHO bulletins into raw data
echo "=== 5. Fetching WHO Bulletins ==="
curl -L -s -o "$RAW_DIR/DON602.html" "https://www.who.int/emergencies/disease-outbreak-news/item/DON602"
curl -L -s -o "$RAW_DIR/DON603.html" "https://www.who.int/emergencies/disease-outbreak-news/item/DON603"

# Verify ingestion integrity
echo "=== 6. Verifying Integrity ==="
if [ -f "$RAW_DIR/BDBV2026_Cases_HA.csv" ]; then
    echo "✔ Ingestion verification successful! All files are in $RAW_DIR/"
else
    echo "❌ INGESTION ERROR: Core files missing from $RAW_DIR/" >&2
    exit 1
fi

# Setup Python environment
echo "=== 7. Setting up Virtual Environment ==="
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo "=== Pipeline completed successfully ==="
