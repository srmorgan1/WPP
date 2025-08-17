import datetime as dt
import os
from functools import cache
from pathlib import Path

import toml

# WPP_ROOT_DIR will be initialized after get_config function is defined


def set_wpp_root_dir(root_dir: str) -> None:
    global WPP_ROOT_DIR
    WPP_ROOT_DIR = Path(root_dir)


def get_wpp_root_dir() -> Path:
    return WPP_ROOT_DIR


def get_wpp_data_dir() -> Path:
    """Get the data directory - can be overridden for tests."""
    return WPP_ROOT_DIR


def get_wpp_input_dir() -> Path:
    return get_wpp_data_dir() / "Inputs"


def get_wpp_static_input_dir() -> Path:
    return get_wpp_data_dir() / "Inputs"  # Assuming static inputs are also in Inputs for now


def get_wpp_report_dir() -> Path:
    return get_wpp_data_dir() / "Reports"


def get_wpp_log_dir() -> Path:
    return get_wpp_data_dir() / "Logs"


def get_wpp_db_dir() -> Path:
    return get_wpp_data_dir() / "Database"


def get_wpp_db_file() -> Path:
    return get_wpp_db_dir() / "WPP_DB.db"


def get_wpp_excel_log_file(date: dt.date) -> Path:
    return get_wpp_report_dir() / f"Data_Import_Issues_{date.strftime('%Y-%m-%d')}.xlsx"


def get_wpp_report_file(date: dt.date | dt.datetime) -> Path:
    return get_wpp_report_dir() / f"WPP_Report_{date.isoformat().replace(':', '.')}.xlsx"


def get_wpp_update_database_log_file(date: dt.date | dt.datetime) -> Path:
    if isinstance(date, dt.datetime):
        timestamp = date.strftime("%Y-%m-%d_%H-%M-%S")
    else:
        timestamp = date.strftime("%Y-%m-%d")
    return get_wpp_log_dir() / f"Log_UpdateDatabase_{timestamp}.txt"


def get_wpp_run_reports_log_file(date: dt.date | dt.datetime) -> Path:
    if isinstance(date, dt.datetime):
        timestamp = date.strftime("%Y-%m-%d_%H-%M-%S")
    else:
        timestamp = date.strftime("%Y-%m-%d")
    return get_wpp_log_dir() / f"Log_RunReports_{timestamp}.txt"


def get_wpp_ref_matcher_log_file(date: dt.date | dt.datetime) -> Path:
    if isinstance(date, dt.datetime):
        timestamp = date.strftime("%Y-%m-%d_%H-%M-%S")
    else:
        timestamp = date.strftime("%Y-%m-%d")
    return get_wpp_log_dir() / f"ref_matcher_{timestamp}.csv"


def get_special_case_properties() -> list[str]:
    """Get the list of properties that require special handling for tenant references."""
    config = get_config()
    return config["TENANT_REFERENCE_PARSING"]["SPECIAL_CASE_PROPERTIES"]


def get_exclude_z_suffix_properties() -> list[str]:
    """Get the list of properties that exclude Z suffix tenant references."""
    config = get_config()
    return config["TENANT_REFERENCE_PARSING"]["EXCLUDE_Z_SUFFIX_PROPERTIES"]


def get_commercial_properties() -> list[str]:
    """Get the list of properties that use commercial (COM) block references."""
    config = get_config()
    return config["TENANT_REFERENCE_PARSING"]["COMMERCIAL_PROPERTIES"]


def get_industrial_estate_properties() -> list[str]:
    """Get the list of properties that use industrial estate single-letter tenant references."""
    config = get_config()
    return config["TENANT_REFERENCE_PARSING"]["INDUSTRIAL_ESTATE_PROPERTIES"]


def get_digit_letter_suffix_properties() -> list[str]:
    """Get the list of properties that use digit-letter suffix tenant references (XXX-XX-DDDA format)."""
    config = get_config()
    return config["TENANT_REFERENCE_PARSING"]["DIGIT_LETTER_SUFFIX_PROPERTIES"]


def get_letter_digit_letter_properties() -> list[str]:
    """Get the list of properties that use digit-letter-digit tenant references (XXX-XX-0AD format)."""
    config = get_config()
    return config["TENANT_REFERENCE_PARSING"]["LETTER_DIGIT_LETTER_PROPERTIES"]


def get_double_zero_letter_properties() -> list[str]:
    """Get the list of properties that use 00X tenant references (XXX-XX-00A format)."""
    config = get_config()
    return config["TENANT_REFERENCE_PARSING"]["DOUBLE_ZERO_LETTER_PROPERTIES"]


def get_three_letter_code_properties() -> list[str]:
    """Get the list of properties that use three-letter code tenant references (XXX-XX-ABC format)."""
    config = get_config()
    return config["TENANT_REFERENCE_PARSING"]["THREE_LETTER_CODE_PROPERTIES"]


def get_two_letter_code_properties() -> list[str]:
    """Get the list of properties that use two-letter code tenant references (XXX-XX-AB format)."""
    config = get_config()
    return config["TENANT_REFERENCE_PARSING"]["TWO_LETTER_CODE_PROPERTIES"]


@cache
def get_config(file_path: str | None = None) -> dict:
    """
    Load configuration values from a TOML file.

    Searches for config.toml in the following order:
    1. Provided file_path (if given)
    2. Current working directory
    3. Same directory as this module (default location)

    :return: A dictionary containing the configuration values.
    """
    if file_path:
        config_file_path = Path(file_path)
    else:
        # Search locations in order of priority
        search_locations = [
            Path.cwd() / "config.toml",  # Current working directory
            Path(__file__).resolve().parent / "config.toml",  # Module directory (original location)
        ]

        config_file_path = None
        for location in search_locations:
            if location.exists():
                config_file_path = location
                break

        if config_file_path is None:
            # If no config file found, provide helpful error message
            searched_locations = "\n  ".join(str(loc) for loc in search_locations)
            raise FileNotFoundError(f"Configuration file 'config.toml' not found in any of the following locations:\n  {searched_locations}")

    try:
        with open(config_file_path) as config_file:
            return toml.load(config_file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file '{config_file_path}' not found.")
    except toml.TomlDecodeError as e:
        raise ValueError(f"Error parsing TOML file '{config_file_path}': {e}")


# Initialize WPP_ROOT_DIR from configuration file
def _get_wpp_root_dir_from_config() -> Path:
    """Get WPP root directory from configuration file."""
    config = get_config()
    if os.name == "posix":
        return Path(config["DIRECTORIES"]["WPP_ROOT_DIR_POSIX"])
    else:
        return Path(config["DIRECTORIES"]["WPP_ROOT_DIR_WINDOWS"])


WPP_ROOT_DIR = _get_wpp_root_dir_from_config()
