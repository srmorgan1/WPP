import datetime as dt
import os
import shutil  # Added
import sqlite3
import subprocess
from pathlib import Path

import pytest
from dateutil import parser

from wpp.config import get_wpp_db_dir, set_wpp_root_dir
from wpp.db import get_or_create_db

# Override deprecated SQLite date adapters for tests to prevent Python 3.12+ warnings
# This is needed because tests pass date objects as query parameters, triggering adaptation
sqlite3.register_adapter(dt.date, str)
sqlite3.register_adapter(dt.datetime, str)

# Define paths relative to conftest.py (which is in tests/ directory)
CONFTEST_SCRIPT_DIR = Path(__file__).resolve().parent  # tests/
WPP_TEST_DATA_ROOT = CONFTEST_SCRIPT_DIR / "Data"  # tests/Data/


# Test-specific directory functions that use get_wpp_data_dir()
def get_test_scenarios_dir():
    """Get the TestScenarios directory under the current data root."""
    return WPP_TEST_DATA_ROOT / "TestScenarios"


def get_test_reference_reports_dir(scenario_name: str):
    """Get the ReferenceReports directory for a specific test scenario."""
    return get_test_scenarios_dir() / scenario_name / "ReferenceReports"


def get_test_reference_logs_dir(scenario_name: str):
    """Get the ReferenceLogs directory for a specific test scenario."""
    return get_test_scenarios_dir() / scenario_name / "ReferenceLogs"


def _clean_up_input_dirs():
    """Cleans up decrypted input and reference files."""
    scenarios_dir = get_test_scenarios_dir()
    if scenarios_dir.exists():
        for scenario_dir in scenarios_dir.iterdir():
            if scenario_dir.is_dir():
                # Clean up decrypted input files
                inputs_dir = scenario_dir / "Inputs"
                if inputs_dir.exists():
                    for file in inputs_dir.iterdir():
                        if file.suffix in [".xlsx", ".zip", ".csv"]:
                            file.unlink(missing_ok=True)

                # Clean up decrypted reference files
                ref_reports_dir = get_test_reference_reports_dir(scenario_dir.name)
                if ref_reports_dir.exists():
                    for file in ref_reports_dir.iterdir():
                        if file.suffix == ".xlsx":
                            file.unlink(missing_ok=True)

                ref_logs_dir = get_test_reference_logs_dir(scenario_dir.name)
                if ref_logs_dir.exists():
                    for file in ref_logs_dir.iterdir():
                        if file.suffix == ".csv":
                            file.unlink(missing_ok=True)


def _clean_up_output_dirs():
    """Cleans up test output directories, temporary files, and decrypted input files."""
    from wpp.config import get_wpp_db_file, get_wpp_log_dir

    # Clean up main log directory files (*.txt and *.csv files)
    log_dir = get_wpp_log_dir()
    if log_dir.exists():
        for log_file in log_dir.glob("*.txt"):
            log_file.unlink(missing_ok=True)
        for csv_file in log_dir.glob("*.csv"):
            csv_file.unlink(missing_ok=True)

    # Clean up main database file
    main_db_file = get_wpp_db_file()
    if main_db_file.exists():
        main_db_file.unlink(missing_ok=True)

    # Clean up output directories in all test scenarios
    scenarios_dir = get_test_scenarios_dir()
    if scenarios_dir.exists():
        for scenario_dir in scenarios_dir.iterdir():
            if scenario_dir.is_dir():
                # Clean up scenario-specific output directories
                for output_dir in ["Reports", "Logs", "Database"]:
                    dir_path = scenario_dir / output_dir
                    if dir_path.exists():
                        shutil.rmtree(dir_path)


def _decrypt_scenario_files(scenario_name: str):
    """Decrypt files for a specific scenario only."""
    # Import here to avoid circular imports
    from test_regression import REGRESSION_TEST_CONFIG

    if not REGRESSION_TEST_CONFIG["run_decrypt"]:
        print(f"Skipping decrypt operation for {scenario_name} (run_decrypt=False)")
        return

    # Ensure GPG_PASSPHRASE is set
    gpg_passphrase = os.getenv("GPG_PASSPHRASE")
    if gpg_passphrase is None:
        raise ValueError("GPG_PASSPHRASE environment variable not set. Decryption cannot proceed.")

    scenario_dir = get_test_scenarios_dir() / scenario_name
    if not scenario_dir.exists():
        raise FileNotFoundError(f"Scenario directory not found: {scenario_dir}")

    print(f"Decrypting files for scenario: {scenario_name}")

    # Function to decrypt files with specified suffixes in a given directory
    def decrypt_files_in_dir(directory: Path, suffixes: list[str]):
        if not directory.exists():
            return
        for suffix in suffixes:
            for file in directory.glob(f"*.{suffix}.gpg"):
                output_file = file.with_suffix("")  # Remove .gpg extension
                try:
                    result = subprocess.run(
                        ["gpg", "--decrypt", "--batch", "--yes", "--passphrase", gpg_passphrase, "--output", str(output_file), str(file)], check=True, capture_output=True, text=True
                    )
                    if result.returncode != 0:
                        raise RuntimeError(f"Failed to decrypt {file}: {result.stderr}")
                    print(f"Decrypted {file} to {output_file}")
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Failed to decrypt {file}: {e.stderr}")

    # Decrypt xlsx and zip files in scenario inputs
    decrypt_files_in_dir(scenario_dir / "Inputs", ["xlsx", "zip"])

    # Decrypt xlsx files in scenario reference reports
    decrypt_files_in_dir(scenario_dir / "ReferenceReports", ["xlsx"])

    # Decrypt csv files in scenario reference logs
    decrypt_files_in_dir(scenario_dir / "ReferenceLogs", ["csv"])


def _encrypt_scenario_files(scenario_name: str):
    """Encrypt files for a specific scenario only."""
    # Import here to avoid circular imports
    from test_regression import REGRESSION_TEST_CONFIG

    if not REGRESSION_TEST_CONFIG["run_encrypt"]:
        print(f"Skipping encrypt operation for {scenario_name} (run_encrypt=False)")
        return

    # Ensure GPG_PASSPHRASE is set
    gpg_passphrase = os.getenv("GPG_PASSPHRASE")
    if gpg_passphrase is None:
        print("GPG_PASSPHRASE not set, skipping encryption")
        return

    scenario_dir = get_test_scenarios_dir() / scenario_name
    if not scenario_dir.exists():
        return

    print(f"Encrypting files for scenario: {scenario_name}")

    # Function to encrypt files with specified suffixes in a given directory
    def encrypt_files_in_dir(directory: Path, suffixes: list[str]):
        if not directory.exists():
            return
        for suffix in suffixes:
            for file in directory.glob(f"*.{suffix}"):
                # Skip if encrypted version already exists
                encrypted_file = file.with_suffix(file.suffix + ".gpg")
                if encrypted_file.exists():
                    continue
                try:
                    result = subprocess.run(
                        ["gpg", "--symmetric", "--batch", "--yes", "--passphrase", gpg_passphrase, "--output", str(encrypted_file), str(file)], check=True, capture_output=True, text=True
                    )
                    if result.returncode != 0:
                        raise RuntimeError(f"Failed to encrypt {file}: {result.stderr}")
                    print(f"Encrypted {file} to {encrypted_file}")
                    # Remove the unencrypted file after successful encryption
                    file.unlink()
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Failed to encrypt {file}: {e.stderr}")

    # Encrypt files in scenario inputs
    encrypt_files_in_dir(scenario_dir / "Inputs", ["xlsx", "zip"])

    # Encrypt files in scenario reference reports
    encrypt_files_in_dir(scenario_dir / "ReferenceReports", ["xlsx"])

    # Encrypt files in scenario reference logs
    encrypt_files_in_dir(scenario_dir / "ReferenceLogs", ["csv"])


def _encrypt_reference_data_after_generation(scenario_name: str):
    """
    Force encryption of reference data after generation, regardless of run_encrypt setting.
    This ensures that newly generated reference data is properly encrypted.
    """
    # Ensure GPG_PASSPHRASE is set
    gpg_passphrase = os.getenv("GPG_PASSPHRASE")
    if gpg_passphrase is None:
        print("GPG_PASSPHRASE not set, skipping encryption of reference data")
        return

    scenario_dir = get_test_scenarios_dir() / scenario_name
    if not scenario_dir.exists():
        return

    print(f"Encrypting reference data for scenario: {scenario_name}")

    # Function to encrypt files with specified suffixes in a given directory
    def encrypt_files_in_dir(directory: Path, suffixes: list[str]):
        if not directory.exists():
            return
        for suffix in suffixes:
            for file in directory.glob(f"*.{suffix}"):
                # Skip if encrypted version already exists
                encrypted_file = file.with_suffix(file.suffix + ".gpg")
                if encrypted_file.exists():
                    print(f"Encrypted version already exists: {encrypted_file}")
                    continue
                try:
                    result = subprocess.run(
                        ["gpg", "--symmetric", "--batch", "--yes", "--passphrase", gpg_passphrase, "--output", str(encrypted_file), str(file)], check=True, capture_output=True, text=True
                    )
                    if result.returncode != 0:
                        raise RuntimeError(f"Failed to encrypt {file}: {result.stderr}")
                    print(f"Encrypted {file} to {encrypted_file}")
                    # Remove the unencrypted file after successful encryption
                    file.unlink()
                    print(f"Removed unencrypted file: {file}")
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Failed to encrypt {file}: {e.stderr}")

    # Encrypt files in all relevant directories
    encrypt_files_in_dir(scenario_dir / "Inputs", ["xlsx", "csv"])
    encrypt_files_in_dir(scenario_dir / "ReferenceReports", ["xlsx"])
    encrypt_files_in_dir(scenario_dir / "ReferenceLogs", ["csv"])

    # Clean up any remaining unencrypted reference files
    _cleanup_unencrypted_reference_files(scenario_name)


def _cleanup_unencrypted_reference_files(scenario_name: str):
    """
    Remove unencrypted reference files that have encrypted versions.
    This handles files that were decrypted at the start of tests but should remain encrypted.
    """
    scenario_dir = get_test_scenarios_dir() / scenario_name

    print(f"Cleaning up unencrypted reference files for scenario: {scenario_name}")

    # Clean up unencrypted reference files that have encrypted versions
    for ref_dir, suffixes in [(scenario_dir / "ReferenceReports", ["xlsx"]), (scenario_dir / "ReferenceLogs", ["csv"])]:
        if ref_dir.exists():
            for suffix in suffixes:
                for unencrypted_file in ref_dir.glob(f"*.{suffix}"):
                    encrypted_version = unencrypted_file.with_suffix(unencrypted_file.suffix + ".gpg")
                    if encrypted_version.exists():
                        print(f"Removing unencrypted reference file: {unencrypted_file}")
                        unencrypted_file.unlink()


@pytest.fixture
def clean_output_dirs():
    """Cleans up test output directories before a test runs."""
    # Import here to avoid circular imports
    from test_regression import REGRESSION_TEST_CONFIG

    if REGRESSION_TEST_CONFIG["run_delete"]:
        _clean_up_output_dirs()


def _clean_up_scenario_output_files_only(scenario_name: str):
    """Clean up generated output files for a specific scenario only. Does not touch input files or reference files."""
    scenario_dir = get_test_scenarios_dir() / scenario_name

    # Clean up scenario-specific generated output directories only
    for output_dir in ["Reports", "Logs", "Database"]:
        dir_path = scenario_dir / output_dir
        if dir_path.exists():
            # Remove entire directory to ensure clean state
            shutil.rmtree(dir_path)


def _clean_up_scenario_files(scenario_name: str):
    """Clean up all generated files for a specific scenario including decrypted input files. Does not touch reference files."""
    scenario_dir = get_test_scenarios_dir() / scenario_name

    # Clean up scenario-specific generated output directories
    for output_dir in ["Reports", "Logs", "Database"]:
        dir_path = scenario_dir / output_dir
        if dir_path.exists():
            # Remove entire directory to ensure clean state
            shutil.rmtree(dir_path)

    # Clean up decrypted input files for this scenario only
    inputs_dir = scenario_dir / "Inputs"
    if inputs_dir.exists():
        for file in inputs_dir.iterdir():
            if file.suffix in [".xlsx", ".zip", ".csv"]:
                file.unlink(missing_ok=True)


@pytest.fixture(scope="session")  # Replaces the old setup_wpp_root_dir
def setup_wpp_root_dir():
    """Sets up WPP root directory for tests."""
    set_wpp_root_dir(str(WPP_TEST_DATA_ROOT))
    yield

    # Per-scenario operations handle all encrypt/decrypt/cleanup now
    pass


@pytest.fixture
def db_file(setup_wpp_root_dir):
    """Provides the path to the test database file."""
    # get_wpp_db_dir() will use the current data dir due to setup_wpp_root_dir
    db_path = Path(get_wpp_db_dir()) / "test_WPP_DB.db"
    return db_path


@pytest.fixture
def db_conn(db_file):
    """Provides a database connection for tests and handles cleanup."""
    # Import here to avoid circular imports
    from test_regression import REGRESSION_TEST_CONFIG

    conn = get_or_create_db(db_file)  # get_or_create_db can handle Path object
    yield conn
    conn.close()
    # Only remove database file if run_delete is enabled
    if REGRESSION_TEST_CONFIG["run_delete"] and db_file.exists():
        os.remove(db_file)


def get_unique_date_from_charges(db_conn) -> dt.date:
    """Get the single unique date from the charges table at_date column.
    Assert that there is exactly one unique date."""
    cursor = db_conn.cursor()
    cursor.execute("SELECT DISTINCT at_date FROM Charges")
    unique_dates = cursor.fetchall()

    assert len(unique_dates) == 1, f"Expected exactly one unique date in Charges table, found {len(unique_dates)}: {unique_dates}"

    date_str = unique_dates[0][0]
    # Parse the date string to a date object
    if isinstance(date_str, str):
        return parser.parse(date_str).date()
    else:
        # If it's already a date object
        return date_str


@pytest.fixture(autouse=True)
def cleanup_ref_matcher_csv_files():
    """Automatically clean up ref_matcher CSV files after each test."""
    import glob
    
    yield  # Let the test run
    
    # Clean up any ref_matcher CSV files after the test
    test_data_dir = Path(__file__).parent / "Data"
    csv_files = glob.glob(str(test_data_dir / "**" / "ref_matcher*.csv"), recursive=True)
    for csv_file in csv_files:
        Path(csv_file).unlink(missing_ok=True)
    
    # Also check the root tests directory
    root_csv_files = glob.glob(str(Path(__file__).parent / "ref_matcher*.csv"))
    for csv_file in root_csv_files:
        Path(csv_file).unlink(missing_ok=True)
    
    # Reset the singleton matcher to prevent state pollution
    try:
        from wpp.ref_matcher import _reset_matcher
        _reset_matcher()
    except ImportError:
        pass  # ref_matcher might not be available in all test contexts
