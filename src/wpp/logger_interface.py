"""
Logger interface and implementations for flexible logging.
Supports both file logging and real-time web streaming.
"""

import logging
import os
import sys
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from pathlib import Path

from wpp.config import get_wpp_log_dir


class WPPLogger(ABC):
    """Abstract interface for all WPP loggers."""

    @abstractmethod
    def info(self, message: str):
        """Log info message."""
        pass

    @abstractmethod
    def warning(self, message: str):
        """Log warning message."""
        pass

    @abstractmethod
    def error(self, message: str):
        """Log error message."""
        pass

    @abstractmethod
    def debug(self, message: str):
        """Log debug message."""
        pass

    @abstractmethod
    def exception(self, message: str):
        """Log exception message with stack trace."""
        pass

    @abstractmethod
    def critical(self, message: str):
        """Log critical message."""
        pass


class FileLogger(WPPLogger):
    """Logger that writes to files (CLI apps)."""

    def __init__(self, logger: logging.Logger):
        """Initialize with a standard Python logger."""
        self.logger = logger

    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)

    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)

    def exception(self, message: str):
        """Log exception message with stack trace."""
        self.logger.exception(message)

    def critical(self, message: str):
        """Log critical message."""
        self.logger.critical(message)


class WebLogger(WPPLogger):
    """Logger that streams to WebSocket (web apps)."""

    def __init__(self, name: str, websocket_callback: Callable[[str], Awaitable[None]] | None = None):
        """Initialize with WebSocket callback."""
        self.logger = logging.getLogger(f"web_{name}")
        self.logger.setLevel(logging.INFO)

        # Clear any existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Add WebSocket handler
        if websocket_callback:
            websocket_handler = WebSocketLogHandler(websocket_callback)
            self.logger.addHandler(websocket_handler)

        # Also add console handler for fallback
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter("%(levelname)s: - %(message)s"))
        self.logger.addHandler(console_handler)

        # Prevent propagation to avoid interference with other loggers
        self.logger.propagate = False

    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)

    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)

    def exception(self, message: str):
        """Log exception message with stack trace."""
        self.logger.exception(message)

    def critical(self, message: str):
        """Log critical message."""
        self.logger.critical(message)


class ConsoleLogger(WPPLogger):
    """Simple console logger for basic output."""

    def __init__(self, name: str = "console", include_timestamp: bool = False):
        """Initialize console logger."""
        self.name = name
        if include_timestamp:
            self.formatter = logging.Formatter("%(asctime)s - %(levelname)s: - %(message)s", datefmt="%H:%M:%S")
        else:
            self.formatter = logging.Formatter("%(levelname)s: - %(message)s")

        # Create a simple logger
        self.logger = logging.getLogger(f"console_{name}")
        self.logger.setLevel(logging.INFO)

        # Clear handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(self.formatter)
        self.logger.addHandler(console_handler)

        self.logger.propagate = False

    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)

    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)

    def exception(self, message: str):
        """Log exception message with stack trace."""
        self.logger.exception(message)

    def critical(self, message: str):
        """Log critical message."""
        self.logger.critical(message)


class NullLogger(WPPLogger):
    """Null logger - does nothing. Useful for testing or silent mode."""

    def info(self, message: str):
        """Log info message - does nothing."""
        pass

    def warning(self, message: str):
        """Log warning message - does nothing."""
        pass

    def error(self, message: str):
        """Log error message - does nothing."""
        pass

    def debug(self, message: str):
        """Log debug message - does nothing."""
        pass

    def exception(self, message: str):
        """Log exception message - does nothing."""
        pass

    def critical(self, message: str):
        """Log critical message - does nothing."""
        pass


class WebSocketLogHandler(logging.Handler):
    """Custom log handler that sends log messages via WebSocket callback."""

    def __init__(self, websocket_callback: Callable[[str], Awaitable[None]] | None = None):
        super().__init__()
        self.websocket_callback = websocket_callback
        self.setFormatter(logging.Formatter("%(levelname)s: - %(message)s"))

    def emit(self, record):
        """Send log record via WebSocket callback."""
        if self.websocket_callback:
            try:
                msg = self.format(record)
                # Schedule the async callback in the event loop
                import asyncio
                if asyncio.get_event_loop().is_running():
                    asyncio.create_task(self.websocket_callback(msg))
            except Exception:
                # If WebSocket fails, don't break the logging - just skip
                pass


# Factory functions for backward compatibility
def setup_file_logger(module_name: str, log_file_path: Path, include_timestamp: bool = False) -> FileLogger:
    """
    Set up a file logger (backward compatibility).

    Args:
        module_name: Name of the module for the logger
        log_file_path: Path where log file will be written
        include_timestamp: Whether to include timestamp in log messages

    Returns:
        FileLogger instance
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

    return FileLogger(logger)


def setup_web_logger(name: str, websocket_callback: Callable[[str], Awaitable[None]] | None = None) -> WebLogger:
    """
    Set up a web logger (backward compatibility).

    Args:
        name: Logger name
        websocket_callback: Async function to send log messages via WebSocket

    Returns:
        WebLogger instance
    """
    return WebLogger(name, websocket_callback)


class InfoFilter(logging.Filter):
    """Filters log records to allow only INFO level and below."""

    def filter(self, record):
        # Allow levels from DEBUG up to INFO
        return record.levelno <= logging.INFO