"""Tests for error handling and edge cases in UpdateDatabase.py."""

import sqlite3
import xml.etree.ElementTree as et
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from wpp.UpdateDatabase import (
    _extract_balance_data,
    _handle_database_error,
    _handle_transaction_processing_error,
    _log_balance_import_error,
    _report_qube_import_errors,
    _validate_account_designation_consistency,
    _validate_account_uniqueness,
    get_element_text,
)


def test_handle_database_error():
    """Test database error handling with logging."""
    test_error = sqlite3.IntegrityError("UNIQUE constraint failed")
    context_data = {"property_ref": "123", "block_ref": "123-01"}
    operation_desc = "Unable to add property to the database"

    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _handle_database_error(test_error, context_data, operation_desc)

        # Verify all expected logging calls
        mock_logger.error.assert_any_call("UNIQUE constraint failed")
        mock_logger.error.assert_any_call("The data which caused the failure is: {'property_ref': '123', 'block_ref': '123-01'}")
        mock_logger.error.assert_any_call("Unable to add property to the database")
        mock_logger.exception.assert_called_once_with(test_error)


def test_report_qube_import_errors():
    """Test Qube import error reporting."""
    qube_errors = [{"Block Reference": "123-01", "Error": "Invalid fund amount"}, {"Block Reference": "456-02", "Error": "Missing category"}]

    # Create mock Excel writer
    mock_excel_writer = Mock()

    with patch("wpp.UpdateDatabase.logger") as mock_logger, patch("pandas.DataFrame.to_excel") as mock_to_excel:
        _report_qube_import_errors(qube_errors, "/path/to/qube.xlsx", mock_excel_writer)

        # Verify logging
        mock_logger.error.assert_any_call("Found 2 Qube import issues in /path/to/qube.xlsx")
        mock_logger.error.assert_any_call("Block 123-01: Invalid fund amount")
        mock_logger.error.assert_any_call("Block 456-02: Missing category")

        # Verify Excel writing
        mock_to_excel.assert_called_once_with(mock_excel_writer, sheet_name="Qube Import Problems", index=False, float_format="%.2f")


def test_report_qube_import_errors_empty_list():
    """Test Qube import error reporting with no errors."""
    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _report_qube_import_errors([], "/path/to/qube.xlsx", Mock())

        # Should not log anything for empty error list
        mock_logger.error.assert_not_called()


def test_validate_account_designation_consistency_violations():
    """Test account designation consistency validation with violations."""
    # Create test DataFrame with designation violations
    test_data = {
        "Reference": ["123-00", "456-01"],  # Estate vs Block references
        "Property Or Block": ["Block", "Property"],  # Use correct column name from actual code
        "Sort Code": ["12-34-56", "98-76-54"],
        "Account Number": ["12345678", "87654321"],
        "Account Name": ["Estate Account", "Block Account"],
        "Client Reference": ["EST123", "BLK456"],
    }
    df = pd.DataFrame(test_data)

    mock_excel_writer = Mock()

    with patch("wpp.UpdateDatabase.logger") as mock_logger, patch("pandas.DataFrame.to_excel") as mock_to_excel, patch("wpp.UpdateDatabase.getPropertyBlockAndTenantRefs") as mock_get_refs:
        # Mock the reference parsing to trigger validation errors
        mock_get_refs.side_effect = [
            (None, "123-00", None),  # Estate reference
            ("456", "456-01", None),  # Block reference
        ]

        violations = _validate_account_designation_consistency(df, "/path/to/accounts.xlsx", mock_excel_writer)

        # Should find violations
        assert len(violations) == 2

        # Verify logging
        mock_logger.error.assert_called()

        # Verify Excel writing
        mock_to_excel.assert_called_once()


def test_validate_account_uniqueness_violations():
    """Test CL account uniqueness validation with violations."""
    # Create test DataFrame with duplicate CL accounts per block
    test_data = {
        "Reference": ["123-01", "123-01", "456-02"],
        "Account Type": ["CL", "CL", "CL"],  # Two CL accounts for same block
        "Sort Code": ["12-34-56", "12-34-56", "98-76-54"],
        "Account Number": ["11111111", "22222222", "33333333"],
        "Account Name": ["Test1", "Test2", "Test3"],
        "Client Reference": ["REF1", "REF2", "REF3"],
    }
    df = pd.DataFrame(test_data)

    mock_excel_writer = Mock()

    with patch("wpp.UpdateDatabase.logger") as mock_logger, patch("pandas.DataFrame.to_excel"):
        with pytest.raises(ValueError, match="multiple CL"):
            _validate_account_uniqueness(df, "/path/to/accounts.xlsx", mock_excel_writer)

        # Verify logging
        mock_logger.error.assert_called()


def test_validate_account_uniqueness_no_violations():
    """Test CL account uniqueness validation without violations."""
    # Create test DataFrame with unique CL accounts per block
    test_data = {"Reference": ["123-01", "456-02"], "Account Type": ["CL", "CL"], "Sort Code": ["12-34-56", "98-76-54"], "Account Number": ["11111111", "22222222"]}
    df = pd.DataFrame(test_data)

    mock_excel_writer = Mock()

    # Should not raise exception
    _validate_account_uniqueness(df, "/path/to/accounts.xlsx", mock_excel_writer)


def test_get_element_text_missing_element():
    """Test get_element_text with missing XML element."""
    root = et.Element("root")

    with pytest.raises(ValueError, match="Missing required XML element: nonexistent"):
        get_element_text(root, "nonexistent")


def test_get_element_text_empty_element():
    """Test get_element_text with empty XML element."""
    root = et.Element("root")
    child = et.SubElement(root, "empty")
    child.text = ""

    with pytest.raises(ValueError, match="Empty required XML element: empty"):
        get_element_text(root, "empty")


def test_get_element_text_whitespace_only():
    """Test get_element_text with whitespace-only XML element."""
    root = et.Element("root")
    child = et.SubElement(root, "whitespace")
    child.text = "   "

    with pytest.raises(ValueError, match="Empty required XML element: whitespace"):
        get_element_text(root, "whitespace")


def test_get_element_text_none_text():
    """Test get_element_text with None text content."""
    root = et.Element("root")
    child = et.SubElement(root, "none_text")
    child.text = None

    with pytest.raises(ValueError, match="Empty required XML element: none_text"):
        get_element_text(root, "none_text")


def test_extract_balance_data_missing_required_field():
    """Test balance data extraction with missing required field."""
    balance = et.Element("BalanceRecord")
    # Missing required SortCode element
    et.SubElement(balance, "AccountNumber").text = "12345678"
    et.SubElement(balance, "LongName").text = "Test Account"
    et.SubElement(balance, "CurrentBalance").text = "1000.50"
    et.SubElement(balance, "AvailableBalance").text = "950.25"

    with pytest.raises(ValueError, match="Missing required XML element: SortCode"):
        _extract_balance_data(balance)


def test_extract_balance_data_empty_required_field():
    """Test balance data extraction with empty required field."""
    balance = et.Element("BalanceRecord")
    et.SubElement(balance, "SortCode").text = "12-34-56"
    account_num = et.SubElement(balance, "AccountNumber")
    account_num.text = ""  # Empty required field
    et.SubElement(balance, "LongName").text = "Test Account"
    et.SubElement(balance, "CurrentBalance").text = "1000.50"
    et.SubElement(balance, "AvailableBalance").text = "950.25"

    with pytest.raises(ValueError, match="Empty required XML element: AccountNumber"):
        _extract_balance_data(balance)


def test_handle_transaction_processing_error():
    """Test transaction processing error handling."""
    mock_cursor = Mock()
    test_error = sqlite3.IntegrityError("Transaction constraint violation")
    transaction_data = {"sort_code": "12-34-56", "account_number": "12345678", "transaction_type": "Credit", "amount": "100.50", "description": "Test payment", "pay_date": "2023-01-15"}
    tenant_id = 123

    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _handle_transaction_processing_error(mock_cursor, test_error, transaction_data, tenant_id)

        # Verify rollback
        mock_cursor.execute.assert_called_with("rollback")

        # Verify logging
        mock_logger.error.assert_called()
        mock_logger.exception.assert_called_with(test_error)


def test_log_balance_import_error_database_error():
    """Test balance import error logging for database errors."""
    balance_data = {
        "sort_code": "12-34-56",
        "account_number": "12345678",
        "account_type": "Current",
        "client_ref": "TEST",
        "account_name": "Test Account",
        "current_balance": "1000.50",
        "available_balance": "900.25",
    }
    at_date = "2023-01-15"
    test_error = sqlite3.IntegrityError("Balance constraint violation")

    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _log_balance_import_error(test_error, balance_data, at_date)

        # Verify error logging
        mock_logger.error.assert_any_call("Balance constraint violation")
        mock_logger.exception.assert_called_with(test_error)

        # Verify context data logging
        expected_context = "('12-34-56', '12345678', 'Current', 'TEST', 'Test Account', '2023-01-15', '1000.50', '900.25')"
        mock_logger.error.assert_any_call(f"The data which caused the failure is: {expected_context}")


def test_log_balance_import_error_xml_parsing_error():
    """Test balance import error logging for XML parsing errors."""
    balance_data = {}
    at_date = "2023-01-15"
    test_error = et.ParseError("XML syntax error at line 5")

    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _log_balance_import_error(test_error, balance_data, at_date)

        # Verify error logging
        mock_logger.error.assert_any_call("XML syntax error at line 5")
        mock_logger.exception.assert_called_with(test_error)


def test_validate_account_designation_consistency_empty_dataframe():
    """Test account designation validation with empty DataFrame."""
    empty_df = pd.DataFrame()
    mock_excel_writer = Mock()

    violations = _validate_account_designation_consistency(empty_df, "/path/to/file.xlsx", mock_excel_writer)

    # Should return empty list for empty DataFrame
    assert violations == []


def test_validate_account_uniqueness_no_cl_accounts():
    """Test CL account uniqueness validation with no CL accounts."""
    test_data = {
        "Reference": ["123-01", "456-02"],
        "Account Type": ["GR", "RE"],  # No CL accounts
        "Sort Code": ["12-34-56", "98-76-54"],
        "Account Number": ["11111111", "22222222"],
    }
    df = pd.DataFrame(test_data)
    mock_excel_writer = Mock()

    # Should not raise exception and should not log errors
    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _validate_account_uniqueness(df, "/path/to/accounts.xlsx", mock_excel_writer)
        mock_logger.error.assert_not_called()


def test_validate_account_uniqueness_blank_references():
    """Test CL account uniqueness validation ignoring blank references."""
    test_data = {
        "Reference": ["", "   ", None, "123-01"],  # Blank references should be ignored
        "Account Type": ["CL", "CL", "CL", "CL"],
        "Sort Code": ["12-34-56", "12-34-56", "12-34-56", "98-76-54"],
        "Account Number": ["11111111", "22222222", "33333333", "44444444"],
    }
    df = pd.DataFrame(test_data)
    mock_excel_writer = Mock()

    # Should not raise exception since blank references are ignored
    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _validate_account_uniqueness(df, "/path/to/accounts.xlsx", mock_excel_writer)
        mock_logger.error.assert_not_called()


def test_database_connection_error_simulation():
    """Test database connection error simulation."""
    # This tests the pattern used throughout the code for database error handling
    test_error = sqlite3.OperationalError("database is locked")
    context_data = {"operation": "test"}

    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _handle_database_error(test_error, context_data, "Database operation failed")

        mock_logger.error.assert_any_call("database is locked")
        mock_logger.error.assert_any_call("Database operation failed")
        mock_logger.exception.assert_called_with(test_error)
