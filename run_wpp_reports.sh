#!/bin/sh
# Run with arg YYYY-MM-DD
# e.g. run_wpp_reports.sh 2016-01-01


pushd .
cd /Users/Steve/PycharmProjects/WPP
PYTHONPATH=src
uv run src/wpp/UpdateDatabase.py
uv run src/wpp/RunReports.py --qube_date $1 --bos_date $1
popd
