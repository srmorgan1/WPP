#!/bin/bash
# Convenience script to run UpdateDatabase.py from project root
# Usage: ./run_update_database.sh

# Get the directory where this script is located (project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR/src"

echo "Running UpdateDatabase..."
uv run python -m wpp.UpdateDatabase
echo "UpdateDatabase completed."