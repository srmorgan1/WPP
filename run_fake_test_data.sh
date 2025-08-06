#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the Python script using uv from the script's directory
# Pass all command-line arguments to the python script
uv run python "$SCRIPT_DIR/fake_test_data.py" "$@"
