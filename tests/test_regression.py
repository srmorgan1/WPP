import re
from pathlib import Path

import pandas as pd
from dateutil import parser
from pandas import ExcelFile

# set_wpp_root_dir is called by conftest.py's setup_wpp_root_dir
from wpp.config import get_wpp_log_dir, get_wpp_report_dir  # Import getters for dynamic paths
from wpp.RunReports import main as run_reports_main
from wpp.UpdateDatabase import main as update_database_main

# Define paths for REFERENCE files locally, as they are specific to this test's known data structure
SCRIPT_DIR = Path(__file__).resolve().parent
# WPP_ROOT_DIR for application data (like DB, Logs, Reports output) is set by conftest.py:setup_wpp_root_dir to tests/Data
REFERENCE_DATA_ROOT = SCRIPT_DIR / "Data"  # This is tests/Data
REFERENCE_REPORT_DIR = REFERENCE_DATA_ROOT / "ReferenceReports"  # tests/Data/ReferenceReports
REFERENCE_LOG_DIR = REFERENCE_DATA_ROOT / "ReferenceLogs"  # tests/Data/ReferenceLogs

# _clean_up_output_dirs and local setup_wpp_root_dir fixture are removed.
# The setup_wpp_root_dir from conftest.py will be used automatically.
# The run_decrypt_script fixture from conftest.py is session-scoped and autouse=True.


def compare_excel_files(generated_file: Path, reference_file: Path) -> None:
    assert generated_file.exists(), f"Generated Excel file not found: {generated_file}"
    assert reference_file.exists(), f"Reference Excel file not found: {reference_file}"
    with (
        ExcelFile(generated_file, engine="openpyxl") as gen_xl,
        ExcelFile(reference_file, engine="openpyxl") as ref_xl,
    ):
        assert gen_xl.sheet_names == ref_xl.sheet_names, f"Sheet names do not match between {generated_file.name} and {reference_file.name}"

        for sheet_name in gen_xl.sheet_names:
            gen_df = pd.read_excel(gen_xl, sheet_name=sheet_name)
            ref_df = pd.read_excel(ref_xl, sheet_name=sheet_name)
            pd.testing.assert_frame_equal(gen_df, ref_df, check_dtype=False, check_like=True), f"DataFrames for sheet '{sheet_name}' in {generated_file.name} and {reference_file.name} do not match"


def normalize_log_line(line: str) -> str:
    """
    Normalize a log line by removing timestamps, dates, file paths, and other dynamic content.
    """
    import re

    # Remove timestamp at beginning (HH:MM:SS format)
    line = re.sub(r"^\d{2}:\d{2}:\d{2} - ", "", line)

    # Remove log level (INFO:, WARNING:, ERROR:)
    line = re.sub(r"^(INFO|WARNING|ERROR|DEBUG): - ", "", line)

    # Remove full file paths, keeping just the filename
    line = re.sub(r"/[^/\s]*/([^/\s]+\.(xlsx|zip|txt|db))", r"\1", line)

    # Remove dates in various formats (YYYY-MM-DD, YYYY-MM-DD HH:MM:SS)
    line = re.sub(r"\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?", "DATE_PLACEHOLDER", line)

    # Remove execution times ("Done in X.X seconds")
    line = re.sub(r"Done in \d+\.\d+ seconds\.", "Done in X.X seconds.", line)

    # Remove "at DATE" timestamps
    line = re.sub(r", at \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", ", at DATE_PLACEHOLDER", line)

    # Strip whitespace
    line = line.strip()

    return line


def compare_log_files(generated_file: Path, reference_file: Path) -> None:
    assert generated_file.exists(), f"Generated log file not found: {generated_file}"
    assert reference_file.exists(), f"Reference log file not found: {reference_file}"
    with open(generated_file) as gen_file, open(reference_file) as ref_file:
        gen_lines = gen_file.readlines()
        ref_lines = ref_file.readlines()

        # Normalize and filter lines, excluding first and last lines and lines with dynamic content
        normalized_gen_lines = []
        normalized_ref_lines = []

        for line in gen_lines[1:-1]:  # Skip first and last lines
            # Skip lines that contain dynamic content that we don't want to compare
            if any(
                skip_pattern in line
                for skip_pattern in [
                    "Creating Excel spreadsheet report file",
                    "Importing irregular transaction references from file",
                    "Importing Properties from file",
                    "Importing Estates from file",
                    "Importing Qube balances from file",
                    "Importing bank accounts from file",
                    "Importing Bank Account Transactions from file",
                    "Importing Bank Account balances from file",
                    "Beginning Import of data into the database",
                ]
            ):
                continue

            normalized_line = normalize_log_line(line)
            if normalized_line:  # Only add non-empty lines
                normalized_gen_lines.append(normalized_line)

        for line in ref_lines[1:-1]:  # Skip first and last lines
            # Skip the same dynamic content lines
            if any(
                skip_pattern in line
                for skip_pattern in [
                    "Creating Excel spreadsheet report file",
                    "Importing irregular transaction references from file",
                    "Importing Properties from file",
                    "Importing Estates from file",
                    "Importing Qube balances from file",
                    "Importing bank accounts from file",
                    "Importing Bank Account Transactions from file",
                    "Importing Bank Account balances from file",
                    "Beginning Import of data into the database",
                ]
            ):
                continue

            normalized_line = normalize_log_line(line)
            if normalized_line:  # Only add non-empty lines
                normalized_ref_lines.append(normalized_line)

        # Compare the normalized lines
        if normalized_gen_lines != normalized_ref_lines:
            print(f"\nLog file comparison failed for {generated_file.name} vs {reference_file.name}")
            print(f"Generated lines ({len(normalized_gen_lines)}):")
            for i, line in enumerate(normalized_gen_lines[:10]):  # Show first 10 lines
                print(f"  {i}: {line}")
            print(f"Reference lines ({len(normalized_ref_lines)}):")
            for i, line in enumerate(normalized_ref_lines[:10]):  # Show first 10 lines
                print(f"  {i}: {line}")

        assert normalized_gen_lines == normalized_ref_lines, f"Log files {generated_file.name} and {reference_file.name} do not match after normalization"


def remove_date_suffix(filename: str) -> str:
    # Removes a suffix like _YYYY-MM-DD.xlsx or _YYYY_MM_DD.xlsx from the filename
    return re.sub(r"_[0-9]{4}[-_][0-9]{2}[-_][0-9]{2}\.xlsx$", "", filename)


def remove_log_date_suffix(filename: str) -> str:
    # Removes a suffix like _YYYY-MM-DD.txt or _YYYY_MM_DD.txt or _YYYY-MM-DD_HHMMSS.txt from the filename
    return re.sub(r"_\d{4}-\d{2}-\d{2}\s?.+?\.txt$", "", filename)


# setup_wpp_root_dir and run_decrypt_script fixtures are injected from conftest.py
def test_regression(setup_wpp_root_dir, run_decrypt_script) -> None:
    # Import here to avoid circular imports
    from wpp.config import get_wpp_db_file

    # Clean up any existing log files to avoid interference from other tests
    log_dir = get_wpp_log_dir()
    if log_dir.exists():
        for log_file in log_dir.glob("*.txt"):
            log_file.unlink()

    # Clean up the main database file to ensure fresh data import
    # This is needed because other tests may have populated the database
    main_db_file = get_wpp_db_file()
    if main_db_file.exists():
        main_db_file.unlink()

    # Run UpdateDatabase
    update_database_main()

    # Run RunReports
    qube_date = parser.parse("2022-10-11").date()
    bos_date = qube_date

    run_reports_main(qube_date=qube_date, bos_date=bos_date)

    # Compare generated reports with reference reports
    # Use get_wpp_report_dir() which respects the WPP_ROOT_DIR set by conftest
    generated_reports = sorted([report for report in get_wpp_report_dir().iterdir() if report.suffix == ".xlsx"])
    reference_reports = sorted([report for report in REFERENCE_REPORT_DIR.iterdir() if report.suffix == ".xlsx"])

    assert len(generated_reports) > 0, "No reports were generated."
    assert len(reference_reports) > 0, "No reference reports found."

    # Group reference reports by type (prefix before date)
    reference_by_type = {
        "WPP_Report": next((ref for ref in reference_reports if ref.name.startswith("WPP_Report_")), None),
        "Data_Import_Issues": next((ref for ref in reference_reports if ref.name.startswith("Data_Import_Issues_")), None),
    }

    for generated_report in generated_reports:
        ref_file = remove_date_suffix(generated_report.name)
        ref_file_to_compare = reference_by_type.get(ref_file)
        assert ref_file_to_compare is not None, f"No matching reference report found for generated report: {generated_report.name}."
        compare_excel_files(generated_report, ref_file_to_compare)

    # Compare generated logs with reference logs
    generated_log_dir = Path(get_wpp_log_dir())
    generated_logs = sorted([log for log in generated_log_dir.iterdir() if log.suffix == ".txt"])
    reference_logs = sorted([log for log in REFERENCE_LOG_DIR.iterdir() if log.suffix == ".txt"])

    assert len(generated_logs) > 0, "No logs were generated."
    assert len(reference_logs) > 0, "No reference logs found."

    # Group reference logs by type (prefix before date)
    reference_log_by_type = {
        "Log_UpdateDatabase": next((ref for ref in reference_logs if ref.name.startswith("Log_UpdateDatabase_")), None),
        "Log_RunReports": next((ref for ref in reference_logs if ref.name.startswith("Log_RunReports_")), None),
    }

    for generated_log in generated_logs:
        log_type = remove_log_date_suffix(generated_log.name)
        ref_log_to_compare = reference_log_by_type.get(log_type)
        assert ref_log_to_compare is not None, f"No matching reference log found for generated log: {generated_log.name}."
        compare_log_files(generated_log, ref_log_to_compare)
