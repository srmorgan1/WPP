import os
from pathlib import Path
import pytest
import subprocess
from wpp.config import set_wpp_root_dir, get_wpp_db_dir
from wpp.db import get_or_create_db


@pytest.fixture(scope="session", autouse=True)
def run_decrypt_script():
    """
    Run the decrypt shell script before tests.
    """
    decrypt_script_path = Path(__file__).resolve().parent.parent / "decrypt_test_data.sh"
    if not decrypt_script_path.exists():
        raise FileNotFoundError(f"Decrypt script not found at {decrypt_script_path}")

    result = subprocess.run(["bash", str(decrypt_script_path)], check=True, capture_output=True, text=True, env={**os.environ, "GPG_PASSPHRASE": os.getenv("GPG_PASSPHRASE", "")})
    if result.returncode != 0:
        raise RuntimeError(f"Decrypt script failed: {result.stderr}")
    print(result.stdout)


@pytest.fixture
def setup_wpp_root_dir():
    WPP_ROOT_DIR = Path(__file__).resolve().parent / "Data"
    set_wpp_root_dir(str(WPP_ROOT_DIR))
    yield


@pytest.fixture
def db_file(setup_wpp_root_dir, run_decrypt_script):
    return Path(get_wpp_db_dir() / "test_WPP_DB.db")


@pytest.fixture
def db_conn(db_file):
    conn = get_or_create_db(db_file)
    yield conn
    conn.close()
    os.remove(db_file)
