"""
Web-specific logger that streams log messages to WebSocket connections
instead of files when running via the React web interface.
"""

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable


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
                if asyncio.get_event_loop().is_running():
                    asyncio.create_task(self.websocket_callback(msg))
            except Exception:
                # If WebSocket fails, don't break the logging - just skip
                pass


class WebLogger:
    """Web-specific logger that streams to WebSocket and optionally to console."""

    def __init__(self, name: str, websocket_callback: Callable[[str], Awaitable[None]] | None = None):
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


def setup_web_logger(name: str, websocket_callback: Callable[[str], Awaitable[None]] | None = None) -> WebLogger:
    """
    Set up a web logger that streams to WebSocket instead of files.

    Args:
        name: Logger name
        websocket_callback: Async function to send log messages via WebSocket

    Returns:
        WebLogger instance
    """
    return WebLogger(name, websocket_callback)
