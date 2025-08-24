"""Tests for refactored UpdateDatabase.py functions to target coverage gaps."""

import xml.etree.ElementTree as et
from unittest.mock import patch

from wpp.UpdateDatabase import _log_balance_import_error, _process_balance_reporting_day, _process_single_transaction, _process_transaction_results


def test_process_single_transaction_added(db_conn):
    """Test processing single transaction that gets added successfully."""
    cursor = db_conn.cursor()

    # Set up test data - create property, block, tenant
    cursor.execute("INSERT INTO Properties (property_ref) VALUES ('123');")
    property_id = cursor.lastrowid
    cursor.execute("INSERT INTO Blocks (block_ref, property_id, type) VALUES ('123-01', ?, 'Residential');", (property_id,))
    block_id = cursor.lastrowid
    cursor.execute("INSERT INTO Tenants (tenant_ref, tenant_name, block_id) VALUES ('123-01-001', 'JOHN SMITH', ?);", (block_id,))

    # Set up account
    cursor.execute(
        "INSERT INTO Accounts (sort_code, account_number, account_type, property_or_block, client_ref, account_name) VALUES ('12-34-56', '06000792', 'Current', 'Block', 'TEST', 'Test Account');"
    )

    transaction_data = {"description": "123-01-001 PAYMENT", "sort_code": "12-34-56", "account_number": "06000792", "transaction_type": "Credit", "amount": "100.50", "pay_date": "2023-01-15"}

    result_type, was_processed, needs_error = _process_single_transaction(cursor, transaction_data)

    assert result_type == "added"
    assert was_processed is True
    assert needs_error is False


def test_process_single_transaction_invalid_refs(db_conn):
    """Test processing single transaction with invalid references."""
    cursor = db_conn.cursor()

    transaction_data = {"description": "INVALID PAYMENT DESCRIPTION", "sort_code": "12-34-56", "account_number": "06000792", "transaction_type": "Credit", "amount": "100.50", "pay_date": "2023-01-15"}

    result_type, was_processed, needs_error = _process_single_transaction(cursor, transaction_data)

    assert result_type == "invalid_refs"
    assert was_processed is False
    assert needs_error is True


def test_process_single_transaction_tenant_not_found(db_conn):
    """Test processing single transaction where tenant is not found."""
    cursor = db_conn.cursor()

    transaction_data = {
        "description": "999-99-999 PAYMENT",  # Non-existent tenant
        "sort_code": "12-34-56",
        "account_number": "06000792",
        "transaction_type": "Credit",
        "amount": "100.50",
        "pay_date": "2023-01-15",
    }

    # Mock getPropertyBlockAndTenantRefs to return valid refs but tenant doesn't exist in DB
    with patch("wpp.UpdateDatabase.getPropertyBlockAndTenantRefs") as mock_get_refs:
        mock_get_refs.return_value = ("999", "999-99", "999-99-999")

        result_type, was_processed, needs_error = _process_single_transaction(cursor, transaction_data)

        assert result_type == "tenant_not_found"
        assert was_processed is False
        assert needs_error is True


def test_process_transaction_results_added():
    """Test processing transaction results for successful addition."""
    unrecognised_transactions = []
    duplicate_transactions = []
    missing_tenant_transactions = []
    transaction_data = {"pay_date": "2023-01-15"}

    added_count, error_count = _process_transaction_results("added", transaction_data, None, unrecognised_transactions, duplicate_transactions, missing_tenant_transactions)

    assert added_count == 1
    assert error_count == 0
    assert len(unrecognised_transactions) == 0
    assert len(duplicate_transactions) == 0
    assert len(missing_tenant_transactions) == 0


def test_process_transaction_results_duplicate():
    """Test processing transaction results for duplicate transaction."""
    unrecognised_transactions = []
    duplicate_transactions = []
    missing_tenant_transactions = []
    transaction_data = {"pay_date": "2023-01-15", "transaction_type": "Credit", "amount": "100.50", "description": "Test payment"}
    tenant_ref = "123-01-001"

    added_count, error_count = _process_transaction_results("duplicate", transaction_data, tenant_ref, unrecognised_transactions, duplicate_transactions, missing_tenant_transactions)

    assert added_count == 0
    assert error_count == 0
    assert len(unrecognised_transactions) == 0
    assert len(duplicate_transactions) == 1
    assert len(missing_tenant_transactions) == 0


def test_process_transaction_results_tenant_not_found():
    """Test processing transaction results when tenant not found."""
    unrecognised_transactions = []
    duplicate_transactions = []
    missing_tenant_transactions = []
    transaction_data = {"pay_date": "2023-01-15", "sort_code": "12-34-56", "account_number": "12345678", "transaction_type": "Credit", "amount": "100.50", "description": "Test payment"}
    tenant_ref = "999-99-999"

    added_count, error_count = _process_transaction_results("tenant_not_found", transaction_data, tenant_ref, unrecognised_transactions, duplicate_transactions, missing_tenant_transactions)

    assert added_count == 0
    assert error_count == 1
    assert len(unrecognised_transactions) == 0  # Should NOT go to unrecognised transactions
    assert len(duplicate_transactions) == 0
    assert len(missing_tenant_transactions) == 1  # Should go to missing tenant transactions
    assert missing_tenant_transactions[0][6] == "999-99-999"  # Tenant reference field
    assert "Tenant '999-99-999' not found in tenants file" in missing_tenant_transactions[0][7]  # Issue field


def test_process_transaction_results_invalid_refs():
    """Test processing transaction results for invalid references."""
    unrecognised_transactions = []
    duplicate_transactions = []
    missing_tenant_transactions = []
    transaction_data = {"pay_date": "2023-01-15", "sort_code": "12-34-56", "account_number": "12345678", "transaction_type": "Credit", "amount": "100.50", "description": "INVALID PAYMENT"}

    added_count, error_count = _process_transaction_results("invalid_refs", transaction_data, None, unrecognised_transactions, duplicate_transactions, missing_tenant_transactions)

    assert added_count == 0
    assert error_count == 1
    assert len(unrecognised_transactions) == 1  # Should go to unrecognised transactions
    assert len(duplicate_transactions) == 0
    assert len(missing_tenant_transactions) == 0  # Should NOT go to missing tenant transactions
    assert "Cannot determine tenant from description" in unrecognised_transactions[0][6]


def test_process_balance_reporting_day(db_conn):
    """Test processing balance records for a reporting day."""
    cursor = db_conn.cursor()

    # Set up test account
    cursor.execute(
        "INSERT INTO Accounts (sort_code, account_number, account_type, property_or_block, client_ref, account_name) VALUES ('12-34-56', '12345678', 'Current', 'Block', 'TEST', 'Test Account');"
    )

    # Create reporting day XML element
    reporting_day = et.Element("ReportingDay")
    et.SubElement(reporting_day, "Date").text = "2023-01-15"

    # Add balance record
    balance_record = et.SubElement(reporting_day, "BalanceRecord")
    et.SubElement(balance_record, "SortCode").text = "12-34-56"
    et.SubElement(balance_record, "AccountNumber").text = "12345678"
    et.SubElement(balance_record, "LongName").text = "Test Account"
    et.SubElement(balance_record, "CurrentBalance").text = "1000.50"
    et.SubElement(balance_record, "AvailableBalance").text = "900.25"
    # No ClientRef for this test

    balances_added = _process_balance_reporting_day(cursor, reporting_day)

    assert balances_added == 1

    # Verify balance was added to database
    cursor.execute("SELECT COUNT(*) FROM AccountBalances WHERE at_date = '2023-01-15'")
    count = cursor.fetchone()[0]
    assert count == 1


def test_process_balance_reporting_day_no_accounts(db_conn):
    """Test processing balance records when no matching accounts exist."""
    cursor = db_conn.cursor()

    # Create reporting day XML element with non-existent account
    reporting_day = et.Element("ReportingDay")
    et.SubElement(reporting_day, "Date").text = "2023-01-15"

    balance_record = et.SubElement(reporting_day, "BalanceRecord")
    et.SubElement(balance_record, "SortCode").text = "99-99-99"
    et.SubElement(balance_record, "AccountNumber").text = "99999999"
    et.SubElement(balance_record, "LongName").text = "Nonexistent Account"
    et.SubElement(balance_record, "CurrentBalance").text = "1000.50"
    et.SubElement(balance_record, "AvailableBalance").text = "900.25"

    balances_added = _process_balance_reporting_day(cursor, reporting_day)

    assert balances_added == 0  # No balances should be added


def test_log_balance_import_error():
    """Test logging balance import errors."""
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
    test_error = ValueError("Test error message")

    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _log_balance_import_error(test_error, balance_data, at_date)

        # Verify logging calls
        assert mock_logger.error.call_count >= 3
        assert mock_logger.exception.call_count == 1

        # Check that error message was logged
        mock_logger.error.assert_any_call("Test error message")

        # Check that context data was logged
        expected_context = "('12-34-56', '12345678', 'Current', 'TEST', 'Test Account', '2023-01-15', '1000.50', '900.25')"
        mock_logger.error.assert_any_call(f"The data which caused the failure is: {expected_context}")


def test_log_balance_import_error_missing_data():
    """Test logging balance import errors with missing data."""
    balance_data = {}  # Empty balance data
    at_date = "2023-01-15"
    test_error = ValueError("Test error")

    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _log_balance_import_error(test_error, balance_data, at_date)

        # Should still log without errors even with missing data
        assert mock_logger.error.call_count >= 3
        assert mock_logger.exception.call_count == 1


def test_process_transaction_results_unknown_type():
    """Test processing transaction results with unknown result type."""
    unrecognised_transactions = []
    duplicate_transactions = []
    missing_tenant_transactions = []
    transaction_data = {"pay_date": "2023-01-15"}

    added_count, error_count = _process_transaction_results("unknown_type", transaction_data, None, unrecognised_transactions, duplicate_transactions, missing_tenant_transactions)

    # Should return 0, 0 for unknown types
    assert added_count == 0
    assert error_count == 0
    assert len(unrecognised_transactions) == 0
    assert len(duplicate_transactions) == 0
    assert len(missing_tenant_transactions) == 0


def test_process_balance_reporting_day_multiple_records(db_conn):
    """Test processing multiple balance records in a single reporting day."""
    cursor = db_conn.cursor()

    # Set up test accounts
    cursor.execute(
        "INSERT INTO Accounts (sort_code, account_number, account_type, property_or_block, client_ref, account_name) VALUES ('12-34-56', '11111111', 'Current', 'Block', 'TEST1', 'Test Account 1');"
    )
    cursor.execute(
        "INSERT INTO Accounts (sort_code, account_number, account_type, property_or_block, client_ref, account_name) VALUES ('12-34-56', '22222222', 'Current', 'Block', 'TEST2', 'Test Account 2');"
    )

    # Create reporting day with multiple balance records
    reporting_day = et.Element("ReportingDay")
    et.SubElement(reporting_day, "Date").text = "2023-01-15"

    # First balance record
    balance1 = et.SubElement(reporting_day, "BalanceRecord")
    et.SubElement(balance1, "SortCode").text = "12-34-56"
    et.SubElement(balance1, "AccountNumber").text = "11111111"
    et.SubElement(balance1, "LongName").text = "Test Account 1"
    et.SubElement(balance1, "CurrentBalance").text = "1000.50"
    et.SubElement(balance1, "AvailableBalance").text = "900.25"

    # Second balance record
    balance2 = et.SubElement(reporting_day, "BalanceRecord")
    et.SubElement(balance2, "SortCode").text = "12-34-56"
    et.SubElement(balance2, "AccountNumber").text = "22222222"
    et.SubElement(balance2, "LongName").text = "Test Account 2"
    et.SubElement(balance2, "CurrentBalance").text = "2000.75"
    et.SubElement(balance2, "AvailableBalance").text = "1800.50"

    balances_added = _process_balance_reporting_day(cursor, reporting_day)

    assert balances_added == 2

    # Verify both balances were added
    cursor.execute("SELECT COUNT(*) FROM AccountBalances WHERE at_date = '2023-01-15'")
    count = cursor.fetchone()[0]
    assert count == 2
