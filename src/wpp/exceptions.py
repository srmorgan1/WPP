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

F = TypeVar("F", bound=Callable[..., Any])


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


# ============================================================================
# Custom Exception Hierarchy for Consistent Error Types
# ============================================================================


class WPPError(Exception):
    """Base exception for all WPP-specific errors."""

    def __init__(self, message: str, context: dict[str, Any] | None = None, original_error: Exception | None = None):
        self.context = context or {}
        self.original_error = original_error

        if original_error:
            message = f"{message} (caused by: {original_error})"

        super().__init__(message)


class DataValidationError(WPPError):
    """Raised when data validation fails."""

    pass


class FileProcessingError(WPPError):
    """Raised when file processing fails."""

    def __init__(self, message: str, file_path: str, context: dict[str, Any] | None = None, original_error: Exception | None = None):
        self.file_path = file_path
        context = context or {}
        context["file_path"] = file_path
        super().__init__(message, context, original_error)


class DatabaseIntegrityError(WPPError):
    """Raised when database integrity constraints are violated."""

    pass


class ReportGenerationError(WPPError):
    """Raised when report generation fails."""

    pass


class ConfigurationError(WPPError):
    """Raised when configuration is invalid or missing."""

    pass


# ============================================================================
# Standard Error Messages
# ============================================================================


class ErrorMessages:
    """Standardized error message templates."""

    # Database errors
    DB_CONNECTION_FAILED = "Failed to connect to database"
    DB_TRANSACTION_FAILED = "Database transaction failed during {operation}"
    DB_CONSTRAINT_VIOLATED = "Database constraint violation: {constraint}"
    DB_RECORD_NOT_FOUND = "Record not found: {record_type} with {identifier}"
    DB_DUPLICATE_RECORD = "Duplicate record found: {record_type} with {identifier}"

    # File processing errors
    FILE_NOT_FOUND = "Required file not found: {file_path}"
    FILE_READ_ERROR = "Failed to read file: {file_path}"
    FILE_WRITE_ERROR = "Failed to write file: {file_path}"
    FILE_FORMAT_INVALID = "Invalid file format: {file_path} (expected: {expected_format})"
    FILE_EMPTY = "File is empty or contains no valid data: {file_path}"

    # Data validation errors
    DATA_MISSING_FIELD = "Missing required field: {field_name}"
    DATA_INVALID_FORMAT = "Invalid format for {field_name}: expected {expected_format}, got {actual_value}"
    DATA_OUT_OF_RANGE = "Value out of range for {field_name}: {value} (valid range: {min_value}-{max_value})"
    DATA_INVALID_TYPE = "Invalid data type for {field_name}: expected {expected_type}, got {actual_type}"

    # Business logic errors
    TENANT_NOT_FOUND = "Tenant not found with reference: {tenant_ref}"
    PROPERTY_NOT_FOUND = "Property not found with reference: {property_ref}"
    BLOCK_NOT_FOUND = "Block not found with reference: {block_ref}"
    ACCOUNT_NOT_FOUND = "Account not found: {sort_code}-{account_number}"

    # Report generation errors
    REPORT_DATA_INSUFFICIENT = "Insufficient data to generate report for date range: {start_date} to {end_date}"
    REPORT_TEMPLATE_ERROR = "Report template error: {template_name}"

    # Configuration errors
    CONFIG_FILE_INVALID = "Configuration file is invalid: {config_file}"
    CONFIG_MISSING_SECTION = "Missing required configuration section: {section_name}"
    CONFIG_MISSING_KEY = "Missing required configuration key: {section_name}.{key_name}"


# ============================================================================
# Standard Error Logging Functions
# ============================================================================


def log_error_with_context(logger: logging.Logger, message: str, error: Exception | None = None, context: dict[str, Any] | None = None, level: int = logging.ERROR) -> None:
    """Standard error logging with context information.

    Args:
        logger: Logger instance to use
        message: Primary error message
        error: Exception instance (if available)
        context: Additional context information
        level: Logging level to use
    """
    # Log the primary message
    logger.log(level, message)

    # Log context information if provided
    if context:
        for key, value in context.items():
            logger.log(level, f"  {key}: {value}")

    # Log the full exception with stack trace if provided
    if error:
        logger.exception(error)


def log_database_error(logger: logging.Logger, operation: str, error: Exception, data: Any = None, sql: str | None = None) -> None:
    """Standard database error logging.

    Args:
        logger: Logger instance to use
        operation: Description of the database operation that failed
        error: The database exception
        data: Data that caused the failure (for context)
        sql: SQL statement that failed (if available)
    """
    context = {}
    if data is not None:
        context["failed_data"] = str(data)
    if sql:
        context["sql_statement"] = sql

    message = ErrorMessages.DB_TRANSACTION_FAILED.format(operation=operation)
    log_error_with_context(logger, message, error, context)


def log_file_error(logger: logging.Logger, operation: str, file_path: str, error: Exception, expected_format: str | None = None) -> None:
    """Standard file processing error logging.

    Args:
        logger: Logger instance to use
        operation: Description of the file operation that failed
        file_path: Path to the file that caused the error
        error: The file processing exception
        expected_format: Expected file format (if applicable)
    """
    context = {"file_path": file_path, "operation": operation}
    if expected_format:
        context["expected_format"] = expected_format

    message = f"File processing failed during {operation}"
    log_error_with_context(logger, message, error, context)


def log_validation_error(logger: logging.Logger, field_name: str, value: Any, expected: str, record_context: dict[str, Any] | None = None) -> None:
    """Standard data validation error logging.

    Args:
        logger: Logger instance to use
        field_name: Name of the field that failed validation
        value: The invalid value
        expected: Description of what was expected
        record_context: Additional context about the record being validated
    """
    context = {"field_name": field_name, "invalid_value": str(value), "expected": expected}
    if record_context:
        context.update(record_context)

    message = ErrorMessages.DATA_INVALID_FORMAT.format(field_name=field_name, expected_format=expected, actual_value=value)
    log_error_with_context(logger, message, context=context)


# ============================================================================
# Exception Factory Functions
# ============================================================================


def create_database_error(operation: str, original_error: Exception, data: Any = None, table: str | None = None) -> DatabaseIntegrityError:
    """Create a standardized database error with context."""
    context = {}
    if data is not None:
        context["data"] = str(data)
    if table:
        context["table"] = table

    message = ErrorMessages.DB_TRANSACTION_FAILED.format(operation=operation)
    return DatabaseIntegrityError(message, context, original_error)


def create_validation_error(field_name: str, value: Any, expected_format: str, record_id: str | None = None) -> DataValidationError:
    """Create a standardized validation error with context."""
    context = {"field_name": field_name, "invalid_value": str(value), "expected_format": expected_format}
    if record_id:
        context["record_id"] = record_id

    message = ErrorMessages.DATA_INVALID_FORMAT.format(field_name=field_name, expected_format=expected_format, actual_value=value)
    return DataValidationError(message, context)


def create_file_error(operation: str, file_path: str, original_error: Exception, expected_format: str | None = None) -> FileProcessingError:
    """Create a standardized file processing error with context."""
    context = {"operation": operation}
    if expected_format:
        context["expected_format"] = expected_format

    message = f"File processing failed during {operation}"
    return FileProcessingError(message, file_path, context, original_error)
