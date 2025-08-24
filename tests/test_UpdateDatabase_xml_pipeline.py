"""Tests for XML loading and validation pipeline in UpdateDatabase.py using synthetic data only."""

import tempfile
import xml.etree.ElementTree as et
from pathlib import Path
from unittest.mock import patch

import pytest

from wpp.UpdateDatabase import _prepare_bos_transaction_xml, _prepare_bos_xml


def test_prepare_bos_transaction_xml_valid():
    """Test transaction XML preparation with synthetic data."""
    # Synthetic XML structure without namespaces (simpler case)
    xml_content = """<?xml version="1.0"?>
<PreviousDayTransactionExtract>
    <TransactionRecord>
        <Description>AAA-BB-CCC TEST</Description>
        <SortCode>00-00-00</SortCode>
        <AccountNumber>00000000</AccountNumber>
        <TransactionType>Credit</TransactionType>
        <Amount>1.00</Amount>
        <PayDate>2000-01-01</PayDate>
    </TransactionRecord>
</PreviousDayTransactionExtract>"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as temp_file:
        temp_file.write(xml_content)
        temp_path = Path(temp_file.name)

    try:
        root = _prepare_bos_transaction_xml(temp_path)
        transaction_records = list(root.iter("TransactionRecord"))
        assert len(transaction_records) == 1
        assert root.tag == "PreviousDayTransactionExtract"
    finally:
        temp_path.unlink()


def test_prepare_bos_transaction_xml_schema_change():
    """Test detection of schema changes in transaction XML."""
    xml_content = """<?xml version="1.0"?>
<root>
    <DifferentRecord>Not a TransactionRecord</DifferentRecord>
</root>"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as temp_file:
        temp_file.write(xml_content)
        temp_path = Path(temp_file.name)

    try:
        with pytest.raises(ValueError, match="No TransactionRecord elements found in XML - possible schema change"):
            _prepare_bos_transaction_xml(temp_path)
    finally:
        temp_path.unlink()


def test_prepare_bos_xml_valid():
    """Test balance XML preparation with synthetic data."""
    xml_content = """<?xml version="1.0"?>
<BalanceDetailedReport>
    <ReportingDay>
        <Date>2000-01-01</Date>
        <BalanceRecord>
            <SortCode>00-00-00</SortCode>
            <AccountNumber>00000000</AccountNumber>
            <LongName>Test</LongName>
            <CurrentBalance>1.00</CurrentBalance>
            <AvailableBalance>1.00</AvailableBalance>
        </BalanceRecord>
    </ReportingDay>
</BalanceDetailedReport>"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as temp_file:
        temp_file.write(xml_content)
        temp_path = Path(temp_file.name)

    try:
        root = _prepare_bos_xml(temp_path)
        reporting_days = list(root.iter("ReportingDay"))
        balance_records = list(root.iter("BalanceRecord"))
        assert len(reporting_days) == 1
        assert len(balance_records) == 1
        assert root.tag == "BalanceDetailedReport"
    finally:
        temp_path.unlink()


def test_prepare_bos_xml_schema_change_no_reporting_days():
    """Test detection of schema changes - missing ReportingDay elements."""
    xml_content = """<?xml version="1.0"?>
<root>
    <DifferentElement>No ReportingDay here</DifferentElement>
</root>"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as temp_file:
        temp_file.write(xml_content)
        temp_path = Path(temp_file.name)

    try:
        with pytest.raises(ValueError, match="No ReportingDay elements found in XML - possible schema change"):
            _prepare_bos_xml(temp_path)
    finally:
        temp_path.unlink()


def test_prepare_bos_xml_schema_change_no_balance_records():
    """Test detection of schema changes - missing BalanceRecord elements."""
    xml_content = """<?xml version="1.0"?>
<root>
    <ReportingDay>
        <Date>2000-01-01</Date>
    </ReportingDay>
</root>"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as temp_file:
        temp_file.write(xml_content)
        temp_path = Path(temp_file.name)

    try:
        with pytest.raises(ValueError, match="No BalanceRecord elements found in XML - possible schema change"):
            _prepare_bos_xml(temp_path)
    finally:
        temp_path.unlink()


def test_bos_schema_namespace_removal():
    """Test that Bank of Scotland schema namespaces are properly removed."""
    xml_content = """<?xml version="1.0"?>
<BalanceDetailedReport xmlns="https://isite.bankofscotland.co.uk/Schemas/BalanceDetailedReport.xsd">
    <ReportingDay>
        <Date>2000-01-01</Date>
        <BalanceRecord>
            <SortCode>00-00-00</SortCode>
            <AccountNumber>00000000</AccountNumber>
            <LongName>Test</LongName>
            <CurrentBalance>1.00</CurrentBalance>
            <AvailableBalance>1.00</AvailableBalance>
        </BalanceRecord>
    </ReportingDay>
</BalanceDetailedReport>"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as temp_file:
        temp_file.write(xml_content)
        temp_path = Path(temp_file.name)

    try:
        root = _prepare_bos_xml(temp_path)
        # Verify the function works with Bank of Scotland schema namespace
        assert root.tag == "BalanceDetailedReport"
        reporting_days = list(root.iter("ReportingDay"))
        assert len(reporting_days) == 1
        balance_records = list(root.iter("BalanceRecord"))
        assert len(balance_records) == 1
    finally:
        temp_path.unlink()


def test_xml_parse_error_propagation():
    """Test that ParseError is properly propagated with diagnostic info."""
    xml_content = """<?xml version="1.0"?>
<root>
    <unclosed_tag>
</root>"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as temp_file:
        temp_file.write(xml_content)
        temp_path = Path(temp_file.name)

    try:
        with pytest.raises(et.ParseError):
            _prepare_bos_transaction_xml(temp_path)
    finally:
        temp_path.unlink()


def test_xml_pipeline_validation_logging():
    """Test that XML validation logging occurs."""
    xml_content = """<?xml version="1.0"?>
<root>
    <TransactionRecord><Description>TEST</Description></TransactionRecord>
    <TransactionRecord><Description>TEST2</Description></TransactionRecord>
</root>"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as temp_file:
        temp_file.write(xml_content)
        temp_path = Path(temp_file.name)

    try:
        with patch("wpp.UpdateDatabase.logger") as mock_logger:
            _prepare_bos_transaction_xml(temp_path)
            mock_logger.debug.assert_called_with("Found 2 transaction records in XML")
    finally:
        temp_path.unlink()
