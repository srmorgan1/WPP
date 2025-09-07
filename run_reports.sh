#!/bin/bash
# Convenience script to run RunReports.py from project root
# Usage: ./run_reports.sh [YYYY-MM-DD]

# Get the directory where this script is located (project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR/src"

# If no date provided, try to get it from the database
if [ $# -eq 0 ]; then
    echo "No date provided. Attempting to use date from database..."
    uv run python -m wpp.RunReports
else
    echo "Running RunReports with date: $1"
    uv run python -m wpp.RunReports --qube_date $1 --bos_date $1
fi

echo "RunReports completed."