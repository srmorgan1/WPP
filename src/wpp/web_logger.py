"""
Backward compatibility module for the old web logger interface.
This module now uses the new WPPLogger interface internally.
"""

from wpp.logger_interface import setup_web_logger as _setup_web_logger

# Re-export the new interface for backward compatibility
WebLogger = _setup_web_logger

def setup_web_logger(name: str, websocket_callback=None):
    """
    Set up a web logger that streams to WebSocket instead of files.

    Args:
        name: Logger name
        websocket_callback: Async function to send log messages via WebSocket

    Returns:
        WebLogger instance
    """
    return _setup_web_logger(name, websocket_callback)
