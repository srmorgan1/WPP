"""Unit tests for exceptions.py module."""

import logging
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wpp.db import get_db_connection
from wpp.exceptions import (
    ConfigurationError,
    DataValidationError,
    DatabaseIntegrityError,
    DatabaseOperationError,
    ErrorMessages,
    FileProcessingError,
    ReportGenerationError,
    WPPError,
    create_database_error,
    create_file_error,
    create_validation_error,
    database_transaction,
    handle_database_error,
    log_database_error,
    log_error_with_context,
    log_exceptions,
    log_file_error,
    log_validation_error,
    safe_pandas_operation,
)


class TestDatabaseTransaction:
    """Test the database_transaction context manager."""

    def test_successful_transaction(self):
        """Test successful transaction commits."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_db:
            db_path = temp_db.name

        conn = get_db_connection(db_path)
        conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")

        with database_transaction(conn) as cursor:
            cursor.execute("INSERT INTO test (id, value) VALUES (1, 'test')")

        # Verify the data was committed
        result = conn.execute("SELECT * FROM test").fetchone()
        assert result == (1, "test")
        conn.close()

        # Clean up
        Path(db_path).unlink()

    def test_transaction_rollback_on_sqlite_error(self):
        """Test transaction rollback on SQLite error."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_db:
            db_path = temp_db.name

        conn = get_db_connection(db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        logger = Mock(spec=logging.Logger)

        with pytest.raises(sqlite3.IntegrityError):
            with database_transaction(conn, logger, "test operation") as cursor:
                cursor.execute("INSERT INTO test (id) VALUES (1)")
                cursor.execute("INSERT INTO test (id) VALUES (1)")  # Duplicate key

        # Verify rollback occurred - no data should be in table
        result = conn.execute("SELECT COUNT(*) FROM test").fetchone()
        assert result[0] == 0

        # Verify logging
        logger.error.assert_called()
        logger.exception.assert_called()
        conn.close()

        # Clean up
        Path(db_path).unlink()

    def test_transaction_rollback_on_general_exception(self):
        """Test transaction rollback on general exception."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_db:
            db_path = temp_db.name

        conn = get_db_connection(db_path)
        conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")

        logger = Mock(spec=logging.Logger)

        with pytest.raises(ValueError):
            with database_transaction(conn, logger, "test operation") as cursor:
                cursor.execute("INSERT INTO test (id, value) VALUES (1, 'test')")
                raise ValueError("Test error")

        # Verify rollback occurred
        result = conn.execute("SELECT COUNT(*) FROM test").fetchone()
        assert result[0] == 0

        # Verify logging
        logger.error.assert_called()
        logger.exception.assert_called()
        conn.close()

        # Clean up
        Path(db_path).unlink()

    def test_transaction_no_rethrow(self):
        """Test transaction with rethrow=False."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_db:
            db_path = temp_db.name

        conn = get_db_connection(db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        logger = Mock(spec=logging.Logger)

        # Should not raise exception
        with database_transaction(conn, logger, "test operation", rethrow=False) as cursor:
            cursor.execute("INSERT INTO test (id) VALUES (1)")
            cursor.execute("INSERT INTO test (id) VALUES (1)")  # Duplicate key

        # Verify logging still occurred
        logger.error.assert_called()
        logger.exception.assert_called()
        conn.close()

        # Clean up
        Path(db_path).unlink()

    def test_transaction_no_logger(self):
        """Test transaction without logger."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_db:
            db_path = temp_db.name

        conn = get_db_connection(db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        with pytest.raises(sqlite3.IntegrityError):
            with database_transaction(conn) as cursor:
                cursor.execute("INSERT INTO test (id) VALUES (1)")
                cursor.execute("INSERT INTO test (id) VALUES (1)")  # Duplicate key

        conn.close()
        # Clean up
        Path(db_path).unlink()


class TestLogExceptions:
    """Test the log_exceptions decorator."""

    def test_decorator_no_exception(self):
        """Test decorator when function executes successfully."""
        logger = Mock(spec=logging.Logger)

        @log_exceptions(logger, "test operation")
        def test_function(x, y):
            return x + y

        result = test_function(2, 3)
        assert result == 5
        logger.error.assert_not_called()

    def test_decorator_with_exception(self):
        """Test decorator when function raises exception."""
        logger = Mock(spec=logging.Logger)

        @log_exceptions(logger, "test operation")
        def test_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            test_function()

        logger.error.assert_called_once()
        logger.exception.assert_called_once()

    def test_decorator_no_rethrow(self):
        """Test decorator with rethrow=False."""
        logger = Mock(spec=logging.Logger)

        @log_exceptions(logger, "test operation", rethrow=False)
        def test_function():
            raise ValueError("Test error")

        # Should not raise exception
        result = test_function()
        assert result is None

        logger.error.assert_called_once()
        logger.exception.assert_called_once()

    def test_decorator_no_logger(self):
        """Test decorator without explicit logger."""
        @log_exceptions()
        def test_function():
            raise ValueError("Test error")

        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            with pytest.raises(ValueError):
                test_function()

            mock_get_logger.assert_called_once()
            mock_logger.error.assert_called_once()

    def test_decorator_no_error_message(self):
        """Test decorator without custom error message."""
        logger = Mock(spec=logging.Logger)

        @log_exceptions(logger)
        def test_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            test_function()

        # Should log just the exception message
        logger.error.assert_called_with("Test error")


class TestSafePandasOperation:
    """Test the safe_pandas_operation context manager."""

    def test_safe_operation_success(self):
        """Test safe operation when no exception occurs."""
        result = None
        with safe_pandas_operation():
            result = 42

        assert result == 42

    def test_safe_operation_with_exception(self):
        """Test safe operation silently handles exceptions."""
        result = "initial"
        with safe_pandas_operation():
            result = "modified"
            raise KeyError("Missing column")

        # Should silently continue
        assert result == "modified"

    def test_safe_operation_default_value(self):
        """Test safe operation with default value parameter."""
        # The default_value parameter exists but isn't used in current implementation
        with safe_pandas_operation(default_value="fallback"):
            raise ValueError("Test error")
        # Should not raise


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_wpp_error_basic(self):
        """Test basic WPPError functionality."""
        error = WPPError("Test message")
        assert str(error) == "Test message"
        assert error.context == {}
        assert error.original_error is None

    def test_wpp_error_with_context(self):
        """Test WPPError with context."""
        context = {"key": "value", "number": 42}
        error = WPPError("Test message", context)
        assert error.context == context

    def test_wpp_error_with_original_error(self):
        """Test WPPError with original error."""
        original = ValueError("Original error")
        error = WPPError("Test message", original_error=original)
        assert error.original_error is original
        assert "caused by: Original error" in str(error)

    def test_data_validation_error(self):
        """Test DataValidationError inheritance."""
        error = DataValidationError("Validation failed")
        assert isinstance(error, WPPError)
        assert str(error) == "Validation failed"

    def test_file_processing_error(self):
        """Test FileProcessingError with file path."""
        error = FileProcessingError("File error", "/path/to/file.txt")
        assert isinstance(error, WPPError)
        assert error.file_path == "/path/to/file.txt"
        assert "file_path" in error.context

    def test_file_processing_error_with_context(self):
        """Test FileProcessingError with additional context."""
        original = IOError("File not found")
        context = {"size": 1024}
        error = FileProcessingError("File error", "/path/to/file.txt", context, original)
        assert error.context["file_path"] == "/path/to/file.txt"
        assert error.context["size"] == 1024
        assert error.original_error is original

    def test_database_integrity_error(self):
        """Test DatabaseIntegrityError inheritance."""
        error = DatabaseIntegrityError("Constraint violation")
        assert isinstance(error, WPPError)

    def test_report_generation_error(self):
        """Test ReportGenerationError inheritance."""
        error = ReportGenerationError("Report failed")
        assert isinstance(error, WPPError)

    def test_configuration_error(self):
        """Test ConfigurationError inheritance."""
        error = ConfigurationError("Config invalid")
        assert isinstance(error, WPPError)


class TestDatabaseOperationError:
    """Test DatabaseOperationError class."""

    def test_basic_error(self):
        """Test basic DatabaseOperationError."""
        error = DatabaseOperationError("insert operation")
        assert "Database operation failed: insert operation" in str(error)
        assert error.operation == "insert operation"
        assert error.data is None
        assert error.original_error is None

    def test_error_with_data(self):
        """Test DatabaseOperationError with data."""
        data = {"id": 1, "name": "test"}
        error = DatabaseOperationError("insert operation", data)
        assert error.data == data
        assert "data:" in str(error)

    def test_error_with_original(self):
        """Test DatabaseOperationError with original error."""
        original = sqlite3.IntegrityError("UNIQUE constraint failed")
        error = DatabaseOperationError("insert operation", original_error=original)
        assert error.original_error is original
        assert "cause:" in str(error)


class TestHandleDatabaseError:
    """Test handle_database_error function."""

    def test_error_handler_with_rollback(self):
        """Test error handler performs rollback and logging."""
        cursor = Mock(spec=sqlite3.Cursor)
        logger = Mock(spec=logging.Logger)
        
        handler = handle_database_error(cursor, logger, "test operation", {"id": 1})
        
        test_error = sqlite3.Error("Test database error")
        with pytest.raises(DatabaseOperationError):
            handler(test_error)

        cursor.execute.assert_called_with("rollback")
        logger.error.assert_called()
        logger.exception.assert_called_with(test_error)

    def test_error_handler_no_rethrow(self):
        """Test error handler with rethrow=False."""
        cursor = Mock(spec=sqlite3.Cursor)
        logger = Mock(spec=logging.Logger)
        
        handler = handle_database_error(cursor, logger, "test operation", rethrow=False)
        
        test_error = sqlite3.Error("Test database error")
        # Should not raise
        handler(test_error)

        cursor.execute.assert_called_with("rollback")
        logger.error.assert_called()


class TestErrorMessages:
    """Test ErrorMessages class."""

    def test_error_message_templates(self):
        """Test error message template formatting."""
        assert ErrorMessages.DB_CONNECTION_FAILED == "Failed to connect to database"
        
        formatted = ErrorMessages.DB_TRANSACTION_FAILED.format(operation="insert")
        assert "insert" in formatted
        
        formatted = ErrorMessages.FILE_NOT_FOUND.format(file_path="/test/path")
        assert "/test/path" in formatted
        
        formatted = ErrorMessages.DATA_MISSING_FIELD.format(field_name="tenant_ref")
        assert "tenant_ref" in formatted


class TestLogErrorWithContext:
    """Test log_error_with_context function."""

    def test_basic_logging(self):
        """Test basic error logging."""
        logger = Mock(spec=logging.Logger)
        log_error_with_context(logger, "Test message")
        
        logger.log.assert_called_with(logging.ERROR, "Test message")

    def test_logging_with_context(self):
        """Test logging with context information."""
        logger = Mock(spec=logging.Logger)
        context = {"key1": "value1", "key2": 42}
        
        log_error_with_context(logger, "Test message", context=context)
        
        # Should log main message and context items
        assert logger.log.call_count >= 3  # main message + 2 context items

    def test_logging_with_exception(self):
        """Test logging with exception."""
        logger = Mock(spec=logging.Logger)
        error = ValueError("Test error")
        
        log_error_with_context(logger, "Test message", error=error)
        
        logger.log.assert_called_with(logging.ERROR, "Test message")
        logger.exception.assert_called_with(error)

    def test_logging_with_custom_level(self):
        """Test logging with custom level."""
        logger = Mock(spec=logging.Logger)
        
        log_error_with_context(logger, "Test message", level=logging.WARNING)
        
        logger.log.assert_called_with(logging.WARNING, "Test message")


class TestLogDatabaseError:
    """Test log_database_error function."""

    def test_database_error_logging(self):
        """Test database error logging."""
        logger = Mock(spec=logging.Logger)
        error = sqlite3.Error("Database error")
        
        log_database_error(logger, "insert operation", error)
        
        logger.log.assert_called()
        logger.exception.assert_called_with(error)

    def test_database_error_with_data(self):
        """Test database error logging with data."""
        logger = Mock(spec=logging.Logger)
        error = sqlite3.Error("Database error")
        data = {"id": 1, "name": "test"}
        
        log_database_error(logger, "insert operation", error, data)
        
        # Should log with context including data
        logger.log.assert_called()
        logger.exception.assert_called_with(error)

    def test_database_error_with_sql(self):
        """Test database error logging with SQL statement."""
        logger = Mock(spec=logging.Logger)
        error = sqlite3.Error("Database error")
        sql = "INSERT INTO test (id) VALUES (?)"
        
        log_database_error(logger, "insert operation", error, sql=sql)
        
        logger.log.assert_called()
        logger.exception.assert_called_with(error)


class TestLogFileError:
    """Test log_file_error function."""

    def test_file_error_logging(self):
        """Test file error logging."""
        logger = Mock(spec=logging.Logger)
        error = FileNotFoundError("File not found")
        
        log_file_error(logger, "read operation", "/path/to/file.txt", error)
        
        logger.log.assert_called()
        logger.exception.assert_called_with(error)

    def test_file_error_with_format(self):
        """Test file error logging with expected format."""
        logger = Mock(spec=logging.Logger)
        error = ValueError("Invalid format")
        
        log_file_error(logger, "parse operation", "/path/to/file.xlsx", error, "Excel")
        
        logger.log.assert_called()
        logger.exception.assert_called_with(error)


class TestLogValidationError:
    """Test log_validation_error function."""

    def test_validation_error_logging(self):
        """Test validation error logging."""
        logger = Mock(spec=logging.Logger)
        
        log_validation_error(logger, "tenant_ref", "invalid-ref", "XXX-XX-XXX format")
        
        logger.log.assert_called()
        # Should use error message template

    def test_validation_error_with_context(self):
        """Test validation error logging with record context."""
        logger = Mock(spec=logging.Logger)
        context = {"row": 5, "file": "tenants.xlsx"}
        
        log_validation_error(logger, "tenant_ref", "invalid-ref", "XXX-XX-XXX format", context)
        
        logger.log.assert_called()


class TestExceptionFactories:
    """Test exception factory functions."""

    def test_create_database_error(self):
        """Test create_database_error factory."""
        original = sqlite3.Error("SQL error")
        data = {"id": 1}
        
        error = create_database_error("insert", original, data, "test_table")
        
        assert isinstance(error, DatabaseIntegrityError)
        assert error.original_error is original
        assert "data" in error.context
        assert "table" in error.context

    def test_create_validation_error(self):
        """Test create_validation_error factory."""
        error = create_validation_error("tenant_ref", "bad-ref", "XXX-XX-XXX", "record123")
        
        assert isinstance(error, DataValidationError)
        assert "field_name" in error.context
        assert "invalid_value" in error.context
        assert "expected_format" in error.context
        assert "record_id" in error.context

    def test_create_file_error(self):
        """Test create_file_error factory."""
        original = IOError("File not found")
        
        error = create_file_error("read", "/path/to/file.txt", original, "Excel")
        
        assert isinstance(error, FileProcessingError)
        assert error.file_path == "/path/to/file.txt"
        assert error.original_error is original
        assert "operation" in error.context
        assert "expected_format" in error.context