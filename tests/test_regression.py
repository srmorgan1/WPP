import pytest
import re
from pathlib import Path
from unittest.mock import patch
from typing import Generator

import pandas as pd
from dateutil import parser
from pandas import ExcelFile

from wpp.config import get_wpp_log_dir, get_wpp_report_dir, get_wpp_input_dir, get_wpp_static_input_dir, get_config
from wpp.RunReports import main as run_reports_main
from wpp.UpdateDatabase import main as update_database_main

# Define paths for test scenarios
SCRIPT_DIR = Path(__file__).resolve().parent
TEST_SCENARIOS_DIR = SCRIPT_DIR / "Data" / "TestScenarios"

# Test scenario configurations
TEST_SCENARIOS = [
    "scenario_default",
    # Add more scenarios here as needed
    # "scenario_alternative",
    # "scenario_edge_cases",  # ← Uncomment and modify as needed
]


def get_scenario_paths(scenario_name: str) -> tuple[Path, Path, Path]:
    """Get input, reference logs, and reference reports paths for a test scenario."""
    scenario_dir = TEST_SCENARIOS_DIR / scenario_name
    return (
        scenario_dir / "Inputs",
        scenario_dir / "ReferenceLogs", 
        scenario_dir / "ReferenceReports"
    )




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


def compare_csv_files(generated_file: Path, reference_file: Path) -> None:
    assert generated_file.exists(), f"Generated CSV file not found: {generated_file}"
    assert reference_file.exists(), f"Reference CSV file not found: {reference_file}"

    with open(generated_file) as gen_file, open(reference_file) as ref_file:
        gen_df = pd.read_csv(gen_file)
        ref_df = pd.read_csv(ref_file)

        # Verify the basic structure first
        expected_columns = ["description", "property_ref", "block_ref", "tenant_ref", "strategy"]
        assert list(gen_df.columns) == expected_columns, f"Generated CSV columns {list(gen_df.columns)} don't match expected {expected_columns}"
        assert list(ref_df.columns) == expected_columns, f"Reference CSV columns {list(ref_df.columns)} don't match expected {expected_columns}"

        # Compare the dataframes
        pd.testing.assert_frame_equal(gen_df, ref_df, check_dtype=False, check_like=True)


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


@pytest.mark.parametrize("scenario", TEST_SCENARIOS)
@patch('wpp.config.get_wpp_data_dir')
def test_regression(mock_data_dir, scenario: str, setup_wpp_root_dir, run_decrypt_script) -> None:
    """Test regression for different scenarios."""
    # Import here to avoid circular imports
    from wpp.config import get_wpp_db_file

    # Set up mock to point to the scenario directory
    scenario_dir = TEST_SCENARIOS_DIR / scenario
    mock_data_dir.return_value = scenario_dir

    # Get paths for this test scenario
    inputs_dir, reference_logs_dir, reference_reports_dir = get_scenario_paths(scenario)
    
    # Verify the test scenario exists
    assert inputs_dir.exists(), f"Test scenario input directory not found: {inputs_dir}"
    assert reference_logs_dir.exists(), f"Test scenario reference logs directory not found: {reference_logs_dir}"
    assert reference_reports_dir.exists(), f"Test scenario reference reports directory not found: {reference_reports_dir}"
    
    # Clean up any existing log files to avoid interference from other tests
    log_dir = get_wpp_log_dir()
    if log_dir.exists():
        for log_file in log_dir.glob("*.txt"):
            log_file.unlink()
        # Also clean up any existing ref_matcher.csv
        ref_matcher_csv = log_dir / "ref_matcher.csv"
        if ref_matcher_csv.exists():
            ref_matcher_csv.unlink()

    # Clean up the main database file to ensure fresh data import
    # This is needed because other tests may have populated the database
    main_db_file = get_wpp_db_file()
    if main_db_file.exists():
        main_db_file.unlink()

    # Run UpdateDatabase
    update_database_main()

    # List files in log dir for debugging
    log_dir_path = get_wpp_log_dir()
    print(f"Listing files in {log_dir_path} for scenario {scenario}:")
    for f in log_dir_path.iterdir():
        print(f)

    # Run RunReports
    qube_date = parser.parse("2022-10-11").date()
    bos_date = qube_date

    run_reports_main(qube_date=qube_date, bos_date=bos_date)

    # Compare generated reports with reference reports
    # Use get_wpp_report_dir() which respects the WPP_ROOT_DIR set by conftest
    generated_reports = sorted([report for report in get_wpp_report_dir().iterdir() if report.suffix == ".xlsx"])
    reference_reports = sorted([report for report in reference_reports_dir.iterdir() if report.suffix == ".xlsx"])

    assert len(generated_reports) > 0, f"No reports were generated for scenario {scenario}."
    assert len(reference_reports) > 0, f"No reference reports found for scenario {scenario}."

    # Group reference reports by type (prefix before date)
    reference_by_type = {
        "WPP_Report": next((ref for ref in reference_reports if ref.name.startswith("WPP_Report_")), None),
        "Data_Import_Issues": next((ref for ref in reference_reports if ref.name.startswith("Data_Import_Issues_")), None),
    }

    for generated_report in generated_reports:
        ref_file = remove_date_suffix(generated_report.name)
        ref_file_to_compare = reference_by_type.get(ref_file)
        assert ref_file_to_compare is not None, f"No matching reference report found for generated report: {generated_report.name} in scenario {scenario}."
        compare_excel_files(generated_report, ref_file_to_compare)

    # Compare generated logs with reference logs
    generated_log_dir = Path(get_wpp_log_dir())
    generated_logs = sorted([log for log in generated_log_dir.iterdir() if log.suffix == ".txt"])
    reference_logs = sorted([log for log in reference_logs_dir.iterdir() if log.suffix == ".txt"])

    assert len(generated_logs) > 0, f"No logs were generated for scenario {scenario}."
    assert len(reference_logs) > 0, f"No reference logs found for scenario {scenario}."

    # Group reference logs by type (prefix before date)
    reference_log_by_type = {
        "Log_UpdateDatabase": next((ref for ref in reference_logs if ref.name.startswith("Log_UpdateDatabase_")), None),
        "Log_RunReports": next((ref for ref in reference_logs if ref.name.startswith("Log_RunReports_")), None),
    }

    for generated_log in generated_logs:
        log_type = remove_log_date_suffix(generated_log.name)
        ref_log_to_compare = reference_log_by_type.get(log_type)
        assert ref_log_to_compare is not None, f"No matching reference log found for generated log: {generated_log.name} in scenario {scenario}."
        compare_log_files(generated_log, ref_log_to_compare)

    # Compare ref_matcher.csv
    generated_ref_matcher_log = get_wpp_log_dir() / "ref_matcher.csv"
    reference_ref_matcher_log = reference_logs_dir / "ref_matcher.csv"
    compare_csv_files(generated_ref_matcher_log, reference_ref_matcher_log)