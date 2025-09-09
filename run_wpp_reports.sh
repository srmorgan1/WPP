#!/bin/sh
# Run with arg YYYY-MM-DD
# e.g. run_wpp_reports.sh 2016-01-01

if [ $# -ne 1 ]; then
    echo "Usage: $0 <Run Date: YYYY-MM-DD>"
    exit 1
fi

# Get the directory where this script is located (project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WPP_ROOT="$SCRIPT_DIR"

pushd .
cd $WPP_ROOT
export PYTHONPATH="$WPP_ROOT/src"
rm Database/*.db 2>/dev/null || true
echo "Running UpdateDatabase..."
uv run python -m wpp.UpdateDatabase
echo "Running RunReports..."
uv run python -m wpp.RunReports --qube_date $1 --bos_date $1
popd
