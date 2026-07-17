#!/bin/bash
set -e

echo "🚀 Starting ViralWatch pipeline setup inside Codespaces..."

echo "⚡ Installing requirements..."
pip install -r requirements.txt

echo "📥 Syncing remote INRB-UMIE data repository into data_test/..."
chmod +x download_data.sh
./download_data.sh

echo "🧹 Processing and synchronizing databases..."
if [ -f "daily_pipeline.py" ]; then
    python3 daily_pipeline.py
else
    echo "⚠️ daily_pipeline.py not found yet. Skipping DB loading."
fi

echo "🎉 PIPELINE SETUP COMPLETE!"
