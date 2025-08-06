#!/bin/bash
# macOS/Linux shell script to build WPP executable
# Requires uv package manager to be installed

set -e  # Exit on any error

echo "Starting WPP executable build process..."

# Check if we're in the project root
if [ ! -f "pyproject.toml" ]; then
    echo "Error: Must run from project root directory"
    echo "Please navigate to the WPP project directory first"
    exit 1
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv package manager not found"
    echo "Please install uv from https://docs.astral.sh/uv/"
    exit 1
fi

echo "Found uv: $(uv --version)"

echo "Running build script with uv..."

# Run the build script using uv
uv run build_executable.py

echo ""
echo "Build completed successfully!"
echo ""
echo "Executable files created in: dist/wpp/"
echo ""
echo "Available executables:"
echo "  wpp-streamlit        - Streamlit web application"
echo "  run-reports          - Command-line reports generator"
echo "  update-database      - Database update utility"
echo ""
echo "Usage:"
echo "  To run the web app: ./dist/wpp/wpp-streamlit"
echo "  To run reports: ./dist/wpp/run-reports"
echo "  To update database: ./dist/wpp/update-database"
echo ""

# Make executables executable on Unix systems
chmod +x dist/wpp/wpp-streamlit 2>/dev/null || true
chmod +x dist/wpp/run-reports 2>/dev/null || true
chmod +x dist/wpp/update-database 2>/dev/null || true

echo "Executables have been made executable."