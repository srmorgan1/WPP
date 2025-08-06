#!/bin/sh
# Run with arg YYYY-MM-DD
# e.g. run_wpp_reports.sh 2016-01-01

if [ $# -ne 1 ]; then
    echo "Usage: $0 <Run Date: YYYY-MM-DD>"
    exit 1
fi

WPP_ROOT=/Users/Steve/Development/PycharmProjects/WPP

pushd .
cd $WPP_ROOT
export PYTHONPATH=src
rm Database/*.db
uv run src/wpp/UpdateDatabase.py
uv run src/wpp/RunReports.py --qube_date $1 --bos_date $1
popd
