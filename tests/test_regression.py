import re
import shutil
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from pandas import ExcelFile

from wpp.config import get_wpp_log_dir, get_wpp_report_dir
from wpp.RunReports import main as run_reports_main
from wpp.UpdateDatabase import main as update_database_main

# Test scenarios will be found using the conftest functions

# Test scenario configurations
TEST_SCENARIOS = [
    "scenario_default",
    # Add more scenarios here as needed
    "2025-08-01",
    # "scenario_edge_cases",  # ← Uncomment and modify as needed
]

# Regression test operation configuration
# Set these to False to skip specific operations during testing
REGRESSION_TEST_CONFIG = {
    "run_decrypt": True,  # Whether to run   decrypt operations on test data
    "run_encrypt": True,  # Whether to re-encrypt/remove decrypted data after tests
    "run_delete": True,  # Whether to run cleanup/delete operations on test files
    "generate_reference_data": False,  # Whether to copy generated logs/reports to reference directories
}


def get_scenario_paths(scenario_name: str) -> tuple[Path, Path, Path]:
    """Get input, reference logs, and reference reports paths for a test scenario."""
    from conftest import get_test_reference_logs_dir, get_test_reference_reports_dir, get_test_scenarios_dir

    scenario_dir = get_test_scenarios_dir() / scenario_name
    inputs_dir = scenario_dir / "Inputs"
    reference_logs_dir = get_test_reference_logs_dir(scenario_name)
    reference_reports_dir = get_test_reference_reports_dir(scenario_name)

    return (inputs_dir, reference_logs_dir, reference_reports_dir)


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
    return re.sub(r"_\d{4}[-_]\d{2}[-_]\d{2}\.xlsx$", "", filename)


def remove_log_date_suffix(filename: str) -> str:
    # Removes a suffix like _YYYY-MM-DD.txt or _YYYY-MM-DD_HH-MM-SS.txt from the filename
    return re.sub(r"_\d{4}-\d{2}-\d{2}(_\d{2}-\d{2}-\d{2})?\.txt$", "", filename)


def _copy_generated_to_references(scenario: str, generated_reports_dir: Path, generated_logs_dir: Path, reference_reports_dir: Path, reference_logs_dir: Path) -> None:
    """
    Copy generated Reports and Logs directories to ReferenceReports and ReferenceLogs.
    Always overwrites existing reference directories when called.
    """
    print(f"\nGenerating reference files for scenario: {scenario}")

    # Copy entire Reports directory to ReferenceReports
    print(f"Copying {generated_reports_dir} to {reference_reports_dir}")
    if reference_reports_dir.exists():
        shutil.rmtree(reference_reports_dir)  # Remove existing directory first
    shutil.copytree(generated_reports_dir, reference_reports_dir)

    # Copy entire Logs directory to ReferenceLogs
    print(f"Copying {generated_logs_dir} to {reference_logs_dir}")
    if reference_logs_dir.exists():
        shutil.rmtree(reference_logs_dir)  # Remove existing directory first
    shutil.copytree(generated_logs_dir, reference_logs_dir)


@pytest.mark.parametrize("scenario", TEST_SCENARIOS)
@patch("wpp.config.get_wpp_data_dir")
def test_regression(mock_data_dir, scenario: str, setup_wpp_root_dir) -> None:
    """Test regression for different scenarios."""
    # Import here to avoid circular imports
    # Set up mock to point to the scenario directory
    from conftest import _clean_up_scenario_files, _decrypt_scenario_files, _encrypt_scenario_files, get_test_scenarios_dir

    from wpp.ref_matcher import _reset_matcher

    # Reset singleton state for test isolation
    _reset_matcher()

    scenario_dir = get_test_scenarios_dir() / scenario
    mock_data_dir.return_value = scenario_dir

    # Enable logging for the ref_matcher with the correct scenario path
    from wpp.ref_matcher import _get_matcher

    matcher = _get_matcher()
    matcher.enable_logging()  # This will use the mocked data directory path

    # Decrypt files for this scenario only
    _decrypt_scenario_files(scenario)

    # Get paths for this test scenario
    inputs_dir, reference_logs_dir, reference_reports_dir = get_scenario_paths(scenario)

    # Verify the test scenario exists
    assert inputs_dir.exists(), f"Test scenario input directory not found: {inputs_dir}"

    # Skip reference directory validation when generating references
    if not REGRESSION_TEST_CONFIG["generate_reference_data"]:
        assert reference_logs_dir.exists(), f"Test scenario reference logs directory not found: {reference_logs_dir}"
        assert reference_reports_dir.exists(), f"Test scenario reference reports directory not found: {reference_reports_dir}"

    # Clean up any existing generated files for this scenario to ensure clean state (but not decrypted input files)
    if REGRESSION_TEST_CONFIG["run_delete"]:
        from conftest import _clean_up_scenario_output_files_only

        _clean_up_scenario_output_files_only(scenario)

    # Run UpdateDatabase
    update_database_main()

    # List files in log dir for debugging
    log_dir_path = get_wpp_log_dir()
    print(f"Listing files in {log_dir_path} for scenario {scenario}:")
    for f in log_dir_path.iterdir():
        print(f)

    # Run RunReports
    # Get the date from the database that was loaded by UpdateDatabase
    from conftest import get_unique_date_from_charges

    from wpp.config import get_wpp_db_file
    from wpp.db import get_or_create_db

    # Connect to the database that UpdateDatabase just populated
    db_path = get_wpp_db_file()  # This is the database UpdateDatabase writes to
    temp_db_conn = get_or_create_db(db_path)
    try:
        qube_date = get_unique_date_from_charges(temp_db_conn)
        bos_date = qube_date
    finally:
        temp_db_conn.close()

    try:
        run_reports_main(qube_date=qube_date, bos_date=bos_date)
    except RuntimeError as e:
        if REGRESSION_TEST_CONFIG["generate_reference_data"]:
            print(f"RunReports failed: {e}")
            print("Continuing with reference generation using available files...")
        else:
            raise  # Re-raise if not generating references

    # Copy generated results to reference directories if requested and they don't exist yet
    if REGRESSION_TEST_CONFIG["generate_reference_data"]:
        _copy_generated_to_references(scenario, get_wpp_report_dir(), get_wpp_log_dir(), reference_reports_dir, reference_logs_dir)
        # If we're generating references, skip the comparison tests
        print(f"Reference generation complete for scenario: {scenario}")

        # Encrypt all reference data after generation
        from conftest import _encrypt_reference_data_after_generation

        _encrypt_reference_data_after_generation(scenario)

        # Cleanup after reference generation
        if REGRESSION_TEST_CONFIG["run_encrypt"]:
            _encrypt_scenario_files(scenario)

        if REGRESSION_TEST_CONFIG["run_delete"]:
            _clean_up_scenario_files(scenario)

        return

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
    generated_log_dir = Path(get_wpp_log_dir())
    generated_ref_matcher_logs = list(generated_log_dir.glob("ref_matcher*.csv"))
    assert len(generated_ref_matcher_logs) == 1, f"Expected 1 ref_matcher csv file, but found {len(generated_ref_matcher_logs)} in {generated_log_dir} for scenario {scenario}"
    generated_ref_matcher_log = generated_ref_matcher_logs[0]

    reference_ref_matcher_logs = list(reference_logs_dir.glob("ref_matcher*.csv"))
    assert len(reference_ref_matcher_logs) == 1, f"Expected 1 reference ref_matcher csv file, but found {len(reference_ref_matcher_logs)} in {reference_logs_dir} for scenario {scenario}"
    reference_ref_matcher_log = reference_ref_matcher_logs[0]

    compare_csv_files(generated_ref_matcher_log, reference_ref_matcher_log)

    # Per-scenario cleanup and encrypt after test completes
    if REGRESSION_TEST_CONFIG["run_encrypt"]:
        _encrypt_scenario_files(scenario)

    if REGRESSION_TEST_CONFIG["run_delete"]:
        _clean_up_scenario_files(scenario)

        # Also clean up unencrypted reference files that were decrypted for comparison
        from conftest import _cleanup_unencrypted_reference_files

        _cleanup_unencrypted_reference_files(scenario)
