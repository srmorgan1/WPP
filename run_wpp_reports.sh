#!/bin/sh

pushd .
cd /Users/Steve/PycharmProjects/Wpp
python UpdateDatabase.py
python RunReports.py
popd
