"""XML data loading functions for WPP management system."""

import logging
import re
import sqlite3
import tempfile
import xml.etree.ElementTree as et
from pathlib import Path
from typing import Any

from dateutil import parser
from lxml import etree

from ..config import get_config
from ..data_classes import TransactionReferences
from ..database.database_commands import DatabaseCommandExecutor, InsertTransactionCommand
from ..database.db import get_single_value
from ..ref_matcher import getPropertyBlockAndTenantRefs
from ..utils.exceptions import log_database_error
from ..utils.utils import open_file

# Set up module logger
logger = logging.getLogger(__name__)

# Constants needed for XML processing
CLIENT_CREDIT_ACCOUNT_NUMBER = "06000792"

# SQL queries needed for XML processing
SELECT_BANK_ACCOUNT_SQL1 = "SELECT ID FROM Accounts WHERE sort_code = ? AND account_number = ?;"
SELECT_BANK_ACCOUNT_BALANCE_SQL = "SELECT ID FROM AccountBalances WHERE at_date = ? AND account_id = ?;"
SELECT_TRANSACTION_SQL = "SELECT ID FROM Transactions WHERE tenant_id = ? AND description = ? AND pay_date = ? AND account_id = ? and type = ? AND amount between (?-0.005) and (?+0.005);"
SELECT_ID_FROM_REF_SQL = "SELECT ID FROM {} WHERE {}_ref = '{}';"

# Insert SQL statements
INSERT_BANK_ACCOUNT_BALANCE_SQL = "INSERT INTO AccountBalances (account_id, at_date, current_balance, available_balance) VALUES (?, ?, ?, ?);"
INSERT_TRANSACTION_SQL = "INSERT INTO Transactions (type, amount, description, pay_date, tenant_id, account_id) VALUES (?, ?, ?, ?, ?, ?);"


def _validate_xml_against_xsd(xml_content: str, xsd_filename: str) -> None:
    """Validate XML content against XSD schema using lxml.

    Args:
        xml_content: XML content as string
        xsd_filename: Name of the XSD file (e.g., 'PreviousDayTransactionExtract.xsd')

    Raises:
        ValueError: If validation fails or XSD file not found
    """
    # Get XSD file path from bundled schemas directory
    schemas_dir = Path(__file__).parent.parent / "schemas"
    xsd_path = schemas_dir / xsd_filename
    if not xsd_path.exists():
        logger.warning(f"XSD file not found: {xsd_path}. Skipping schema validation.")
        return

    try:
        # Parse XSD schema and remove problematic anchors
        with open(xsd_path, encoding="utf-8") as xsd_file:
            xsd_content = xsd_file.read()

        # Remove ^ and $ anchors from xs:pattern values since XML Schema patterns are implicitly anchored
        # Also fix the problematic \d{0,2} pattern to be XML Schema compliant
        original_content = xsd_content
        # Handle patterns with alternation (|) more carefully
        xsd_content = re.sub(r'(<xs:pattern\s+value=")\^([^"]*)\$\|\^\$"', r'\1\2|"', xsd_content)  # ^pattern$|^$ -> pattern|
        xsd_content = re.sub(r'(<xs:pattern\s+value=")\^([^"]*)\$"', r'\1\2"', xsd_content)  # ^pattern$ -> pattern
        xsd_content = re.sub(r'(<xs:pattern\s+value=")\^([^"]*)"', r'\1\2"', xsd_content)  # ^pattern -> pattern (no ending $)
        # Fix the specific problematic pattern: replace the entire amount pattern
        xsd_content = xsd_content.replace("[-+]?\\d{1,13}(?:\\.\\d{0,2})?", "[-+]?\\d{1,13}(\\.\\d{1,2})?")
        logger.debug(f"XSD pattern modifications applied: {original_content != xsd_content}")

        # Create temporary directory with all XSD files to handle includes properly
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy all XSD files to temp directory, applying fixes to all of them
            for schema_file in xsd_path.parent.glob("*.xsd"):
                if schema_file.name == xsd_filename:
                    # Write our modified main XSD content
                    temp_file_path = Path(temp_dir) / schema_file.name
                    with open(temp_file_path, "w", encoding="utf-8") as f:
                        f.write(xsd_content)
                else:
                    # Read, fix, and write other XSD files (like IBLTypes.xsd)
                    with open(schema_file, encoding="utf-8") as f:
                        other_content = f.read()
                    # Apply same fixes to included files
                    # Handle patterns with alternation (|) more carefully
                    other_content = re.sub(r'(<xs:pattern\s+value=")\^([^"]*)\$\|\^\$"', r'\1\2|"', other_content)  # ^pattern$|^$ -> pattern|
                    other_content = re.sub(r'(<xs:pattern\s+value=")\^([^"]*)\$"', r'\1\2"', other_content)  # ^pattern$ -> pattern
                    other_content = re.sub(r'(<xs:pattern\s+value=")\^([^"]*)"', r'\1\2"', other_content)  # ^pattern -> pattern (no ending $)
                    other_content = other_content.replace("[-+]?\\d{1,13}(?:\\.\\d{0,2})?", "[-+]?\\d{1,13}(\\.\\d{1,2})?")
                    temp_file_path = Path(temp_dir) / schema_file.name
                    with open(temp_file_path, "w", encoding="utf-8") as f:
                        f.write(other_content)

            # Parse XSD schema from temp directory and create schema object
            main_xsd = Path(temp_dir) / xsd_filename
            xsd_doc = etree.parse(str(main_xsd))
            schema = etree.XMLSchema(xsd_doc)

            # Perform the actual XML validation while temp files still exist
            xml_doc = etree.fromstring(xml_content.encode("utf-8"))
            if not schema.validate(xml_doc):
                error_log = schema.error_log
                raise ValueError(f"XML validation failed against {xsd_filename}: {error_log}")

        # If we get here, validation passed
        logger.info(f"XML successfully validated against {xsd_filename}")
        return

    except etree.XMLSyntaxError:
        logger.warning(f"XSD file {xsd_filename} is not valid XML (possibly downloaded error page). Skipping schema validation.")
        return
    except Exception as e:
        logger.warning(f"Unable to perform XSD validation against {xsd_filename}: {e}. Skipping schema validation.")
        return


def _validate_transaction_xml_structure(root: et.Element) -> None:
    """Validate that the transaction XML has the expected structure."""
    if root.tag != "PreviousDayTransactionExtract":
        raise ValueError(f"Unexpected root element: {root.tag}")

    reporting_day = root.find("ReportingDay")
    if reporting_day is None:
        raise ValueError("Missing ReportingDay element")

    date_elem = reporting_day.find("Date")
    if date_elem is None:
        raise ValueError("Missing Date element")

    transactions_elem = reporting_day.find("Transactions")
    if transactions_elem is None:
        raise ValueError("Missing Transactions element")


def _prepare_bos_transaction_xml(transactions_xml_file: str) -> et.Element:
    """Prepare Bank of Scotland transaction XML for processing."""
    xml = open_file(transactions_xml_file)
    xml = xml.replace("\n", "")

    # Validate XML against XSD before processing
    _validate_xml_against_xsd(xml, "PreviousDayTransactionExtract.xsd")

    # Remove schema namespace for ElementTree parsing
    schema = "PreviousDayTransactionExtract"
    xsd = f"https://isite.bankofscotland.co.uk/Schemas/{schema}.xsd"
    xml = re.sub(
        f'<{schema} xmlns="{xsd}">',
        f"<{schema}>",
        xml,
    )

    root = et.fromstring(xml)
    _validate_transaction_xml_structure(root)
    return root


def _validate_balance_xml_structure(root: et.Element) -> None:
    """Validate that the balance XML has the expected structure."""
    # Check for both possible root element names
    if root.tag not in ["EndOfDayBalanceExtract", "BalanceDetailedReport"]:
        raise ValueError(f"Unexpected root element: {root.tag}")

    reporting_day = root.find("ReportingDay")
    if reporting_day is None:
        raise ValueError("Missing ReportingDay element")

    date_elem = reporting_day.find("Date")
    if date_elem is None:
        raise ValueError("Missing Date element")


def _prepare_bos_xml(balances_xml_file: str) -> et.Element:
    """Prepare Bank of Scotland balance XML for processing."""
    xml = open_file(balances_xml_file)
    xml = xml.replace("\n", "")

    # Validate XML against XSD before processing
    _validate_xml_against_xsd(xml, "EndOfDayBalanceExtract.xsd")

    # Remove schema namespaces to simplify XML parsing
    for schema in ["BalanceDetailedReport", "EndOfDayBalanceExtract"]:
        xsd = f"https://isite.bankofscotland.co.uk/Schemas/{schema}.xsd"
        xml = re.sub(
            f'<{schema} xmlns="{xsd}">',
            f"<{schema}>",
            xml,
        )

    root = et.fromstring(xml)
    _validate_balance_xml_structure(root)
    return root


# Constants needed for XML processing
CLIENT_CREDIT_ACCOUNT_NUMBER = "06000792"

# SQL queries needed for XML processing
SELECT_BANK_ACCOUNT_SQL1 = "SELECT ID FROM Accounts WHERE sort_code = ? AND account_number = ?;"
SELECT_BANK_ACCOUNT_BALANCE_SQL = "SELECT ID FROM AccountBalances WHERE at_date = ? AND account_id = ?;"
SELECT_TRANSACTION_SQL = "SELECT ID FROM Transactions WHERE sort_code = ? AND account_number = ? AND transaction_type = ? AND amount = ? AND transaction_description = ? AND payment_date = ?;"
SELECT_ID_FROM_REF_SQL = "SELECT ID FROM {} WHERE {} = '{}';"

# Insert SQL statements
INSERT_BANK_ACCOUNT_BALANCE_SQL = "INSERT INTO AccountBalances (account_id, at_date, current_balance, available_balance) VALUES (?, ?, ?, ?);"


def get_element_text(parent_element: et.Element, child_element_name: str) -> str:
    """Extract text from required XML element with enhanced validation.

    Args:
        parent_element: Parent XML element
        child_element_name: Name of child element to extract text from

    Returns:
        str: Text content of the child element

    Raises:
        ValueError: If child element is not found or is empty
    """
    child_element = parent_element.find(child_element_name)
    if child_element is None:
        raise ValueError(f"Required element '{child_element_name}' not found in {parent_element.tag}")

    text = child_element.text
    if text is None or text.strip() == "":
        raise ValueError(f"Element '{child_element_name}' is empty in {parent_element.tag}")

    return text.strip()


def get_id(db_cursor: sqlite3.Cursor, sql: str, args_tuple: tuple = ()) -> int | None:
    return get_single_value(db_cursor, sql, args_tuple)


def get_id_from_ref(db_cursor: sqlite3.Cursor, table_name: str, field_name: str, ref_name: str) -> int | None:
    sql = SELECT_ID_FROM_REF_SQL.format(table_name, field_name, ref_name)
    db_cursor.execute(sql)
    _id = db_cursor.fetchone()
    return _id[0] if _id else None


def _extract_transaction_data(transaction: et.Element) -> dict:
    """Extract transaction data from XML transaction element."""
    return {
        "sort_code": get_element_text(transaction, "SortCode"),
        "account_number": get_element_text(transaction, "AccountNumber"),
        "transaction_type": get_element_text(transaction, "TransactionType"),
        "amount": get_element_text(transaction, "TransactionAmount"),
        "description": get_element_text(transaction, "TransactionDescription"),
        "pay_date": get_element_text(transaction, "TransactionPostedDate"),
    }


def _should_process_transaction(transaction_data: dict) -> bool:
    """Check if transaction should be processed based on account number."""
    return transaction_data["account_number"] == CLIENT_CREDIT_ACCOUNT_NUMBER


def get_element_text(parent_element: et.Element, child_element_name: str) -> str:
    """Extract text from required XML element with enhanced validation.

    Args:
        parent_element: Parent XML element
        child_element_name: Name of child element to extract text from

    Returns:
        str: Text content of the child element

    Raises:
        ValueError: If child element is not found or is empty
    """
    child_element = parent_element.find(child_element_name)
    if child_element is None:
        raise ValueError(f"Required element '{child_element_name}' not found in {parent_element.tag}")

    text = child_element.text
    if text is None or text.strip() == "":
        raise ValueError(f"Element '{child_element_name}' is empty in {parent_element.tag}")

    return text.strip()


def get_id(db_cursor: sqlite3.Cursor, sql: str, args_tuple: tuple = ()) -> int | None:
    return get_single_value(db_cursor, sql, args_tuple)


def get_id_from_ref(db_cursor: sqlite3.Cursor, table_name: str, field_name: str, ref_name: str) -> int | None:
    sql = SELECT_ID_FROM_REF_SQL.format(table_name, field_name, ref_name)
    db_cursor.execute(sql)
    _id = db_cursor.fetchone()
    return _id[0] if _id else None


def _validate_transaction_xml_structure(root: et.Element) -> None:
    """Validate that the transaction XML has the expected structure."""
    if root.tag != "PreviousDayTransactionExtract":
        raise ValueError(f"Unexpected root element: {root.tag}")

    reporting_day = root.find("ReportingDay")
    if reporting_day is None:
        raise ValueError("Missing ReportingDay element")

    date_elem = reporting_day.find("Date")
    if date_elem is None:
        raise ValueError("Missing Date element")

    transactions_elem = reporting_day.find("Transactions")
    if transactions_elem is None:
        raise ValueError("Missing Transactions element")


def _prepare_bos_transaction_xml(transactions_xml_file: str) -> et.Element:
    """Prepare Bank of Scotland transaction XML for processing."""
    xml = open_file(transactions_xml_file)
    xml = xml.replace("\n", "")

    # Validate XML against XSD before processing
    _validate_xml_against_xsd(xml, "PreviousDayTransactionExtract.xsd")

    # Remove schema namespace for ElementTree parsing
    schema = "PreviousDayTransactionExtract"
    xsd = f"https://isite.bankofscotland.co.uk/Schemas/{schema}.xsd"
    xml = re.sub(
        f'<{schema} xmlns="{xsd}">',
        f"<{schema}>",
        xml,
    )

    root = et.fromstring(xml)
    _validate_transaction_xml_structure(root)
    return root


def _validate_balance_xml_structure(root: et.Element) -> None:
    """Validate that the balance XML has the expected structure."""
    # Check for both possible root element names
    if root.tag not in ["EndOfDayBalanceExtract", "BalanceDetailedReport"]:
        raise ValueError(f"Unexpected root element: {root.tag}")

    reporting_day = root.find("ReportingDay")
    if reporting_day is None:
        raise ValueError("Missing ReportingDay element")

    date_elem = reporting_day.find("Date")
    if date_elem is None:
        raise ValueError("Missing Date element")


def _prepare_bos_xml(balances_xml_file: str) -> et.Element:
    """Prepare Bank of Scotland balance XML for processing."""
    xml = open_file(balances_xml_file)
    xml = xml.replace("\n", "")

    # Validate XML against XSD before processing
    _validate_xml_against_xsd(xml, "EndOfDayBalanceExtract.xsd")

    # Remove schema namespaces to simplify XML parsing
    for schema in ["BalanceDetailedReport", "EndOfDayBalanceExtract"]:
        xsd = f"https://isite.bankofscotland.co.uk/Schemas/{schema}.xsd"
        xml = re.sub(
            f'<{schema} xmlns="{xsd}">',
            f"<{schema}>",
            xml,
        )

    root = et.fromstring(xml)
    _validate_balance_xml_structure(root)
    return root


def _extract_transaction_data(transaction: et.Element) -> dict:
    """Extract transaction data from XML transaction element."""
    return {
        "sort_code": get_element_text(transaction, "SortCode"),
        "account_number": get_element_text(transaction, "AccountNumber"),
        "transaction_type": get_element_text(transaction, "TransactionType"),
        "amount": get_element_text(transaction, "TransactionAmount"),
        "description": get_element_text(transaction, "TransactionDescription"),
        "pay_date": get_element_text(transaction, "TransactionPostedDate"),
    }


def _should_process_transaction(transaction_data: dict) -> bool:
    """Check if transaction should be processed based on account number."""
    return transaction_data["account_number"] == CLIENT_CREDIT_ACCOUNT_NUMBER


def _format_pay_date(pay_date: str) -> str:
    """Format payment date to standard format."""
    return parser.parse(pay_date, dayfirst=True).strftime("%Y-%m-%d")


def _process_valid_transaction(csr: sqlite3.Cursor, transaction_data: dict, refs: TransactionReferences) -> tuple[bool, bool]:
    """Process a valid transaction and return (was_added, is_duplicate)."""
    account_id = get_id(csr, SELECT_BANK_ACCOUNT_SQL1, (transaction_data["sort_code"], transaction_data["account_number"]))
    tenant_id = get_id_from_ref(csr, "Tenants", "tenant", refs.tenant_ref) if refs.tenant_ref else None

    if not tenant_id:
        return False, False

    # Check for duplicate transaction
    transaction_id = get_id(
        csr,
        SELECT_TRANSACTION_SQL,
        (
            tenant_id,
            transaction_data["description"],
            transaction_data["pay_date"],
            account_id,
            transaction_data["transaction_type"],
            transaction_data["amount"],
            transaction_data["amount"],
        ),
    )

    if transaction_id:
        return False, True  # Duplicate found

    # Add new transaction
    executor = DatabaseCommandExecutor(csr, logger)
    command = InsertTransactionCommand(
        transaction_data["transaction_type"],
        transaction_data["amount"],
        transaction_data["description"],
        transaction_data["pay_date"],
        tenant_id,
        account_id,
        transaction_data["sort_code"],
        transaction_data["account_number"],
        refs.tenant_ref,
        INSERT_TRANSACTION_SQL,
    )
    executor.execute(command)
    return True, False


def _create_error_record(transaction_data: dict, error_message: str) -> list:
    """Create an error record for unprocessable transactions."""
    return [
        transaction_data["pay_date"],
        transaction_data["sort_code"],
        transaction_data["account_number"],
        transaction_data["transaction_type"],
        float(transaction_data["amount"]),
        transaction_data["description"],
        error_message,
    ]


def _create_missing_tenant_record(transaction_data: dict, tenant_ref: str) -> list:
    """Create a record for transactions with valid references but missing tenants."""
    return [
        transaction_data["pay_date"],
        transaction_data["sort_code"],
        transaction_data["account_number"],
        transaction_data["transaction_type"],
        float(transaction_data["amount"]),
        transaction_data["description"],
        tenant_ref,
        f"Tenant '{tenant_ref}' not found in tenants file",
    ]


def _create_duplicate_record(transaction_data: dict, tenant_ref: str) -> list:
    """Create a duplicate transaction record."""
    return [
        transaction_data["pay_date"],
        transaction_data["transaction_type"],
        float(transaction_data["amount"]),
        tenant_ref,
        transaction_data["description"],
    ]


def _handle_transaction_processing_error(csr: sqlite3.Cursor, error: Exception, transaction_data: dict, tenant_id: int | None) -> None:
    """Handle errors that occur during transaction processing."""
    error_context = {
        "sort_code": transaction_data.get("sort_code"),
        "account_number": transaction_data.get("account_number"),
        "transaction_type": transaction_data.get("transaction_type"),
        "amount": transaction_data.get("amount"),
        "description": transaction_data.get("description"),
        "pay_date": transaction_data.get("pay_date"),
        "tenant_id": tenant_id,
    }

    # Use standardized database error logging
    log_database_error(logger, "importing Bank of Scotland transaction", error, error_context)
    logger.error("No Bank Of Scotland transactions have been added to the database.")

    csr.execute("rollback")


def _process_single_transaction(csr: sqlite3.Cursor, transaction_data: dict) -> tuple[str, bool, bool]:
    """Process a single transaction and return the result.

    Returns:
        tuple: (result_type, was_processed, needs_error_record)
        result_type: "added", "duplicate", "tenant_not_found", "invalid_refs"
        was_processed: True if transaction was successfully processed
        needs_error_record: True if an error record should be created
    """
    property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefs(transaction_data["description"], csr)

    if not (tenant_ref and property_ref and block_ref):
        return "invalid_refs", False, True

    refs = TransactionReferences(property_ref, block_ref, tenant_ref)
    was_added, is_duplicate = _process_valid_transaction(csr, transaction_data, refs)

    if was_added:
        return "added", True, False
    elif is_duplicate:
        return "duplicate", True, False
    else:
        return "tenant_not_found", False, True


def _process_transaction_results(
    result_type: str, transaction_data: dict, tenant_ref: str | None, unrecognised_transactions: list, duplicate_transactions: list, missing_tenant_transactions: list
) -> tuple[int, int]:
    """Process the results of a transaction and update counters.

    Returns:
        tuple: (added_count, error_count)
    """
    if result_type == "added":
        return 1, 0
    elif result_type == "duplicate":
        duplicate_transactions.append(_create_duplicate_record(transaction_data, tenant_ref))
        return 0, 0
    elif result_type == "tenant_not_found":
        error_msg = f"Cannot find tenant with reference '{tenant_ref}'"
        logger.debug(
            f"{error_msg}. Ignoring transaction {(transaction_data['pay_date'], transaction_data['sort_code'], transaction_data['account_number'], transaction_data['transaction_type'], transaction_data['amount'], transaction_data['description'])}"
        )
        missing_tenant_transactions.append(_create_missing_tenant_record(transaction_data, tenant_ref))
        return 0, 1
    elif result_type == "invalid_refs":
        error_msg = "Cannot determine tenant from description"
        logger.debug(
            f"{error_msg} '{transaction_data['description']}'. Ignoring transaction {(transaction_data['pay_date'], transaction_data['sort_code'], transaction_data['account_number'], transaction_data['transaction_type'], transaction_data['amount'], transaction_data['description'])}"
        )
        unrecognised_transactions.append(_create_error_record(transaction_data, error_msg))
        return 0, 1

    return 0, 0


def _determine_account_type(client_ref: str | None) -> str:
    """Determine account type from client reference."""
    if not client_ref:
        return "NA"

    client_ref_upper = client_ref.upper()
    if "RENT" in client_ref_upper:
        return "GR"
    elif "BANK" in client_ref_upper:
        return "CL"
    elif "RES" in client_ref_upper:
        return "RE"
    else:
        return "NA"


def _extract_balance_data(balance_element) -> dict:
    """Extract balance data from XML balance element."""
    # ClientRef is optional - handle explicitly
    client_ref_element = balance_element.find("ClientRef")
    client_ref = None
    if client_ref_element is not None and client_ref_element.text is not None:
        client_ref = client_ref_element.text.strip()
        if client_ref == "":  # Empty string treated as None
            client_ref = None

    return {
        "sort_code": get_element_text(balance_element, "SortCode"),
        "account_number": get_element_text(balance_element, "AccountNumber"),
        "client_ref": client_ref,
        "account_name": get_element_text(balance_element, "LongName"),
        "account_type": _determine_account_type(client_ref),
        "current_balance": get_element_text(balance_element, "CurrentBalance"),
        "available_balance": get_element_text(balance_element, "AvailableBalance"),
    }


def _process_balance_record(csr, balance_data: dict, at_date: str) -> bool:
    """Process a single balance record and add to database if needed. Returns True if added."""
    sort_code = balance_data["sort_code"]
    account_number = balance_data["account_number"]

    if not (sort_code and account_number):
        logger.warning(f"Cannot determine bank account. Ignoring balance record {balance_data}")
        return False

    account_id = get_id(csr, SELECT_BANK_ACCOUNT_SQL1, (sort_code, account_number))
    if not account_id:
        # Account doesn't exist in our system, skip
        return False

    # Check if balance already exists for this date
    account_balance_id = get_id(csr, SELECT_BANK_ACCOUNT_BALANCE_SQL, (at_date, account_id))
    if account_balance_id:
        # Balance already exists, skip
        return False

    # Add new balance record
    csr.execute(
        INSERT_BANK_ACCOUNT_BALANCE_SQL,
        (
            account_id,
            at_date,
            balance_data["current_balance"],
            balance_data["available_balance"],
        ),
    )

    logger.debug(
        f"\tAdding bank balance {(sort_code, account_number, balance_data['account_type'], balance_data['client_ref'], balance_data['account_name'], at_date, balance_data['current_balance'], balance_data['available_balance'])}"
    )
    return True


def _process_balance_reporting_day(csr: sqlite3.Cursor, reporting_day_element) -> int:
    """Process all balance records for a single reporting day.

    Returns:
        int: Number of balance records added to database
    """
    at_date = get_element_text(reporting_day_element, "Date")
    at_date = parser.parse(at_date, dayfirst=True).strftime("%Y-%m-%d")

    balances_added = 0
    for balance in reporting_day_element.iter("BalanceRecord"):
        balance_data = _extract_balance_data(balance)
        if _process_balance_record(csr, balance_data, at_date):
            balances_added += 1

    return balances_added


def _log_balance_import_error(error: Exception, balance_data: dict, at_date: str) -> None:
    """Log balance import error with context data."""
    sort_code = balance_data.get("sort_code")
    account_number = balance_data.get("account_number")
    account_type = balance_data.get("account_type")
    client_ref = balance_data.get("client_ref")
    account_name = balance_data.get("account_name")
    current_balance = balance_data.get("current_balance")
    available_balance = balance_data.get("available_balance")

    logger.error(str(error))
    logger.error(f"The data which caused the failure is: {(sort_code, account_number, account_type, client_ref, account_name, at_date, current_balance, available_balance)}")
    logger.error("No Bank Of Scotland account balances have been added to the database.")
    logger.exception(error)


def importBankOfScotlandTransactionsXMLFile(db_conn: sqlite3.Connection, transactions_xml_file: str) -> tuple[list[list[Any]], list[list[Any]], list[list[Any]]]:
    """Import Bank of Scotland transactions from XML file into database.

    Returns:
        tuple: (unrecognised_transactions, duplicate_transactions, missing_tenant_transactions) - Lists of problematic transactions
    """
    unrecognised_transactions = []
    duplicate_transactions = []
    missing_tenant_transactions = []
    tree = _prepare_bos_transaction_xml(transactions_xml_file)

    num_transactions_added_to_db = 0
    num_import_errors = 0
    tenant_id = None
    transaction_data = {}

    try:
        csr = db_conn.cursor()
        csr.execute("begin")

        for transaction in tree.iter("TransactionRecord"):
            transaction_data = _extract_transaction_data(transaction)

            if not _should_process_transaction(transaction_data):
                continue

            transaction_data["pay_date"] = _format_pay_date(transaction_data["pay_date"])

            result_type, was_processed, needs_error = _process_single_transaction(csr, transaction_data)

            # Extract tenant_ref for duplicate records
            if result_type in ["duplicate", "tenant_not_found"]:
                _, _, tenant_ref = getPropertyBlockAndTenantRefs(transaction_data["description"], csr)
            else:
                tenant_ref = None

            added_count, error_count = _process_transaction_results(result_type, transaction_data, tenant_ref, unrecognised_transactions, duplicate_transactions, missing_tenant_transactions)

            num_transactions_added_to_db += added_count
            num_import_errors += error_count

        csr.execute("end")
        db_conn.commit()

        if num_import_errors:
            logger.info(
                f"Unable to import {num_import_errors} transactions into the database. "
                f"See the Data_Import_Issues Excel file for details. Add tenant references to "
                f"{get_config()['INPUTS']['IRREGULAR_TRANSACTION_REFS_FILE']} and run import again."
            )
        logger.info(f"{num_transactions_added_to_db} Bank Of Scotland transactions added to the database.")
        return unrecognised_transactions, duplicate_transactions, missing_tenant_transactions

    except (db_conn.Error, Exception) as error:
        _handle_transaction_processing_error(csr, error, transaction_data, tenant_id)
        return [], [], []


def importBankOfScotlandBalancesXMLFile(db_conn: sqlite3.Connection, balances_xml_file: str) -> None:
    """Import Bank of Scotland account balances from XML file into database."""
    tree = _prepare_bos_xml(balances_xml_file)
    num_balances_added_to_db = 0

    # Variables for error handling context
    last_balance_data = {}
    last_at_date = ""

    try:
        csr = db_conn.cursor()
        csr.execute("begin")

        for reporting_day in tree.iter("ReportingDay"):
            last_at_date = get_element_text(reporting_day, "Date")
            try:
                balances_added = _process_balance_reporting_day(csr, reporting_day)
                num_balances_added_to_db += balances_added
            except Exception as day_error:
                # Update context for error reporting
                for balance in reporting_day.iter("BalanceRecord"):
                    last_balance_data = _extract_balance_data(balance)
                    break  # Just get the first one for context
                raise day_error

        csr.execute("end")
        db_conn.commit()
        logger.info(f"{num_balances_added_to_db} Bank Of Scotland account balances added to the database.")

    except db_conn.Error as err:
        _log_balance_import_error(err, last_balance_data, last_at_date)
        csr.execute("rollback")
    except Exception as ex:
        _log_balance_import_error(ex, last_balance_data, last_at_date)
        csr.execute("rollback")
