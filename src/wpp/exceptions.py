"""Exception handling utilities for WPP project.

This module provides context managers and decorators to handle common exception
patterns throughout the codebase, reducing code duplication and improving maintainability.
"""

import logging
import sqlite3
import traceback
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, TypeVar, cast

F = TypeVar('F', bound=Callable[..., Any])


@contextmanager
def database_transaction(
    db_conn: sqlite3.Connection,
    logger: logging.Logger | None = None,
    error_context: str = "",
    rethrow: bool = True,
) -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for database transactions with automatic rollback on error.
    
    Args:
        db_conn: Database connection
        logger: Logger for error messages (optional)
        error_context: Additional context for error messages
        rethrow: Whether to re-raise exceptions after logging
        
    Yields:
        Database cursor with transaction begun
        
    Example:
        with database_transaction(db_conn, logger, "importing properties") as cursor:
            cursor.execute("INSERT INTO Properties ...")
    """
    cursor = db_conn.cursor()
    cursor.execute("begin")
    
    try:
        yield cursor
        cursor.execute("end")
        db_conn.commit()
    except sqlite3.Error as err:
        cursor.execute("rollback")
        if logger:
            logger.error(f"Database error{f' during {error_context}' if error_context else ''}: {err}")
            logger.exception(err)
        if rethrow:
            raise
    except Exception as ex:
        cursor.execute("rollback")
        if logger:
            logger.error(f"Unexpected error{f' during {error_context}' if error_context else ''}: {ex}")
            logger.exception(ex)
        if rethrow:
            raise


def log_exceptions(
    logger: logging.Logger | None = None,
    error_message: str = "",
    rethrow: bool = True,
) -> Callable[[F], F]:
    """Decorator for consistent exception logging.
    
    Args:
        logger: Logger to use (defaults to module logger if available)
        error_message: Custom error message prefix
        rethrow: Whether to re-raise exceptions after logging
        
    Example:
        @log_exceptions(logger, "processing reports")
        def process_reports():
            # Function implementation
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as ex:
                effective_logger = logger or logging.getLogger(func.__module__)
                message = f"{error_message}: {ex}" if error_message else str(ex)
                effective_logger.error(message)
                effective_logger.exception(ex)
                if rethrow:
                    raise
        return cast(F, wrapper)
    return decorator


@contextmanager
def safe_pandas_operation(default_value: Any = None) -> Generator[None, None, None]:
    """Context manager for pandas operations that may fail silently.
    
    Used for operations where we want to continue processing even if
    specific pandas operations fail (e.g., accessing optional columns).
    
    Args:
        default_value: Value to return if operation fails
        
    Example:
        with safe_pandas_operation():
            qube_total = df.loc[select, "Qube Total"].iloc[0]
    """
    try:
        yield
    except Exception:
        # Silently ignore pandas access errors for optional operations
        pass


class DatabaseOperationError(Exception):
    """Exception raised when database operations fail with context."""
    
    def __init__(self, operation: str, data: Any = None, original_error: Exception | None = None):
        self.operation = operation
        self.data = data
        self.original_error = original_error
        
        message = f"Database operation failed: {operation}"
        if data is not None:
            message += f" (data: {data})"
        if original_error:
            message += f" (cause: {original_error})"
            
        super().__init__(message)


def handle_database_error(
    cursor: sqlite3.Cursor,
    logger: logging.Logger,
    operation: str,
    data: Any = None,
    rethrow: bool = True,
) -> Callable[[Exception], None]:
    """Factory function for standardized database error handling.
    
    Args:
        cursor: Database cursor for rollback
        logger: Logger for error messages
        operation: Description of the operation that failed
        data: Data that caused the failure (for logging)
        rethrow: Whether to re-raise as DatabaseOperationError
        
    Returns:
        Error handler function
    """
    def error_handler(error: Exception) -> None:
        cursor.execute("rollback")
        
        logger.error(f"Database error during {operation}: {error}")
        if data is not None:
            logger.error(f"Data that caused the failure: {data}")
        logger.exception(error)
        
        if rethrow:
            raise DatabaseOperationError(operation, data, error)
    
    return error_handler