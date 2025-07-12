import os
import shutil  # Added
from pathlib import Path
import pytest
import subprocess
from wpp.config import set_wpp_root_dir, get_wpp_db_dir
from wpp.db import get_or_create_db

# Define paths relative to conftest.py (which is in tests/ directory)
CONFTEST_SCRIPT_DIR = Path(__file__).resolve().parent  # tests/
WPP_TEST_DATA_ROOT = CONFTEST_SCRIPT_DIR / "Data"  # tests/Data/
WPP_TEST_REPORTS_DIR = WPP_TEST_DATA_ROOT / "Reports"
REFERENCE_REPORT_DIR = WPP_TEST_DATA_ROOT / "ReferenceReports" # tests/Data/ReferenceReports
INPUT_DATA_DIR = WPP_TEST_DATA_ROOT / "Inputs"
WPP_TEST_LOGS_DIR = WPP_TEST_DATA_ROOT / "Logs"
WPP_TEST_DB_DIR = WPP_TEST_DATA_ROOT / "Database"


def _clean_up_output_dirs():
    """Cleans up test output directories."""
    if WPP_TEST_REPORTS_DIR.exists():
        shutil.rmtree(WPP_TEST_REPORTS_DIR)
    if WPP_TEST_LOGS_DIR.exists():
        shutil.rmtree(WPP_TEST_LOGS_DIR)
    if WPP_TEST_DB_DIR.exists():
        shutil.rmtree(WPP_TEST_DB_DIR)

def _remove_decrypted_data():
    """Removes decrypted data files if they exist."""
    reference_reports = sorted([report for report in REFERENCE_REPORT_DIR.iterdir() if report.suffix == ".xlsx"])
    for report in reference_reports:
        report.unlink(missing_ok=True)

    reference_reports = sorted([report for report in INPUT_DATA_DIR.iterdir() if report.suffix == ".xlsx" or report.suffix == ".zip"])
    for report in reference_reports:
        report.unlink(missing_ok=True)

@pytest.fixture(scope="session", autouse=True)
def run_decrypt_script():
    """
    Run the decrypt shell script before tests.
    Ensures GPG_PASSPHRASE environment variable is set.
    """
    decrypt_script_path = Path(__file__).resolve().parent.parent / "decrypt_test_data.sh"
    if not decrypt_script_path.exists():
        raise FileNotFoundError(f"Decrypt script not found at {decrypt_script_path}")

    # Ensure GPG_PASSPHRASE is set, otherwise provide a default or raise error
    gpg_passphrase = os.getenv("GPG_PASSPHRASE")
    if gpg_passphrase is None:
        # This matches the original behavior of defaulting to "" if not set,
        # but a warning or error might be more robust if it's truly required.
        print("Warning: GPG_PASSPHRASE environment variable not set. Decryption might fail.")
        gpg_passphrase = ""

    env = {**os.environ, "GPG_PASSPHRASE": gpg_passphrase}
    result = subprocess.run(["bash", str(decrypt_script_path)], check=True, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Decrypt script failed: {result.stderr}")
    print(result.stdout)


@pytest.fixture # Replaces the old setup_wpp_root_dir
def setup_wpp_root_dir():
    """Sets up WPP root directory for tests, and cleans up output directories."""
    _clean_up_output_dirs()
    set_wpp_root_dir(str(WPP_TEST_DATA_ROOT))

    # Ensure the main output directories exist for the application to write to.
    WPP_TEST_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    WPP_TEST_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    WPP_TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
    yield
    _clean_up_output_dirs()
    _remove_decrypted_data()


@pytest.fixture
def db_file(setup_wpp_root_dir, run_decrypt_script):
    """Provides the path to the test database file, ensuring setup and data decryption."""
    # get_wpp_db_dir() will use WPP_TEST_DATA_ROOT due to setup_wpp_root_dir
    db_path = Path(get_wpp_db_dir()) / "test_WPP_DB.db"
    # Parent directory (WPP_TEST_DB_DIR) is created by setup_wpp_root_dir
    return db_path


@pytest.fixture
def db_conn(db_file): # db_file fixture ensures setup_wpp_root_dir and run_decrypt_script have run
    """Provides a database connection for tests and handles cleanup."""
    conn = get_or_create_db(db_file) # get_or_create_db can handle Path object
    yield conn
    conn.close()
    if db_file.exists(): # Check if exists before removing, good practice
        os.remove(db_file)
