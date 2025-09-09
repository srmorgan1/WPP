"""
Backward compatibility module for the old logging interface.
This module now uses the new WPPLogger interface internally.
"""

import logging
import os
import sys
from pathlib import Path

from .config import get_wpp_log_dir


#
# Set up Logging
#
class InfoFilter(logging.Filter):
    """Filters log records to allow only INFO level and below."""

    def filter(self, record):
        # Allow levels from DEBUG up to INFO
        return record.levelno <= logging.INFO


def setup_logger(module_name: str, log_file_path: Path, include_timestamp: bool = False) -> logging.Logger:
    """
    Configures and returns a logger for a given module.

    The logger will have three handlers:
    1. A file handler that logs all messages (INFO and above).
    2. A stream handler for stdout that logs INFO messages.
    3. A stream handler for stderr that logs WARNING and ERROR messages.

    This function is idempotent; it will not add duplicate handlers if called
    multiple times for the same logger.

    Args:
        module_name: Name of the module for the logger
        log_file_path: Path where log file will be written
        include_timestamp: Whether to include timestamp in log messages (default: False)

    Returns:
        logging.Logger: Standard Python logger (for backward compatibility)
    """
    os.makedirs(get_wpp_log_dir(), exist_ok=True)

    if include_timestamp:
        log_formatter = logging.Formatter("%(asctime)s - %(levelname)s: - %(message)s", datefmt="%H:%M:%S")
    else:
        log_formatter = logging.Formatter("%(levelname)s: - %(message)s")

    logger = logging.getLogger(module_name)
    logger.setLevel(logging.INFO)

    # Remove existing handlers to prevent duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # File handler (logs everything at INFO level and above)
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)

    # Stdout handler for INFO messages
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(log_formatter)
    stdout_handler.addFilter(InfoFilter())
    logger.addHandler(stdout_handler)

    # Stderr handler for WARNING and ERROR messages
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(log_formatter)
    stderr_handler.setLevel(logging.WARNING)
    logger.addHandler(stderr_handler)

    return logger
