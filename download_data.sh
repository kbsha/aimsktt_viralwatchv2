#!/bin/bash
set -e

REPO_URL="https://github.com/INRB-UMIE/BDBV2026-Data.git"
REPO_DIR="BDBV2026-Data"

echo "🧹 Preparing local data_test directory..."
rm -rf data_test
mkdir -p data_test

echo "🚀 Cloning BDBV2026-Data Repository..."
rm -rf "$REPO_DIR"
git clone --depth 1 "$REPO_URL"

echo "🎯 Collecting requested datasets..."

# 1. Copy targeted files from build/
if [ -d "$REPO_DIR/build" ]; then
    echo "Processing build artifacts..."
    find "$REPO_DIR/build" -type f \( \
        -iname "insp*" -o \
        -iname "epi_cases*" -o \
        -iname "worldpop_*" -o \
        -iname "OSRM_*" -o \
        -iname "cross_border*" -o \
        -iname "flowminder_short*" -o \
        -iname "grid3_healthsites*" \
    \) -exec cp {} data_test/ \;
fi

# 2. Extract Shapefiles from data/ directory
SHP_DIR="$REPO_DIR/data/shapefiles"
if [ -d "$SHP_DIR" ]; then
    echo "🌎 Extracting geographical shapefiles..."
    cp "$SHP_DIR"/DRC_Health_zones.* data_test/ 2>/dev/null || cp "$SHP_DIR"/* data_test/ 2>/dev/null
else
    find "$REPO_DIR/data" -type f \( -name "*.shp" -o -name "*.shx" -o -name "*.dbf" -o -name "*.prj" \) -exec cp {} data_test/ \;
fi

# Clean up cloned repository
rm -rf "$REPO_DIR"

echo "🎉 All selected datasets loaded into data_test/!"
ls -l data_test/
