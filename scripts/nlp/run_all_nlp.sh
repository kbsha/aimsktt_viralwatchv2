#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "=========================================="
echo "Starting NLP Batch Processing Pipeline"
echo "=========================================="

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")

echo "Running Named Entity Recognition..."
python "$SCRIPT_DIR/run_ner.py"

echo "Running Summarization..."
python "$SCRIPT_DIR/run_summarization.py"

echo "Running Emotion Analysis..."
python "$SCRIPT_DIR/run_emotion.py"

echo "Running Zero-Shot Classification..."
python "$SCRIPT_DIR/run_zeroshot.py"

echo "=========================================="
echo "All NLP Tasks Completed Successfully!"
echo "Check the 'output/nlp' directory for the generated CSVs."
echo "=========================================="
