import shutil
from pathlib import Path

import pandas as pd
import pytest
from dateutil import parser
from pandas import ExcelFile

from wpp.config import set_wpp_root_dir
from wpp.RunReports import main as run_reports_main
from wpp.UpdateDatabase import main as update_database_main

# Define paths
SCRIPT_DIR = Path(__file__).resolve().parent
WPP_ROOT_DIR = SCRIPT_DIR / "Data"
WPP_REPORT_DIR = WPP_ROOT_DIR / "Reports"
WPP_LOG_DIR = WPP_ROOT_DIR / "Logs"
WPP_DB_DIR = WPP_ROOT_DIR / "Database"
REFERENCE_REPORT_DIR = WPP_ROOT_DIR / "ReferenceReports"
REFERENCE_LOG_DIR = WPP_ROOT_DIR / "ReferenceLogs"


def _clean_up_output_dirs():
    # Clean up the Reports, Logs and DB directories
    if WPP_REPORT_DIR.exists():
        shutil.rmtree(WPP_REPORT_DIR)
    if WPP_LOG_DIR.exists():
        shutil.rmtree(WPP_LOG_DIR)
    if WPP_DB_DIR.exists():
        shutil.rmtree(WPP_DB_DIR)


@pytest.fixture
def setup_wpp_root_dir():
    _clean_up_output_dirs()
    set_wpp_root_dir(str(WPP_ROOT_DIR))
    # Make output dirs
    # WPP_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    # WPP_LOG_DIR.mkdir(parents=True, exist_ok=True)
    # WPP_DB_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Teardown code
    _clean_up_output_dirs()


def compare_excel_files(generated_file: Path, reference_file: Path) -> None:
    with (
        ExcelFile(generated_file, engine="openpyxl") as gen_xl,
        ExcelFile(reference_file, engine="openpyxl") as ref_xl,
    ):
        assert gen_xl.sheet_names == ref_xl.sheet_names, "Sheet names do not match"

        for sheet_name in gen_xl.sheet_names:
            gen_df = pd.read_excel(gen_xl, sheet_name=sheet_name)
            ref_df = pd.read_excel(ref_xl, sheet_name=sheet_name)
            pd.testing.assert_frame_equal(gen_df, ref_df, check_dtype=False, check_like=True)


def compare_log_files(generated_file: Path, reference_file: Path) -> None:
    with open(generated_file) as gen_file, open(reference_file) as ref_file:
        gen_lines = [" ".join(line.split(" ")[4:]) for line in gen_file.readlines()[1:-2] if "Creating" not in line and "Importing" not in line]
        ref_lines = [" ".join(line.split(" ")[4:]) for line in ref_file.readlines()[1:-2] if "Creating" not in line and "Importing" not in line]
        assert gen_lines == ref_lines, f"Log files {generated_file} and {reference_file} do not match"


def test_regression(setup_wpp_root_dir) -> None:
    # Run UpdateDatabase
    update_database_main()

    # Run RunReports
    qube_date = parser.parse("2022-10-11").date()
    bos_date = qube_date

    run_reports_main(qube_date=qube_date, bos_date=bos_date)

    # Compare generated reports with reference reports
    generated_reports = sorted([report for report in WPP_REPORT_DIR.iterdir() if report.suffix == ".xlsx"])
    reference_reports = sorted([report for report in REFERENCE_REPORT_DIR.iterdir() if report.suffix == ".xlsx"])

    assert len(generated_reports) == len(reference_reports), "Number of reports do not match"

    for generated_report, reference_report in zip(generated_reports, reference_reports):
        assert generated_report.name.split("_")[1] == reference_report.name.split("_")[1], "Report names do not match"
        compare_excel_files(generated_report, reference_report)

    # Compare generated logs with reference logs
    generated_logs = sorted([log for log in WPP_LOG_DIR.iterdir() if log.suffix == ".txt"])
    reference_logs = sorted([log for log in REFERENCE_LOG_DIR.iterdir() if log.suffix == ".txt"])

    assert len(generated_logs) == len(reference_logs), "Number of logs do not match"

    for generated_log, reference_log in zip(generated_logs, reference_logs):
        assert generated_log.name.split("_")[1] == reference_log.name.split("_")[1], "Log names do not match"
        compare_log_files(generated_log, reference_log)
