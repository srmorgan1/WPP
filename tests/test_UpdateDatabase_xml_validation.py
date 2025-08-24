"""Tests for enhanced XML validation in UpdateDatabase.py."""

import xml.etree.ElementTree as et
from unittest.mock import patch

import pytest

from wpp.UpdateDatabase import _extract_balance_data, _validate_balance_xml_structure, _validate_transaction_xml_structure, get_element_text


def test_get_element_text_enhanced_validation():
    """Test enhanced get_element_text function."""
    root = et.Element("root")

    # Test with valid element
    child = et.SubElement(root, "valid")
    child.text = "  test_value  "
    assert get_element_text(root, "valid") == "test_value"  # Should be stripped

    # Test with missing element
    with pytest.raises(ValueError, match="Missing required XML element: missing"):
        get_element_text(root, "missing")

    # Test with empty element
    empty = et.SubElement(root, "empty")
    empty.text = None
    with pytest.raises(ValueError, match="Empty required XML element: empty"):
        get_element_text(root, "empty")

    # Test with whitespace-only element
    whitespace = et.SubElement(root, "whitespace")
    whitespace.text = "   "
    with pytest.raises(ValueError, match="Empty required XML element: whitespace"):
        get_element_text(root, "whitespace")


def test_validate_transaction_xml_structure_valid():
    """Test transaction XML structure validation with valid XML."""
    root = et.Element("root")

    # Add TransactionRecord elements
    et.SubElement(root, "TransactionRecord")
    et.SubElement(root, "TransactionRecord")

    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _validate_transaction_xml_structure(root)
        mock_logger.debug.assert_called_with("Found 2 transaction records in XML")


def test_validate_transaction_xml_structure_no_records():
    """Test transaction XML structure validation with no TransactionRecord elements."""
    root = et.Element("root")
    # No TransactionRecord elements

    with pytest.raises(ValueError, match="No TransactionRecord elements found in XML - possible schema change"):
        _validate_transaction_xml_structure(root)


def test_validate_balance_xml_structure_valid():
    """Test balance XML structure validation with valid XML."""
    root = et.Element("root")

    # Add ReportingDay elements
    reporting_day1 = et.SubElement(root, "ReportingDay")
    reporting_day2 = et.SubElement(root, "ReportingDay")

    # Add BalanceRecord elements
    et.SubElement(reporting_day1, "BalanceRecord")
    et.SubElement(reporting_day1, "BalanceRecord")
    et.SubElement(reporting_day2, "BalanceRecord")

    with patch("wpp.UpdateDatabase.logger") as mock_logger:
        _validate_balance_xml_structure(root)
        mock_logger.debug.assert_called_with("Found 2 reporting days and 3 balance records in XML")


def test_validate_balance_xml_structure_no_reporting_days():
    """Test balance XML structure validation with no ReportingDay elements."""
    root = et.Element("root")
    # No ReportingDay elements

    with pytest.raises(ValueError, match="No ReportingDay elements found in XML - possible schema change"):
        _validate_balance_xml_structure(root)


def test_validate_balance_xml_structure_no_balance_records():
    """Test balance XML structure validation with no BalanceRecord elements."""
    root = et.Element("root")

    # Add ReportingDay but no BalanceRecord elements
    et.SubElement(root, "ReportingDay")

    with pytest.raises(ValueError, match="No BalanceRecord elements found in XML - possible schema change"):
        _validate_balance_xml_structure(root)


def test_extract_balance_data_with_client_ref():
    """Test extracting balance data with ClientRef present."""
    balance = et.Element("BalanceRecord")

    et.SubElement(balance, "SortCode").text = "12-34-56"
    et.SubElement(balance, "AccountNumber").text = "12345678"
    et.SubElement(balance, "ClientRef").text = "  RENT001  "  # With whitespace
    et.SubElement(balance, "LongName").text = "Test Account"
    et.SubElement(balance, "CurrentBalance").text = "1000.50"
    et.SubElement(balance, "AvailableBalance").text = "900.25"

    data = _extract_balance_data(balance)

    assert data["client_ref"] == "RENT001"  # Should be stripped
    assert data["account_type"] == "GR"  # Should be determined from client_ref


def test_extract_balance_data_no_client_ref():
    """Test extracting balance data with no ClientRef element."""
    balance = et.Element("BalanceRecord")

    et.SubElement(balance, "SortCode").text = "12-34-56"
    et.SubElement(balance, "AccountNumber").text = "12345678"
    # No ClientRef element
    et.SubElement(balance, "LongName").text = "Test Account"
    et.SubElement(balance, "CurrentBalance").text = "1000.50"
    et.SubElement(balance, "AvailableBalance").text = "900.25"

    data = _extract_balance_data(balance)

    assert data["client_ref"] is None
    assert data["account_type"] == "NA"


def test_extract_balance_data_empty_client_ref():
    """Test extracting balance data with empty ClientRef."""
    balance = et.Element("BalanceRecord")

    et.SubElement(balance, "SortCode").text = "12-34-56"
    et.SubElement(balance, "AccountNumber").text = "12345678"
    client_ref_elem = et.SubElement(balance, "ClientRef")
    client_ref_elem.text = "   "  # Whitespace only
    et.SubElement(balance, "LongName").text = "Test Account"
    et.SubElement(balance, "CurrentBalance").text = "1000.50"
    et.SubElement(balance, "AvailableBalance").text = "900.25"

    data = _extract_balance_data(balance)

    assert data["client_ref"] is None  # Empty string should be treated as None
    assert data["account_type"] == "NA"


def test_extract_balance_data_null_client_ref():
    """Test extracting balance data with null ClientRef text."""
    balance = et.Element("BalanceRecord")

    et.SubElement(balance, "SortCode").text = "12-34-56"
    et.SubElement(balance, "AccountNumber").text = "12345678"
    client_ref_elem = et.SubElement(balance, "ClientRef")
    client_ref_elem.text = None  # Explicit None
    et.SubElement(balance, "LongName").text = "Test Account"
    et.SubElement(balance, "CurrentBalance").text = "1000.50"
    et.SubElement(balance, "AvailableBalance").text = "900.25"

    data = _extract_balance_data(balance)

    assert data["client_ref"] is None
    assert data["account_type"] == "NA"


def test_extract_balance_data_missing_required_field():
    """Test extracting balance data with missing required field."""
    balance = et.Element("BalanceRecord")

    et.SubElement(balance, "SortCode").text = "12-34-56"
    # Missing AccountNumber (required)
    et.SubElement(balance, "LongName").text = "Test Account"
    et.SubElement(balance, "CurrentBalance").text = "1000.50"
    et.SubElement(balance, "AvailableBalance").text = "900.25"

    with pytest.raises(ValueError, match="Missing required XML element: AccountNumber"):
        _extract_balance_data(balance)


def test_extract_balance_data_empty_required_field():
    """Test extracting balance data with empty required field."""
    balance = et.Element("BalanceRecord")

    et.SubElement(balance, "SortCode").text = "12-34-56"
    account_num_elem = et.SubElement(balance, "AccountNumber")
    account_num_elem.text = ""  # Empty
    et.SubElement(balance, "LongName").text = "Test Account"
    et.SubElement(balance, "CurrentBalance").text = "1000.50"
    et.SubElement(balance, "AvailableBalance").text = "900.25"

    with pytest.raises(ValueError, match="Empty required XML element: AccountNumber"):
        _extract_balance_data(balance)
