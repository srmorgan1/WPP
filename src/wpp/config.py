import datetime as dt
import os
from functools import cache
from pathlib import Path

import toml

# NB: These must be set to the correct locations on your system
if os.name == "posix":
    WPP_ROOT_DIR = Path("/Users/steve/Work/WPP")
else:
    WPP_ROOT_DIR = Path(r"\\SBS\public\qube\iSite\AutoBOSShelleyAngeAndSandra")
    # WPP_ROOT_DIR = Path(r'Z:/qube/iSite/AutoBOSShelleyAngeAndSandra')
    # WPP_ROOT_DIR = Path(os.path.normpath(os.path.join(sys.path[0], os.pardir)))


def set_wpp_root_dir(root_dir: str) -> None:
    global WPP_ROOT_DIR
    WPP_ROOT_DIR = Path(root_dir)


def get_wpp_root_dir() -> Path:
    return WPP_ROOT_DIR


def get_wpp_input_dir() -> Path:
    return WPP_ROOT_DIR / "Inputs"


def get_wpp_static_input_dir() -> Path:
    return WPP_ROOT_DIR / "Inputs"  # Assuming static inputs are also in Inputs for now


def get_wpp_report_dir() -> Path:
    return WPP_ROOT_DIR / "Reports"


def get_wpp_log_dir() -> Path:
    return WPP_ROOT_DIR / "Logs"


def get_wpp_db_dir() -> Path:
    return WPP_ROOT_DIR / "Database"


def get_wpp_db_file() -> Path:
    return get_wpp_db_dir() / "WPP_DB.db"


def get_wpp_excel_log_file(date: dt.date) -> Path:
    return get_wpp_report_dir() / f"Data_Import_Issues_{date.strftime('%Y-%m-%d')}.xlsx"


def get_wpp_report_file(date: dt.date | dt.datetime) -> Path:
    return get_wpp_report_dir() / f"WPP_Report_{date.isoformat().replace(':', '.')}.xlsx"


def get_wpp_update_database_log_file(date: dt.date | dt.datetime) -> Path:
    return get_wpp_log_dir() / f"Log_UpdateDatabase_{str(date).replace(':', '.')}.txt"


def get_wpp_run_reports_log_file(date: dt.date | dt.datetime) -> Path:
    return get_wpp_log_dir() / f"Log_RunReports_{str(date).replace(':', '.')}.txt"


@cache
def get_config(file_path: str | None = None) -> dict:
    """
    Load configuration values from a TOML file.

    :return: A dictionary containing the configuration values.
    """
    config_file_path = file_path or Path(__file__).resolve().parent / "config.toml"

    try:
        with open(config_file_path) as config_file:
            return toml.load(config_file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file '{config_file_path}' not found.")
    except toml.TomlDecodeError as e:
        raise ValueError(f"Error parsing TOML file '{config_file_path}': {e}")
