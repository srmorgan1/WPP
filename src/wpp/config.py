import datetime as dt
import os
import shutil
import sys
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
    """Get the input directory, using override if specified in config."""
    override_dir = get_wpp_input_dir_override()
    if override_dir:
        return override_dir
    return get_wpp_data_dir() / "Inputs"


def get_wpp_static_input_dir() -> Path:
    """Get the static input directory, using override if specified in config."""
    override_dir = get_wpp_static_input_dir_override()
    if override_dir:
        return override_dir
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


def get_wpp_app_log_file(date: dt.date | dt.datetime) -> Path:
    if isinstance(date, dt.datetime):
        timestamp = date.strftime("%Y-%m-%d_%H-%M-%S")
    else:
        timestamp = date.strftime("%Y-%m-%d")
    return get_wpp_log_dir() / f"Log_App_{timestamp}.txt"


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


def get_alphanumeric_properties() -> list[str]:
    """Get the list of properties that use alphanumeric property references (059A format)."""
    config = get_config()
    return config["TENANT_REFERENCE_PARSING"]["ALPHANUMERIC_PROPERTIES"]


def get_max_runtime_minutes() -> int:
    """Get the maximum runtime in minutes before auto-shutdown (0 = disabled)."""
    config = get_config()
    return config.get("SERVER", {}).get("MAX_RUNTIME_MINUTES", 60)


def get_connection_check_interval() -> int:
    """Get the connection check interval in seconds (ping interval)."""
    config = get_config()
    return config.get("SERVER", {}).get("CONNECTION_CHECK_INTERVAL", 10)


def get_no_connection_shutdown_delay() -> int:
    """Get the delay before shutdown when no connections detected (minutes)."""
    config = get_config()
    return config.get("SERVER", {}).get("NO_CONNECTION_SHUTDOWN_DELAY", 20)


def get_user_interaction_timeout() -> int:
    """Get the user interaction timeout in minutes (no API activity)."""
    config = get_config()
    return config.get("SERVER", {}).get("USER_INTERACTION_TIMEOUT", 60)


def get_web_app_use_memory_db() -> bool:
    """Get whether the web app should use an in-memory database."""
    config = get_config()
    return config.get("SERVER", {}).get("WPP_WEB_APP_USE_MEMORY_DB", False)


def get_enable_network_restrictions() -> bool:
    """Get whether network restrictions are enabled."""
    config = get_config()
    return config.get("SERVER", {}).get("ENABLE_NETWORK_RESTRICTIONS", True)


def get_allowed_networks() -> list[str]:
    """Get the list of allowed IP networks in CIDR notation."""
    config = get_config()
    return config.get("SERVER", {}).get("ALLOWED_NETWORKS", ["127.0.0.1/32", "192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"])


def get_server_bind_address() -> str:
    """Get the server bind address."""
    config = get_config()
    return config.get("SERVER", {}).get("SERVER_BIND_ADDRESS", "0.0.0.0")


def get_server_port() -> int:
    """Get the server port."""
    config = get_config()
    return config.get("SERVER", {}).get("SERVER_PORT", 8000)


def get_wpp_input_dir_override() -> Path | None:
    """Get the custom input directory path if specified in config."""
    config = get_config()
    input_dir = config.get("DIRECTORIES", {}).get("WPP_INPUT_DIR")
    return Path(input_dir) if input_dir else None


def get_wpp_static_input_dir_override() -> Path | None:
    """Get the custom static input directory path if specified in config."""
    config = get_config()
    static_input_dir = config.get("DIRECTORIES", {}).get("WPP_STATIC_INPUT_DIR")
    return Path(static_input_dir) if static_input_dir else None


def _is_running_as_executable() -> bool:
    """Check if running as a PyInstaller executable."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _get_user_home_config_path() -> Path:
    """Get the path to the user's home directory config file."""
    home = Path.home()
    # Check for both .wpp-config.toml and wpp-config.toml
    for filename in [".wpp-config.toml", "wpp-config.toml"]:
        config_path = home / filename
        if config_path.exists():
            return config_path
    # Return the preferred filename if neither exists
    return home / ".wpp-config.toml"


def _get_cwd_config_path() -> Path:
    """Get the path to the current working directory config file."""
    cwd = Path.cwd()
    # Check for both .wpp-config.toml and wpp-config.toml
    for filename in [".wpp-config.toml", "wpp-config.toml"]:
        config_path = cwd / filename
        if config_path.exists():
            return config_path
    # Return None if neither exists
    return None


def _get_default_config_path() -> Path:
    """Get the path to the default config.toml in the src directory."""
    if _is_running_as_executable():
        # In PyInstaller executable, use the bundled config location
        import sys

        base_path = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent
        config_path = base_path / "wpp" / "config.toml"
        print(f"DEBUG: Executable mode - looking for config at: {config_path}")
        return config_path
    else:
        # In development mode, use the source directory
        config_path = Path(__file__).resolve().parent / "config.toml"
        print(f"DEBUG: Development mode - looking for config at: {config_path}")
        return config_path


def _copy_default_config_to_home() -> Path:
    """Copy the default config.toml to user's home directory as .wpp-config.toml.

    If an existing config exists but differs from the bundled config, backs it up
    with install date timestamp before copying the new one. Only updates when
    configs are actually different.
    """
    default_config = _get_default_config_path()
    home_config = Path.home() / ".wpp-config.toml"

    print(f"DEBUG: Default config path: {default_config}")
    print(f"DEBUG: Default config exists: {default_config.exists()}")
    print(f"DEBUG: Home config path: {home_config}")
    print(f"DEBUG: Home config exists: {home_config.exists()}")

    if not default_config.exists():
        print(f"DEBUG: Default config file not found at: {default_config}")
        return home_config

    try:
        # If home config doesn't exist, just copy it
        if not home_config.exists():
            shutil.copy2(default_config, home_config)
            print(f"✅ Configuration file copied to: {home_config}")
            return home_config

        # Both configs exist - check if they're different
        default_content = default_config.read_text(encoding="utf-8")
        home_content = home_config.read_text(encoding="utf-8")

        if default_content != home_content:
            # Configs are different - backup old one and copy new one
            timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_config = Path.home() / f".wpp-config_{timestamp}.toml"

            # Create backup of existing config
            shutil.copy2(home_config, backup_config)
            print(f"📋 Existing config backed up to: {backup_config}")

            # Copy new config
            shutil.copy2(default_config, home_config)
            print(f"✅ Configuration file updated: {home_config}")
        else:
            print(f"ℹ️  Configuration file is already up to date: {home_config}")

    except Exception as e:
        print(f"Warning: Could not copy config file to home directory: {e}")

    return home_config


@cache
def get_config(file_path: str | None = None) -> dict:
    """
    Load configuration values from a TOML file.

    Searches for config files in the following order:
    1. Provided file_path (if given)
    2. User's home directory (.wpp-config.toml or wpp-config.toml)
    3. Current working directory (.wpp-config.toml or wpp-config.toml)
    4. Source directory (config.toml)

    If running as a Windows executable and no home config exists, copies
    the default config to the user's home directory as .wpp-config.toml.

    :return: A dictionary containing the configuration values.
    """
    if file_path:
        config_file_path = Path(file_path)
    else:
        # Search locations in order of priority
        search_locations = []

        # 1. User's home directory
        home_config = _get_user_home_config_path()
        search_locations.append(home_config)

        # 2. Current working directory
        cwd_config = _get_cwd_config_path()
        if cwd_config:
            search_locations.append(cwd_config)

        # 3. Source directory (default)
        default_config = _get_default_config_path()
        search_locations.append(default_config)

        config_file_path = None
        for location in search_locations:
            if location and location.exists():
                config_file_path = location
                break

        # If running as executable, ensure home config is up to date
        if _is_running_as_executable() and default_config.exists():
            home_config = _copy_default_config_to_home()
            if home_config.exists():
                config_file_path = home_config

        if config_file_path is None:
            # If no config file found, provide helpful error message
            searched_locations = "\n  ".join(str(loc) for loc in search_locations if loc)
            raise FileNotFoundError(f"Configuration file not found in any of the following locations:\n  {searched_locations}")

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
