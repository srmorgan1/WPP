import argparse
import datetime as dt
import logging
import os
import re
import sqlite3
import xml.etree.ElementTree as et
from typing import Any

import pandas as pd
from dateutil import parser
from openpyxl import load_workbook

from .calendars import BUSINESS_DAY
from .config import get_config, get_wpp_db_file, get_wpp_excel_log_file, get_wpp_input_dir, get_wpp_report_dir, get_wpp_static_input_dir, get_wpp_update_database_log_file
from .constants import DEBIT_CARD_SUFFIX, EXCLUDED_TENANT_REF_CHARACTERS, MINIMUM_TENANT_NAME_MATCH_LENGTH, MINIMUM_VALID_PROPERTY_REF
from .data_classes import ChargeData, TransactionReferences
from .database_commands import DatabaseCommandExecutor, InsertBlockCommand, InsertChargeCommand, InsertPropertyCommand, InsertTenantCommand, InsertTransactionCommand, UpdateTenantNameCommand
from .db import checkTenantExists, get_last_insert_id, get_or_create_db, get_single_value, getTenantName
from .exceptions import database_transaction, log_database_error
from .logger import setup_logger
from .ref_matcher import getPropertyBlockAndTenantRefs as getPropertyBlockAndTenantRefs_strategy
from .utils import getLatestMatchingFileName, getLongestCommonSubstring, getMatchingFileNames, is_running_via_pytest, open_file

#
# Constants
#
CLIENT_CREDIT_ACCOUNT_NUMBER = "06000792"

# Set up logger
logger = logging.getLogger(__name__)

#
# SQL
#
INSERT_PROPERTY_SQL = "INSERT INTO Properties (property_ref, property_name) VALUES (?, Null);"
INSERT_BLOCK_SQL = "INSERT INTO Blocks (block_ref, block_name, type, property_id) VALUES (?, Null, ?, ?);"
INSERT_BLOCK_SQL2 = "INSERT INTO Blocks (block_ref, block_name, type, property_id) VALUES (?, ?, ?, ?);"
INSERT_TENANT_SQL = "INSERT INTO Tenants (tenant_ref, tenant_name, block_id) VALUES (?, ?, ?);"
INSERT_SUGGESTED_TENANT_SQL = "INSERT INTO SuggestedTenants (tenant_id, transaction_id) VALUES (?, ?);"
INSERT_TRANSACTION_SQL = "INSERT INTO Transactions (type, amount, description, pay_date, tenant_id, account_id) VALUES (?, ?, ?, ?, ?, ?);"
INSERT_CHARGES_SQL = "INSERT INTO Charges (fund_id, category_id, type_id, at_date, amount, block_id) VALUES (?, ?, ?, ?, ?, ?);"
INSERT_BANK_ACCOUNT_SQL = "INSERT INTO Accounts (sort_code, account_number, account_type, property_or_block, client_ref, account_name, block_id) VALUES (?, ?, ?, ?, ?, ?, ?);"
INSERT_BANK_ACCOUNT_BALANCE_SQL = "INSERT INTO AccountBalances (current_balance, available_balance, at_date, account_id) VALUES (?, ?, ?, ?);"
INSERT_KEY_TABLE_SQL = "INSERT INTO Key_{} (value) VALUES (?);"
INSERT_IRREGULAR_TRANSACTION_REF_SQL = "INSERT INTO IrregularTransactionRefs (tenant_ref, transaction_ref_pattern) VALUES (?, ?);"

SELECT_TENANT_ID_SQL = "SELECT tenant_id FROM Tenants WHERE tenant_ref = ?;"
SELECT_ID_FROM_REF_SQL = "SELECT ID FROM {} WHERE {}_ref = '{}';"
SELECT_ID_FROM_KEY_TABLE_SQL = "SELECT ID FROM Key_{} WHERE value = ?;"
SELECT_PROPERTY_ID_FROM_REF_SQL = "SELECT ID FROM Properties WHERE property_ref = ? AND property_name IS NULL;"
SELECT_TRANSACTION_SQL = "SELECT ID FROM Transactions WHERE tenant_id = ? AND description = ? AND pay_date = ? AND account_id = ? and type = ? AND amount between (?-0.005) and (?+0.005);"
SELECT_CHARGES_SQL = "SELECT ID FROM Charges WHERE fund_id = ? AND category_id = ? and type_id = ? and block_id = ? and at_date = ?;"
SELECT_BANK_ACCOUNT_SQL = "SELECT ID FROM Blocks WHERE ID = ? AND account_number IS Null;"
SELECT_BANK_ACCOUNT_SQL1 = "SELECT ID FROM Accounts WHERE sort_code = ? AND account_number = ?;"
SELECT_BANK_ACCOUNT_BALANCE_SQL = "SELECT ID FROM AccountBalances WHERE at_date = ? AND account_id = ?;"
SELECT_BLOCK_NAME_SQL = "SELECT block_name FROM Blocks WHERE block_ref = ?;"
SELECT_TENANT_NAME_BY_ID_SQL = "SELECT tenant_name FROM Tenants WHERE ID = ?;"
SELECT_IRREGULAR_TRANSACTION_TENANT_REF_SQL = "select tenant_ref from IrregularTransactionRefs where instr(?, transaction_ref_pattern) > 0;"
SELECT_IRREGULAR_TRANSACTION_REF_ID_SQL = "select ID from IrregularTransactionRefs where tenant_ref = ? and transaction_ref_pattern = ?;"
SELECT_ALL_IRREGULAR_TRANSACTION_REFS_SQL = "select tenant_ref, transaction_ref_pattern from IrregularTransactionRefs;"

UPDATE_BLOCK_ACCOUNT_NUMBER_SQL = "UPDATE Blocks SET account_number = ? WHERE ID = ? AND account_number IS Null;"
UPDATE_PROPERTY_DETAILS_SQL = "UPDATE Properties SET property_name = ? WHERE ID = ?;"
UPDATE_BLOCK_NAME_SQL = "UPDATE Blocks SET block_name = ? WHERE ID = ?;"
UPDATE_TENANT_NAME_SQL = "UPDATE Tenants SET tenant_name = ? WHERE ID = ?;"

# Charge types
AUTH_CREDITORS = "Auth Creditors"
AVAILABLE_FUNDS = "Available Funds"
SC_FUND = "SC Fund"

# # Regular expressions
# PBT_REGEX = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d)-(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
# PBT_REGEX2 = re.compile(r"(?:^|\s+|,)(\d\d\d)\s-\s(\d\d)\s-\s(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
# PBT_REGEX3 = re.compile(r"(?:^|\s+|,)(\d\d\d)-0?(\d\d)-(\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
# PBT_REGEX4 = re.compile(r"(?:^|\s+|,)(\d\d)-0?(\d\d)-(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
# PBT_REGEX_NO_TERMINATING_SPACE = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d)-(\d\d\d)(?:$|\s*|,|/)")
# PBT_REGEX_NO_BEGINNING_SPACE = re.compile(r"(?:^|\s*|,)(\d\d\d)-(\d\d)-(\d\d\d)(?:$|\s+|,|/)")
# PBT_REGEX_SPECIAL_CASES = re.compile(
#     r"(?:^|\s+|,|\.)(\d\d\d)-{1,2}0?(\d\d)-{1,2}(\w{2,5})\s?(?:DC)?(?:$|\s+|,|/)",
#     re.ASCII,
# )
# PBT_REGEX_NO_HYPHENS = re.compile(r"(?:^|\s+|,)(\d\d\d)\s{0,2}0?(\d\d)\s{0,2}(\d\d\d)(?:$|\s+|,|/)")
# PBT_REGEX_NO_HYPHENS_SPECIAL_CASES = re.compile(r"(?:^|\s+|,)(\d\d\d)\s{0,2}0?(\d\d)\s{0,2}(\w{3})(?:$|\s+|,|/)", re.ASCII)
# PBT_REGEX_FWD_SLASHES = re.compile(r"(?:^|\s+|,)(\d\d\d)/0?(\d\d)/(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
# PT_REGEX = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d\d)(?:$|\s+|,|/)")
# PB_REGEX = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d)(?:$|\s+|,|/)")
# P_REGEX = re.compile(r"(?:^|\s+)(\d\d\d)(?:$|\s+)")


def get_id(db_cursor: sqlite3.Cursor, sql: str, args_tuple: tuple = ()) -> int | None:
    return get_single_value(db_cursor, sql, args_tuple)


def get_id_from_ref(db_cursor: sqlite3.Cursor, table_name: str, field_name: str, ref_name: str) -> int | None:
    sql = SELECT_ID_FROM_REF_SQL.format(table_name, field_name, ref_name)
    db_cursor.execute(sql)
    _id = db_cursor.fetchone()
    if _id:
        return _id[0]
    else:
        return None


def get_id_from_key_table(db_cursor: sqlite3.Cursor, key_table_name: str, value: str) -> int:
    sql = SELECT_ID_FROM_KEY_TABLE_SQL.format(key_table_name)
    db_cursor.execute(sql, (value,))
    _id = db_cursor.fetchone()
    if _id:
        return _id[0]
    else:
        sql = INSERT_KEY_TABLE_SQL.format(key_table_name)
        db_cursor.execute(sql, (value,))
        return get_last_insert_id(db_cursor, f"Key_{key_table_name}")


def matchTransactionRef(tenant_name: str, transaction_reference: str) -> bool:
    tnm = re.sub(r"(?:^|\s+)mr?s?\s+", "", tenant_name.lower())
    tnm = re.sub(r"\s+and\s+", "", tnm)
    tnm = re.sub(r"(?:^|\s+)\w\s+", " ", tnm)
    tnm = re.sub(r"[_\W]+", " ", tnm).strip()

    trf = re.sub(r"(?:^|\s+)mr?s?\s+", "", transaction_reference.lower())
    trf = re.sub(r"\s+and\s+", "", trf)
    trf = re.sub(r"(?:^|\s+)\w\s+", " ", trf)
    trf = re.sub(r"\d", "", trf)
    trf = re.sub(r"[_\W]+", " ", trf).strip()

    if tenant_name:
        lcss = getLongestCommonSubstring(tnm, trf)
        # Assume that if the transaction reference has a substring matching
        # one in the tenant name of >= minimum length chars, then this is a match.
        return len(lcss) >= MINIMUM_TENANT_NAME_MATCH_LENGTH
    else:
        return False


def removeDCReferencePostfix(tenant_ref: str | None) -> str | None:
    # Remove 'DC' from parsed tenant references paid by debit card
    if tenant_ref is not None and tenant_ref.endswith(DEBIT_CARD_SUFFIX):
        tenant_ref = tenant_ref[:-2].strip()
    return tenant_ref


def correctKnownCommonErrors(property_ref: str, block_ref: str, tenant_ref: str | None) -> tuple[str, str, str | None]:
    # Correct known errors in the tenant payment references
    if property_ref == "094" and tenant_ref is not None and tenant_ref[-3] == "O":
        tenant_ref = tenant_ref[:-3] + "0" + tenant_ref[-2:]
    return property_ref, block_ref, tenant_ref


def recodeSpecialPropertyReferenceCases(property_ref: str, block_ref: str, tenant_ref: str | None) -> tuple[str, str, str | None]:
    if property_ref == "020" and block_ref == "020-03":
        # Block 020-03 belongs to a different property group, call this 020A.
        property_ref = "020A"
    elif property_ref == "064" and block_ref == "064-01":
        property_ref = "064A"
    return property_ref, block_ref, tenant_ref


def recodeSpecialBlockReferenceCases(property_ref: str, block_ref: str, tenant_ref: str | None) -> tuple[str, str, str | None]:
    if property_ref == "101" and block_ref == "101-02":
        # Block 101-02 is wrong, change this to 101-01
        block_ref = "101-01"
        if tenant_ref is not None:
            tenant_ref = tenant_ref.replace("101-02", "101-01")
    return property_ref, block_ref, tenant_ref


def getPropertyBlockAndTenantRefsFromRegexMatch(
    match: re.Match,
) -> tuple[str, str, str]:
    property_ref, block_ref, tenant_ref = None, None, None
    if match:
        property_ref = match.group(1)
        block_ref = f"{match.group(1)}-{match.group(2)}"
        tenant_ref = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return property_ref, block_ref, tenant_ref


def doubleCheckTenantRef(db_cursor: sqlite3.Cursor, tenant_ref: str, reference: str) -> bool:
    if not checkTenantExists(db_cursor, tenant_ref):
        return False
    tenant_name = getTenantName(db_cursor, tenant_ref)
    return matchTransactionRef(tenant_name, reference)


def postProcessPropertyBlockTenantRefs(property_ref: str | None, block_ref: str | None, tenant_ref: str | None) -> tuple[str | None, str | None, str | None]:
    # Ignore some property and tenant references, and recode special cases
    # e.g. Block 020-03 belongs to a different property than the other 020-xx blocks.
    if (tenant_ref is not None and any(char in tenant_ref for char in EXCLUDED_TENANT_REF_CHARACTERS)) or (
        property_ref is not None and property_ref.isnumeric() and int(property_ref) >= MINIMUM_VALID_PROPERTY_REF
    ):
        return None, None, None
    # Only apply special recoding if we have non-None property_ref and block_ref
    if property_ref is not None and block_ref is not None:
        property_ref, block_ref, tenant_ref = recodeSpecialPropertyReferenceCases(property_ref, block_ref, tenant_ref)
        property_ref, block_ref, tenant_ref = recodeSpecialBlockReferenceCases(property_ref, block_ref, tenant_ref)
    return property_ref, block_ref, tenant_ref


def checkForIrregularTenantRefInDatabase(reference: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
    # Look for known irregular transaction refs which we know some tenants use
    if db_cursor:
        tenant_ref = get_single_value(db_cursor, SELECT_IRREGULAR_TRANSACTION_TENANT_REF_SQL, (reference,))
        if tenant_ref:
            return getPropertyBlockAndTenantRefs(tenant_ref)  # Parse tenant reference
        # else:
        #    transaction_ref_data = get_data(db_cursor, SELECT_ALL_IRREGULAR_TRANSACTION_REFS_SQL)
        #    for tenant_ref, transaction_ref_pattern in transaction_ref_data:
        #        pass
    return None, None, None


def getPropertyBlockAndTenantRefs(reference: str, db_cursor: sqlite3.Cursor | None = None) -> tuple[str | None, str | None, str | None]:
    # return getPropertyBlockAndTenantRefsImpl(reference, db_cursor)
    result = getPropertyBlockAndTenantRefs_strategy(reference, db_cursor)
    return result.to_tuple()


# def getPropertyBlockAndTenantRefsImpl(reference: str, db_cursor: sqlite3.Cursor | None = None) -> tuple[str | None, str | None, str | None]:
#     property_ref, block_ref, tenant_ref = None, None, None

#     if not isinstance(reference, str):
#         return None, None, None

#     # Try to match property, block and tenant
#     description = str(reference).strip()

#     # if "MEDHURST K M 10501001 RP4652285818999300" in description:
#     #     pass

#     # Check the database for irregular transaction references first
#     property_ref, block_ref, tenant_ref = checkForIrregularTenantRefInDatabase(description, db_cursor)
#     if property_ref and block_ref and tenant_ref:
#         return property_ref, block_ref, tenant_ref

#     # Then check various regular expression rules
#     match = re.search(PBT_REGEX, description)
#     if match:
#         property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
#         # if db_cursor and not checkTenantExists(db_cursor, tenant_ref):
#         #    return None, None, None
#     else:
#         match = re.search(PBT_REGEX_FWD_SLASHES, description)
#         if match:
#             property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
#             if db_cursor and not doubleCheckTenantRef(db_cursor, tenant_ref, reference):
#                 return None, None, None
#         else:
#             match = re.search(PBT_REGEX2, description)  # Match tenant with spaces between hyphens
#             if match:
#                 property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
#                 if db_cursor and not doubleCheckTenantRef(db_cursor, tenant_ref, reference):
#                     return None, None, None
#             else:
#                 match = re.search(PBT_REGEX3, description)  # Match tenant with 2 digits
#                 if match:
#                     property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
#                     if db_cursor and not doubleCheckTenantRef(db_cursor, tenant_ref, reference):
#                         tenant_ref = f"{match.group(1)}-{match.group(2)}-0{match.group(3)}"
#                         if not doubleCheckTenantRef(db_cursor, tenant_ref, reference):
#                             return None, None, None
#                 else:
#                     match = re.search(PBT_REGEX4, description)  # Match property with 2 digits
#                     if match:
#                         property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
#                         if db_cursor and not checkTenantExists(db_cursor, tenant_ref):
#                             property_ref = f"0{match.group(1)}"
#                             block_ref = f"{property_ref}-{match.group(2)}"
#                             tenant_ref = f"{block_ref}-{match.group(3)}"
#                             if not checkTenantExists(db_cursor, tenant_ref):
#                                 return None, None, None
#                     else:
#                         # Try to match property, block and tenant special cases
#                         match = re.search(PBT_REGEX_SPECIAL_CASES, description)
#                         if match:
#                             property_ref = match.group(1)
#                             block_ref = f"{match.group(1)}-{match.group(2)}"
#                             tenant_ref = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
#                             if db_cursor:
#                                 tenant_ref = removeDCReferencePostfix(tenant_ref) or tenant_ref
#                                 if tenant_ref and not doubleCheckTenantRef(db_cursor, tenant_ref, reference):
#                                     if property_ref and block_ref:
#                                         property_ref, block_ref, tenant_ref = correctKnownCommonErrors(property_ref, block_ref, tenant_ref)
#                                     if tenant_ref and not doubleCheckTenantRef(db_cursor, tenant_ref, reference):
#                                         return None, None, None
#                             elif not (
#                                 (
#                                     property_ref
#                                     in [
#                                         "093",
#                                         "094",
#                                         "095",
#                                         "096",
#                                         "099",
#                                         "124",
#                                         "132",
#                                         "133",
#                                         "134",
#                                     ]
#                                 )
#                                 or (property_ref in ["020", "022", "039", "053", "064"] and match.group(3)[-1] != "Z")
#                             ):
#                                 return None, None, None
#                         else:
#                             # Match property and block only
#                             match = re.search(PB_REGEX, description)
#                             if match:
#                                 property_ref = match.group(1)
#                                 block_ref = f"{match.group(1)}-{match.group(2)}"
#                             else:
#                                 # Match property and tenant only
#                                 # Prevent this case from matching for now, or move to the end of the match blocks
#                                 match = None  # Disabled: re.search(PT_REGEX, description)
#                                 if match:
#                                     pass
#                                     # property_ref = match.group(1)
#                                     # tenant_ref = match.group(2)  # Non-unique tenant ref, may be useful
#                                     # block_ref = '01'   # Null block indicates that the tenant and block can't be matched uniquely
#                                 else:
#                                     # Match without hyphens, or with no terminating space.
#                                     # These cases can only come from parsed transaction references.
#                                     # in which case we can double check that the data exists in and matches the database.
#                                     match = (
#                                         re.search(PBT_REGEX_NO_HYPHENS, description)
#                                         or re.search(
#                                             PBT_REGEX_NO_HYPHENS_SPECIAL_CASES,
#                                             description,
#                                         )
#                                         or re.search(PBT_REGEX_NO_TERMINATING_SPACE, description)
#                                         or re.search(PBT_REGEX_NO_BEGINNING_SPACE, description)
#                                     )
#                                     if match:
#                                         property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
#                                         if db_cursor and tenant_ref and not doubleCheckTenantRef(db_cursor, tenant_ref, reference):
#                                             if property_ref and block_ref:
#                                                 property_ref, block_ref, tenant_ref = correctKnownCommonErrors(property_ref, block_ref, tenant_ref)
#                                             if tenant_ref and not doubleCheckTenantRef(db_cursor, tenant_ref, reference):
#                                                 return None, None, None
#                                     # else:
#                                     #    # Match property reference only
#                                     #    match = re.search(P_REGEX, description)
#                                     #    if match:
#                                     #        property_ref = match.group(1)
#                                     #    else:
#                                     #        return None, None, None
#     return postProcessPropertyBlockTenantRefs(property_ref, block_ref, tenant_ref)


def getTenantID(csr: sqlite3.Cursor, tenant_ref: str) -> None:
    csr.execute(SELECT_TENANT_ID_SQL, (tenant_ref))


# Helper function to get text from an XML element and ensure it is not None
def get_element_text(parent_element: et.Element, child_element_name: str) -> str:
    child_element = parent_element.find(child_element_name)
    if child_element is None or child_element.text is None:
        raise ValueError(f"Missing or empty field: {child_element_name}")
    return child_element.text


def _prepare_bos_transaction_xml(transactions_xml_file: str) -> et.Element:
    """Read and prepare Bank of Scotland transaction XML file for parsing."""
    with open_file(transactions_xml_file) as f:
        xml = f.read()
        if type(xml) is bytes:
            xml = str(xml, "utf-8")
        xml = xml.replace("\n", "")
        schema = "PreviousDayTransactionExtract"
        xsd = f"https://isite.bankofscotland.co.uk/Schemas/{schema}.xsd"
        xml = re.sub(
            rf"""<({schema})\s+(xmlns=(?:'|")){xsd}(?:'|")\s*>""",
            r"<\1>",
            xml,
        )
    return et.fromstring(xml)


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


def importBankOfScotlandTransactionsXMLFile(db_conn: sqlite3.Connection, transactions_xml_file: str) -> tuple[list[list[Any]], list[list[Any]]]:
    """Import Bank of Scotland transactions from XML file into database.

    Returns:
        tuple: (errors_list, duplicate_transactions) - Lists of problematic transactions
    """
    errors_list = []
    duplicate_transactions = []
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

            # Parse the description field to determine the property, block and tenant
            property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefs(transaction_data["description"], csr)

            if tenant_ref and property_ref and block_ref:
                refs = TransactionReferences(property_ref, block_ref, tenant_ref)
                was_added, is_duplicate = _process_valid_transaction(csr, transaction_data, refs)

                if was_added:
                    num_transactions_added_to_db += 1
                elif is_duplicate:
                    duplicate_transactions.append(_create_duplicate_record(transaction_data, tenant_ref))
                else:
                    # Tenant not found in database
                    num_import_errors += 1
                    error_msg = f"Cannot find tenant with reference '{tenant_ref}'"
                    logger.debug(
                        f"{error_msg}. Ignoring transaction {(transaction_data['pay_date'], transaction_data['sort_code'], transaction_data['account_number'], transaction_data['transaction_type'], transaction_data['amount'], transaction_data['description'])}"
                    )
                    errors_list.append(_create_error_record(transaction_data, error_msg))
            else:
                # Cannot determine tenant from description
                num_import_errors += 1
                error_msg = "Cannot determine tenant from description"
                logger.debug(
                    f"{error_msg} '{transaction_data['description']}'. Ignoring transaction {(transaction_data['pay_date'], transaction_data['sort_code'], transaction_data['account_number'], transaction_data['transaction_type'], transaction_data['amount'], transaction_data['description'])}"
                )
                errors_list.append(_create_error_record(transaction_data, error_msg))

        csr.execute("end")
        db_conn.commit()

        if num_import_errors:
            logger.info(
                f"Unable to import {num_import_errors} transactions into the database. "
                f"See the Data_Import_Issues Excel file for details. Add tenant references to "
                f"{get_config()['INPUTS']['IRREGULAR_TRANSACTION_REFS_FILE']} and run import again."
            )
        logger.info(f"{num_transactions_added_to_db} Bank Of Scotland transactions added to the database.")
        return errors_list, duplicate_transactions

    except (db_conn.Error, Exception) as error:
        _handle_transaction_processing_error(csr, error, transaction_data, tenant_id)
        return [], []


def _prepare_bos_xml(balances_xml_file: str) -> et.Element:
    """Read and clean Bank of Scotland XML file, returning parsed tree."""
    with open_file(balances_xml_file) as f:
        xml = f.read()
        if isinstance(xml, bytes):
            xml = str(xml, "utf-8")
        xml = xml.replace("\n", "")

        # Remove schema namespaces to simplify XML parsing
        for schema in ["BalanceDetailedReport", "EndOfDayBalanceExtract"]:
            xsd = f"https://isite.bankofscotland.co.uk/Schemas/{schema}.xsd"
            xml = re.sub(
                rf"""<({schema})\s+(xmlns=(?:'|")){xsd}(?:'|")\s*>""",
                r"<\1>",
                xml,
            )

    return et.fromstring(xml)


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
    client_ref_element = balance_element.find("ClientRef")
    client_ref = client_ref_element.text if client_ref_element is not None else None

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
            balance_data["current_balance"],
            balance_data["available_balance"],
            at_date,
            account_id,
        ),
    )

    logger.debug(
        f"\tAdding bank balance {(sort_code, account_number, balance_data['account_type'], balance_data['client_ref'], balance_data['account_name'], at_date, balance_data['current_balance'], balance_data['available_balance'])}"
    )
    return True


def importBankOfScotlandBalancesXMLFile(db_conn: sqlite3.Connection, balances_xml_file: str) -> None:
    """Import Bank of Scotland account balances from XML file into database."""
    tree = _prepare_bos_xml(balances_xml_file)
    num_balances_added_to_db = 0

    # Variables for error handling context
    sort_code = account_number = account_type = client_ref = None
    account_name = at_date = current_balance = available_balance = None

    try:
        csr = db_conn.cursor()
        csr.execute("begin")

        for reporting_day in tree.iter("ReportingDay"):
            at_date = get_element_text(reporting_day, "Date")
            at_date = parser.parse(at_date, dayfirst=True).strftime("%Y-%m-%d")

            for balance in reporting_day.iter("BalanceRecord"):
                balance_data = _extract_balance_data(balance)

                # Update error context variables
                sort_code = balance_data["sort_code"]
                account_number = balance_data["account_number"]
                account_type = balance_data["account_type"]
                client_ref = balance_data["client_ref"]
                account_name = balance_data["account_name"]
                current_balance = balance_data["current_balance"]
                available_balance = balance_data["available_balance"]

                if _process_balance_record(csr, balance_data, at_date):
                    num_balances_added_to_db += 1

        csr.execute("end")
        db_conn.commit()
        logger.info(f"{num_balances_added_to_db} Bank Of Scotland account balances added to the database.")

    except db_conn.Error as err:
        logger.error(str(err))
        logger.error(f"The data which caused the failure is: {(sort_code, account_number, account_type, client_ref, account_name, at_date, current_balance, available_balance)}")
        logger.error("No Bank Of Scotland account balances have been added to the database.")
        logger.exception(err)
        csr.execute("rollback")
    except Exception as ex:
        logger.error(str(ex))
        logger.error(f"The data which caused the failure is: {(sort_code, account_number, account_type, client_ref, account_name, at_date, current_balance, available_balance)}")
        logger.error("No Bank Of Scotland account balances have been added to the database.")
        logger.exception(ex)
        csr.execute("rollback")


def _read_properties_df(properties_xls_file: str) -> pd.DataFrame:
    """Reads properties data from an Excel file into a DataFrame."""
    properties_df = pd.read_excel(properties_xls_file)
    properties_df.fillna("", inplace=True)
    return properties_df


def _is_valid_reference(reference: str) -> bool:
    """Checks if a reference is valid for processing."""
    if not reference or reference.startswith("9") or "Y" in reference.upper() or "Z" in reference.upper():
        return False
    return True


def _process_property(csr: sqlite3.Cursor, property_ref: str) -> tuple[int, int]:
    """Processes a property, adding it to the DB if it doesn't exist."""
    executor = DatabaseCommandExecutor(csr, logger)
    property_id = get_id_from_ref(csr, "Properties", "property", property_ref)
    if not property_id:
        command = InsertPropertyCommand(property_ref, INSERT_PROPERTY_SQL)
        new_id = executor.execute(command)
        return new_id, 1
    assert property_id is not None  # For mypy
    return property_id, 0


def _process_block(csr: sqlite3.Cursor, block_ref: str, property_id: int) -> tuple[int, int]:
    """Processes a block, adding it to the DB if it doesn't exist."""
    executor = DatabaseCommandExecutor(csr, logger)
    block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)
    if not block_id:
        block_type = "P" if block_ref and block_ref.endswith("00") else "B"
        command = InsertBlockCommand(block_ref, block_type, property_id, INSERT_BLOCK_SQL)
        new_id = executor.execute(command)
        return new_id, 1
    assert block_id is not None  # For mypy
    return block_id, 0


def _process_tenant(csr: sqlite3.Cursor, tenant_ref: str, tenant_name: str, block_id: int) -> int:
    """Processes a tenant, adding or updating it in the DB."""
    executor = DatabaseCommandExecutor(csr, logger)
    tenant_id = get_id_from_ref(csr, "Tenants", "tenant", tenant_ref)
    if tenant_ref and not tenant_id:
        command = InsertTenantCommand(tenant_ref, tenant_name, block_id, INSERT_TENANT_SQL)
        executor.execute(command)
        return 1
    elif tenant_id:
        old_tenant_name = get_single_value(csr, SELECT_TENANT_NAME_BY_ID_SQL, (tenant_id,))
        if tenant_name and tenant_name != old_tenant_name:
            command = UpdateTenantNameCommand(tenant_name, tenant_id, tenant_ref, UPDATE_TENANT_NAME_SQL)
            executor.execute(command)
    return 0


def importPropertiesFile(db_conn: sqlite3.Connection, properties_xls_file: str) -> None:
    """Import properties data from Excel file into database."""
    properties_df = _read_properties_df(properties_xls_file)

    num_properties_added_to_db = 0
    num_blocks_added_to_db = 0
    num_tenants_added_to_db = 0
    current_data = {}

    with database_transaction(db_conn, logger, "importing properties file") as csr:
        for index, row in properties_df.iterrows():
            reference = row["Reference"]
            tenant_name = row["Name"]
            current_data = {"reference": reference, "tenant_name": tenant_name}

            if not _is_valid_reference(reference):
                continue

            property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefs(reference)
            if not all((property_ref, block_ref, tenant_ref)):
                logger.warning(f"\tUnable to parse tenant reference {reference}, will not add to the database.")
                continue

            current_data.update({"property_ref": property_ref, "block_ref": block_ref, "tenant_ref": tenant_ref})

            # Type assertions for mypy since we know they're not None after the all() check
            assert property_ref is not None
            assert block_ref is not None
            assert tenant_ref is not None

            try:
                prop_id, props_added = _process_property(csr, property_ref)
                num_properties_added_to_db += props_added

                blk_id, blocks_added = _process_block(csr, block_ref, prop_id)
                num_blocks_added_to_db += blocks_added

                tenants_added = _process_tenant(csr, tenant_ref, tenant_name, blk_id)
                num_tenants_added_to_db += tenants_added
            except Exception:
                logger.error(f"Failed to process record: {current_data}")
                raise

    logger.info(f"{num_properties_added_to_db} properties added to the database.")
    logger.info(f"{num_blocks_added_to_db} blocks added to the database.")
    logger.info(f"{num_tenants_added_to_db} tenants added to the database.")


def importEstatesFile(db_conn: sqlite3.Connection, estates_xls_file: str) -> None:
    # Read Excel spreadsheet into dataframe
    estates_df = pd.read_excel(estates_xls_file, dtype=str)
    estates_df.fillna("", inplace=True)

    num_estates_added_to_db = 0
    num_blocks_added_to_db = 0

    # Import into DB
    try:
        csr = db_conn.cursor()
        csr.execute("begin")
        for index, row in estates_df.iterrows():
            reference = row["Reference"]
            estate_name = row["Name"]
            # If the property reference begins with a '9' or contains a 'Y' or 'Z',then ignore this data
            if reference is None or reference[0] == "9" or "Y" in reference.upper() or "Z" in reference.upper():
                continue

            # Update property to be an estate, if the property name has not already been set
            property_id = get_id_from_ref(csr, "Properties", "property", reference)
            if property_id:
                if get_id(csr, SELECT_PROPERTY_ID_FROM_REF_SQL, (reference,)) == property_id:
                    csr.execute(UPDATE_PROPERTY_DETAILS_SQL, (estate_name, property_id))
                    num_estates_added_to_db += 1

                # Add a '00' block for the estate service charges, if not already present
                block_ref = reference + "-00"
                block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)
                if not block_id:
                    csr.execute(INSERT_BLOCK_SQL2, (block_ref, estate_name, "P", property_id))
                    num_blocks_added_to_db += 1
        csr.execute("end")
        db_conn.commit()
        logger.info(f"{num_estates_added_to_db} estates added to the database.")
        logger.info(f"{num_blocks_added_to_db} estate blocks added to the database.")
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error("The data which caused the failure is: " + str((reference, estate_name)))
        logger.error("No estates or estate blocks have been added to the database")
        csr.execute("rollback")
        raise
    except Exception as ex:
        logger.error(str(ex))
        logger.error("The data which caused the failure is: " + str((reference, estate_name)))
        logger.error("No estates or estate blocks have been added to the database.")
        csr.execute("rollback")
        raise


def addPropertyToDB(db_conn: sqlite3.Connection, property_ref: str, rethrow_exception: bool = False) -> int | None:
    property_id = None
    try:
        csr = db_conn.cursor()
        csr.execute("begin")

        if property_ref:
            property_id = get_id_from_ref(csr, "Properties", "property", property_ref)
            if not property_id:
                csr.execute(INSERT_PROPERTY_SQL, (property_ref,))
                logger.debug(f"\tAdding property {property_ref}")
                property_id = get_last_insert_id(csr, "Properties")

        csr.execute("end")
        db_conn.commit()
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error(f"The data which caused the failure is: {property_ref}")
        logger.error(f"Unable to add property {property_ref} to the database")
        logger.exception(err)
        csr.execute("rollback")
        if rethrow_exception:
            raise
    except Exception as ex:
        logger.error(str(ex))
        logger.exception(ex)
        logger.error(f"Unable to add property {property_ref} to the database")
        csr.execute("rollback")
        if rethrow_exception:
            raise
    return property_id


def addBlockToDB(
    db_conn: sqlite3.Connection,
    property_ref: str,
    block_ref: str,
    rethrow_exception: bool = False,
) -> int | None:
    block_id = None
    try:
        csr = db_conn.cursor()
        csr.execute("begin")

        if block_ref:
            block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)
            if not block_id and property_ref:
                if block_ref.endswith("00"):
                    block_type = "P"
                else:
                    block_type = "B"
                property_id = get_id_from_ref(csr, "Properties", "property", property_ref)
                csr.execute(INSERT_BLOCK_SQL, (block_ref, block_type, property_id))
                logger.debug(f"\tAdding block {block_ref}")
                block_id = get_last_insert_id(csr, "Blocks")

        csr.execute("end")
        db_conn.commit()
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error("The data which caused the failure is: " + str((property_ref, block_ref)))
        logger.error("Unable to add property or block to the database")
        logger.exception(err)
        csr.execute("rollback")
        if rethrow_exception:
            raise
    except Exception as ex:
        logger.error(str(ex))
        logger.exception(ex)
        logger.error("The data which caused the failure is: " + str((property_ref, block_ref)))
        logger.error("Unable to add property or block to the database")
        csr.execute("rollback")
        if rethrow_exception:
            raise
    return block_id


def addTenantToDB(
    db_conn: sqlite3.Connection,
    block_ref: str,
    tenant_ref: str,
    tenant_name: str,
    rethrow_exception: bool = False,
) -> int | None:
    tenant_id = None
    try:
        csr = db_conn.cursor()
        csr.execute("begin")

        if tenant_ref:
            tenant_id = get_id_from_ref(csr, "Tenants", "tenant", tenant_ref)
            if not tenant_id:
                block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)
                if block_id:
                    csr.execute(INSERT_TENANT_SQL, (tenant_ref, tenant_name, block_id))
                    logger.debug(f"\tAdding tenant {tenant_ref}")
                    tenant_id = get_last_insert_id(csr, "Tenants")

        csr.execute("end")
        db_conn.commit()
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error("The data which caused the failure is: " + str((block_ref, tenant_ref)))
        logger.error("Unable to add tenant to the database")
        logger.exception(err)
        csr.execute("rollback")
        if rethrow_exception:
            raise
    except Exception as ex:
        logger.error(str(ex))
        logger.exception(ex)
        logger.error("The data which caused the failure is: " + str((block_ref, tenant_ref)))
        logger.error("Unable to add tenant to the database")
        csr.execute("rollback")
        if rethrow_exception:
            raise
    return tenant_id


# def importBlockBankAccountNumbers(db_conn: sqlite3.Connection, bos_reconciliations_file: str) -> None:
#     # Read Excel spreadsheet into dataframe
#     bank_accounts_df = pd.read_excel(bos_reconciliations_file, "Accounts", dtype=str)

#     num_bank_accounts_added_to_db = 0

#     try:
#         csr = db_conn.cursor()
#         csr.execute("begin")
#         for index, row in bank_accounts_df.iterrows():
#             block_ref = row["Reference"]
#             account_number = row["Account Number"]

#             block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)
#             if block_id:
#                 id = get_id(csr, SELECT_BANK_ACCOUNT_SQL, (block_id,))
#                 if id:
#                     csr.execute(UPDATE_BLOCK_ACCOUNT_NUMBER_SQL, (account_number, block_id))
#                     logger.debug(f"\tAdding bank account number {account_number} for block {block_id}")
#                     num_bank_accounts_added_to_db += 1
#         csr.execute("end")
#         db_conn.commit()
#         logger.info(f"{num_bank_accounts_added_to_db} bank account numbers added to the database.")
#     except db_conn.Error as err:
#         logger.error(str(err))
#         logger.error("The data which caused the failure is: " + str((block_ref, account_number)))
#         logger.error("No bank account numbers have been added to the database")
#         logger.exception(err)
#         csr.execute("rollback")
#     except Exception as ex:
#         logger.error(str(ex))
#         logger.error("The data which caused the failure is: " + str((block_ref, account_number)))
#         logger.error("No bank account numbers have been added to the database.")
#         logger.exception(ex)
#         csr.execute("rollback")
#         # charges = {}


def importBankAccounts(db_conn: sqlite3.Connection, bank_accounts_file: str) -> None:
    # Read Excel spreadsheet into dataframe
    bank_accounts_df = pd.read_excel(bank_accounts_file, "Accounts", dtype=str)
    bank_accounts_df.replace("nan", "", inplace=True)
    bank_accounts_df.fillna("", inplace=True)

    num_bank_accounts_added_to_db = 0

    try:
        csr = db_conn.cursor()
        csr.execute("begin")
        for index, row in bank_accounts_df.iterrows():
            reference = row["Reference"]
            sort_code = row["Sort Code"]
            account_number = row["Account Number"]
            account_type = row["Account Type"]
            property_or_block = row["Property Or Block"]
            client_ref = row["Client Reference"]
            account_name = row["Account Name"]

            property_block = None
            if property_or_block.upper() == "PROPERTY" or property_or_block.upper() == "P":
                property_block = "P"
            elif property_or_block.upper() == "BLOCK" or property_or_block.upper() == "B":
                property_block = "B"
            elif property_or_block == "" or property_or_block is None:
                property_block = ""
            else:
                raise ValueError(f"Unknown property/block type {property_or_block} for bank account ({sort_code}, {account_number})")

            _, block_ref, _ = getPropertyBlockAndTenantRefs(reference)

            if property_block == "P" and block_ref is not None and not block_ref.endswith("00"):
                property_ref, _, _ = getPropertyBlockAndTenantRefs(reference)
                suggested_ref = f"{property_ref}-00" if property_ref else f"{reference.split('-')[0]}-00"
                raise ValueError(
                    f"Invalid block reference '{reference}' for estate account. "
                    f"Estate accounts (Property Or Block = 'Property') must use estate block references ending in '-00'. "
                    f"Either change the reference to '{suggested_ref}' or set 'Property Or Block' to 'Block'. "
                    f"Bank account: {sort_code}-{account_number}"
                )

            block_id = get_id_from_ref(csr, "Blocks", "block", reference)
            # if block_id is None:
            #     property_ref, _, _ = getPropertyBlockAndTenantRefs(reference)
            #     logger.warning(
            #         f"Block reference '{reference}' does not exist in database for bank account {sort_code}-{account_number}. "
            #         f"Ensure property '{property_ref}' exists in the Properties table and block {reference} exists in the blocks table. "
            #         f"Skipping this bank account as it is not required."
            #     )
            #     continue  # Skip this account rather than failing

            _id = get_id(csr, SELECT_BANK_ACCOUNT_SQL1, (sort_code, account_number))
            if sort_code and account_number and not _id:
                csr.execute(
                    INSERT_BANK_ACCOUNT_SQL,
                    (
                        sort_code,
                        account_number,
                        account_type,
                        property_block,
                        client_ref,
                        account_name,
                        block_id,
                    ),
                )
                logger.debug(f"\tAdding bank account ({sort_code}, {account_number}) for property {reference}")
                num_bank_accounts_added_to_db += 1

        csr.execute("end")
        db_conn.commit()
        logger.info(f"{num_bank_accounts_added_to_db} bank accounts added to the database.")
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error("The data which caused the failure is: " + str((reference, sort_code, account_number, account_type, property_or_block)))
        logger.error("No bank accounts have been added to the database")
        csr.execute("rollback")
        raise
    except Exception as ex:
        logger.error(str(ex))
        logger.error("The data which caused the failure is: " + str((reference, sort_code, account_number, account_type, property_or_block)))
        logger.error("No bank accounts have been added to the database.")
        csr.execute("rollback")
        raise


def importIrregularTransactionReferences(db_conn: sqlite3.Connection, anomalous_refs_file: str) -> None:
    # Read Excel spreadsheet into dataframe
    anomalous_refs_df = pd.read_excel(anomalous_refs_file, "Sheet1", dtype=str)
    anomalous_refs_df.replace("nan", "", inplace=True)
    anomalous_refs_df.fillna("", inplace=True)

    num_anomalous_refs_added_to_db = 0
    tenant_reference = ""

    try:
        csr = db_conn.cursor()
        csr.execute("begin")
        for index, row in anomalous_refs_df.iterrows():
            tenant_reference = row["Tenant Reference"].strip()
            payment_reference_pattern = row["Payment Reference Pattern"].strip()

            _id = get_id(
                csr,
                SELECT_IRREGULAR_TRANSACTION_REF_ID_SQL,
                (tenant_reference, payment_reference_pattern),
            )
            if tenant_reference and not _id:
                csr.execute(
                    INSERT_IRREGULAR_TRANSACTION_REF_SQL,
                    (tenant_reference, payment_reference_pattern),
                )
                logger.debug(f"\tAdding irregular transaction reference pattern ({tenant_reference}) for tenant {payment_reference_pattern}")
                num_anomalous_refs_added_to_db += 1

        csr.execute("end")
        db_conn.commit()
        logger.info(f"{num_anomalous_refs_added_to_db} irregular transaction reference patterns added to the database.")
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error("No irregular transaction reference patterns have been added to the database")
        logger.error("The data which caused the failure is: " + str((tenant_reference, payment_reference_pattern)))
        csr.execute("rollback")
        raise
    except Exception as ex:
        logger.error(str(ex))
        logger.error("No irregular transaction reference patterns have been added to the database.")
        logger.error("The data which caused the failure is: " + str((tenant_reference, payment_reference_pattern)))
        csr.execute("rollback")
        raise


def calculateSCFund(auth_creditors: float, available_funds: float, property_ref: str, block_ref: str) -> float:
    # TODO: This should be encoded in a user-supplied rules spreadsheet for generality
    if property_ref == "035":
        return available_funds
    else:
        return auth_creditors + available_funds


def _validate_qube_spreadsheet(workbook_sheet) -> None:
    """Validate that the spreadsheet is a valid Qube balances report."""
    A1_cell_value = workbook_sheet.cell(1, 1).value
    B1_cell_value = workbook_sheet.cell(1, 2).value
    produced_date_cell_value = workbook_sheet.cell(3, 1).value

    if not isinstance(produced_date_cell_value, str):
        raise ValueError(f"The produced date cell value is not a string: {produced_date_cell_value}")

    cell_values_actual = [workbook_sheet.cell(5, i + 1).value for i in range(0, 4)]
    cell_values_expected = [
        "Property / Fund",
        "Bank",
        "Excluded VAT",
        AUTH_CREDITORS,
        AVAILABLE_FUNDS,
    ]

    is_valid_header = A1_cell_value == "Property Management" and B1_cell_value == "Funds Available in Property Funds"
    is_valid_columns = all(actual == expected for actual, expected in zip(cell_values_actual, cell_values_expected))

    if not (is_valid_header and is_valid_columns):
        logger.error("The spreadsheet does not look like a Qube balances report.")


def _extract_qube_date(workbook_sheet) -> str:
    """Extract and parse the date from the Qube report."""
    produced_date_cell_value = workbook_sheet.cell(3, 1).value
    at_date_str = " ".join(produced_date_cell_value.split()[-3:])
    return (parser.parse(at_date_str, dayfirst=True) - BUSINESS_DAY).strftime("%Y-%m-%d")


def _prepare_qube_dataframe(qube_eod_balances_xls_file: str) -> pd.DataFrame:
    """Read and prepare the Qube balances dataframe."""
    qube_eod_balances_df = pd.read_excel(qube_eod_balances_xls_file, usecols="B:G", skiprows=4)

    # Fix column names
    qube_eod_balances_df.columns = [  # type: ignore[assignment]
        "PropertyCode / Fund",
        "PropertyName / Category",
        "Bank",
        "Excluded VAT",
        AUTH_CREDITORS,
        AVAILABLE_FUNDS,
    ]

    # Clean data
    qube_eod_balances_df.dropna(how="all", inplace=True)
    qube_eod_balances_df.fillna(0, inplace=True)

    return qube_eod_balances_df


def _diagnose_missing_property(csr, property_ref: str, block_ref: str) -> str:
    """Provide diagnostic information for missing property."""
    # Check if property exists at all
    property_count = get_id(csr, "SELECT COUNT(*) FROM Properties WHERE property_ref = ?", (property_ref,))

    if property_count == 0:
        return (
            f"Property '{property_ref}' does not exist in the Properties table. "
            f"Check if property '{property_ref}' is included in the Tenants.xlsx file "
            f"or add it to the Estates.xlsx file if it's an estate."
        )
    else:
        return f"Property '{property_ref}' exists but block '{block_ref}' was not found. This may indicate a block creation issue."


def _ensure_block_exists(csr, property_ref: str, block_ref: str) -> int | None:
    """Ensure the block exists in the database and return its ID."""
    property_id = get_id_from_ref(csr, "Properties", "property", property_ref)
    if not property_id:
        return None

    block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)
    if not block_id:
        block_type = "P" if block_ref and block_ref.endswith("00") else "B"
        csr.execute(INSERT_BLOCK_SQL, (block_ref, block_type, property_id))
        logger.debug(f"\tAdding block {block_ref}")
        block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)

    return block_id


def _update_block_name_if_needed(csr, block_ref: str, block_name: str, block_id: int) -> None:
    """Update block name if it doesn't exist."""
    if not get_id(csr, SELECT_BLOCK_NAME_SQL, (block_ref,)):
        csr.execute(UPDATE_BLOCK_NAME_SQL, (block_name, block_id))
        logger.debug(f"\tAdding block name {block_name} for block reference {block_ref}")


def _add_charge_if_not_exists(csr, charge: ChargeData) -> bool:
    """Add a charge to the database if it doesn't already exist. Returns True if added."""
    executor = DatabaseCommandExecutor(csr, logger)
    charges_id = get_id(csr, SELECT_CHARGES_SQL, (charge.fund_id, charge.category_id, charge.type_id, charge.block_id, charge.at_date))
    if not charges_id:
        command = InsertChargeCommand(charge, INSERT_CHARGES_SQL)
        executor.execute(command)
        return True
    return False


def _process_fund_category_data(
    csr, property_code_or_fund: str, property_ref: str, block_ref: str, block_name: str, fund: str, category: str, auth_creditors: float, available_funds: float, at_date: str, type_ids: dict
) -> int:
    """Process fund/category data and add charges to database. Returns number of charges added."""
    num_charges_added = 0

    # Ensure block exists
    block_id = _ensure_block_exists(csr, property_ref, block_ref)
    if not block_id:
        diagnostic_info = _diagnose_missing_property(csr, property_ref, block_ref)
        logger.warning(f"Cannot process Qube balances for block '{block_ref}'. {diagnostic_info} Skipping {block_ref} charges.")
        return 0

    # Update block name if needed
    _update_block_name_if_needed(csr, block_ref, block_name, block_id)

    # Get fund and category IDs
    fund_id = get_id_from_key_table(csr, "fund", fund)
    category_id = get_id_from_key_table(csr, "category", category)

    # Add available funds charge
    available_charge = ChargeData(fund_id, category_id, type_ids["available_funds"], at_date, available_funds, block_id)
    if _add_charge_if_not_exists(csr, available_charge):
        logger.debug(f"\tAdding charge {(fund, category, AVAILABLE_FUNDS, at_date, block_ref, available_funds)}")
        num_charges_added += 1

    # Add auth creditors and SC fund charges for specific fund types
    if property_code_or_fund in ["Service Charge", "Tenant Recharge"]:
        auth_charge = ChargeData(fund_id, category_id, type_ids["auth_creditors"], at_date, auth_creditors, block_id)
        if _add_charge_if_not_exists(csr, auth_charge):
            logger.debug(f"\tAdding charge for {(fund, category, AUTH_CREDITORS, at_date, block_ref, auth_creditors)}")
            num_charges_added += 1

        sc_fund = calculateSCFund(auth_creditors, available_funds, property_ref, block_ref)
        sc_charge = ChargeData(fund_id, category_id, type_ids["sc_fund"], at_date, sc_fund, block_id)
        if _add_charge_if_not_exists(csr, sc_charge):
            logger.debug(f"\tAdding charge for {(fund, category, SC_FUND, at_date, block_ref, sc_fund)}")
            num_charges_added += 1

    return num_charges_added


def importQubeEndOfDayBalancesFile(db_conn: sqlite3.Connection, qube_eod_balances_xls_file: str) -> None:
    """Import Qube End of Day balances from Excel file into database."""
    num_charges_added_to_db = 0

    # Load and validate spreadsheet
    qube_eod_balances_workbook = load_workbook(qube_eod_balances_xls_file, read_only=True, data_only=True)
    qube_eod_balances_workbook_sheet = qube_eod_balances_workbook.worksheets[0]

    _validate_qube_spreadsheet(qube_eod_balances_workbook_sheet)
    at_date = _extract_qube_date(qube_eod_balances_workbook_sheet)
    qube_eod_balances_df = _prepare_qube_dataframe(qube_eod_balances_xls_file)

    try:
        csr = db_conn.cursor()
        csr.execute("begin")

        # Get type IDs once for efficiency
        type_ids = {
            "auth_creditors": get_id_from_key_table(csr, "type", AUTH_CREDITORS),
            "available_funds": get_id_from_key_table(csr, "type", AVAILABLE_FUNDS),
            "sc_fund": get_id_from_key_table(csr, "type", SC_FUND),
        }

        # Process each row in the dataframe
        found_property = False
        property_ref = block_ref = block_name = None
        block_ref = fund = category = auth_creditors = block_id = None  # For error handling

        for i in range(qube_eod_balances_df.shape[0]):
            property_code_or_fund = qube_eod_balances_df.iloc[i]["PropertyCode / Fund"]
            property_name_or_category = qube_eod_balances_df.iloc[i]["PropertyName / Category"]

            # Check if this is a property/block reference
            try_property_ref, try_block_ref, _ = getPropertyBlockAndTenantRefs(property_code_or_fund)

            if try_property_ref and try_block_ref:
                # Found a new property/block
                found_property = True
                property_ref = try_property_ref
                block_ref = try_block_ref
                block_name = property_name_or_category

            elif found_property and property_code_or_fund in ["Service Charge", "Rent", "Tenant Recharge", "Admin Fund", "Reserve"]:
                # Process fund/category data for current property/block
                fund = property_code_or_fund
                category = property_name_or_category
                auth_creditors = qube_eod_balances_df.iloc[i][AUTH_CREDITORS]
                available_funds = qube_eod_balances_df.iloc[i][AVAILABLE_FUNDS]

                # Skip if we don't have all required data
                if not all([property_ref, block_ref, block_name, fund, category]):
                    logger.warning(f"Missing required data: property_ref={property_ref}, block_ref={block_ref}, block_name={block_name}, fund={fund}, category={category}")
                    continue

                # Type assertions for mypy since we verified they're not None
                assert property_ref is not None
                assert block_ref is not None
                assert block_name is not None

                charges_added = _process_fund_category_data(csr, property_code_or_fund, property_ref, block_ref, block_name, fund, category, auth_creditors, available_funds, at_date, type_ids)
                num_charges_added_to_db += charges_added

            elif property_code_or_fund == "Property Totals":
                # Reset for next property
                found_property = False

        csr.execute("end")
        db_conn.commit()
        logger.info(f"{num_charges_added_to_db} charges added to the database.")

    except db_conn.Error as err:
        logger.error(str(err))
        logger.error("The data which caused the failure is: " + str((block_ref, fund, category, at_date, auth_creditors, block_id)))
        logger.error("No Qube balances have been added to the database.")
        logger.exception(err)
        csr.execute("rollback")
    except Exception as ex:
        logger.error(str(ex))
        logger.error("The data which caused the failure is: " + str((block_ref, fund, category, at_date, auth_creditors, block_id)))
        logger.error("No Qube balances have been added to the database.")
        logger.exception(ex)
        csr.execute("rollback")


def add_misc_data_to_db(db_conn: sqlite3.Connection) -> None:
    # Add account number and property name for some properties
    try:
        csr = db_conn.cursor()
        # csr.execute('begin')
        # csr.execute(UPDATE_PROPERTY_DETAILS_SQL, ('St Winefrides Estate', '020'))
        # csr.execute(UPDATE_PROPERTY_DETAILS_SQL, ('Sand Wharf Estate', '034'))
        # csr.execute(UPDATE_PROPERTY_DETAILS_SQL, ('Hensol Castle Park', '036'))
        # csr.execute(UPDATE_PROPERTY_DETAILS_SQL, ('Grangemoor Court', '064'))
        # csr.execute(UPDATE_PROPERTY_DETAILS_SQL, ('Farmleigh Estate', '074'))
        # csr.execute(UPDATE_PROPERTY_DETAILS_SQL, ('St Fagans Rise', '095'))
        # Add the 064-00 block as this is not yet present in the data
        # block_id = get_id_from_ref(csr, 'Blocks', 'block', '064-00')
        # if not block_id:
        #    property_id = get_id_from_ref(csr, 'Properties', 'property', '064')
        #    sql = "INSERT INTO Blocks (block_ref, block_name, type, property_id) VALUES (?, ?, ?, ?);"
        #    csr.execute(sql, ('064-00', 'Grangemoor Court', 'P', property_id))
        # csr.execute('end')
        # db_conn.commit()
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error("No miscellaneous data has been added to the database.")
        logger.exception(err)
        csr.execute("rollback")
    except Exception as ex:
        logger.error(str(ex))
        logger.error("No miscellaneous data has been added to the database.")
        logger.exception(ex)
        csr.execute("rollback")


def importAllData(db_conn: sqlite3.Connection) -> None:
    # Create a Pandas Excel writer using openpyxl as the engine.
    excel_log_file = get_wpp_excel_log_file(dt.date.today())
    logger.debug(f"Creating Excel spreadsheet report file {excel_log_file}")
    excel_writer = pd.ExcelWriter(excel_log_file, engine="openpyxl")

    config = get_config()
    inputs_config = config["INPUTS"]

    # Import iregular transaction references
    irregular_transaction_refs_file_pattern = os.path.join(get_wpp_static_input_dir(), f"{inputs_config['IRREGULAR_TRANSACTION_REFS_FILE']}")
    irregular_transaction_refs_file = getLatestMatchingFileName(irregular_transaction_refs_file_pattern)
    if irregular_transaction_refs_file:
        logger.info(f"Importing irregular transaction references from file {irregular_transaction_refs_file}")
        importIrregularTransactionReferences(db_conn, irregular_transaction_refs_file)
    else:
        logger.error(f"Cannot find irregular transaction references file matching {irregular_transaction_refs_file_pattern}")
    logger.info("")

    # Import tenants
    properties_file_pattern = os.path.join(get_wpp_static_input_dir(), inputs_config["PROPERTIES_FILE_PATTERN"])
    tenants_file_pattern = os.path.join(get_wpp_static_input_dir(), inputs_config["TENANTS_FILE_PATTERN"])
    properties_xls_file = getLatestMatchingFileName(properties_file_pattern) or getLatestMatchingFileName(tenants_file_pattern)
    if properties_xls_file:
        logger.info(f"Importing Properties from file {properties_xls_file}")
        importPropertiesFile(db_conn, properties_xls_file)
    else:
        logger.error(f"Cannot find Properties file matching {properties_file_pattern}")
    logger.info("")

    estates_file_pattern = os.path.join(get_wpp_static_input_dir(), inputs_config["ESTATES_FILE_PATTERN"])
    estates_xls_file = getLatestMatchingFileName(estates_file_pattern)
    if estates_xls_file:
        logger.info(f"Importing Estates from file {estates_xls_file}")
        importEstatesFile(db_conn, estates_xls_file)
    else:
        logger.error(f"Cannot find Estates file matching {estates_file_pattern}")
    logger.info("")

    qube_eod_balances_file_pattern = os.path.join(get_wpp_input_dir(), inputs_config["QUBE_EOD_BALANCES_PATTERN"])
    qube_eod_balances_files = getMatchingFileNames(qube_eod_balances_file_pattern)
    if qube_eod_balances_files:
        for qube_eod_balances_file in qube_eod_balances_files:
            logger.info(f"Importing Qube balances from file {qube_eod_balances_file}")
            importQubeEndOfDayBalancesFile(db_conn, qube_eod_balances_file)
    else:
        logger.error(f"Cannot find Qube EOD Balances file matching {qube_eod_balances_file_pattern}")
    logger.info("")

    accounts_file_pattern = os.path.join(get_wpp_static_input_dir(), inputs_config["BANK_ACCOUNTS_PATTERN"])
    accounts_file = getLatestMatchingFileName(accounts_file_pattern)
    if accounts_file:
        logger.info(f"Importing bank accounts from file {accounts_file}")
        importBankAccounts(db_conn, accounts_file)
    else:
        logger.error(f"ERROR: Cannot find account numbers file matching {accounts_file_pattern}")
    logger.info("")

    bos_statement_file_pattern = [
        os.path.join(get_wpp_input_dir(), f)
        for f in [
            "PreviousDayTransactionExtract_*.xml",
            "PreviousDayTransactionExtract_*.zip",
        ]
    ]
    bos_statement_xml_files = getMatchingFileNames(bos_statement_file_pattern)
    errors_list = []
    duplicate_transactions = []
    if bos_statement_xml_files:
        for bos_statement_xml_file in bos_statement_xml_files:
            logger.info(f"Importing Bank Account Transactions from file {bos_statement_xml_file}")
            errors, duplicates = importBankOfScotlandTransactionsXMLFile(db_conn, bos_statement_xml_file)
            errors_list.extend(errors)
            duplicate_transactions.extend(duplicates)
        errors_columns = [
            "Payment Date",
            "Sort Code",
            "Account Number",
            "Transaction Type",
            "Amount",
            "Description",
            "Reason",
        ]
        duplicates_columns = [
            "Payment Date",
            "Transaction Type",
            "Amount",
            "Tenant Reference",
            "Description",
        ]
        errors_df = pd.DataFrame(errors_list, columns=errors_columns)
        duplicates_df = pd.DataFrame(duplicate_transactions, columns=duplicates_columns)
        errors_df.to_excel(
            excel_writer,
            sheet_name="Unrecognised Transactions",
            index=False,
            float_format="%.2f",
        )
        duplicates_df.to_excel(
            excel_writer,
            sheet_name="Duplicate Transactions",
            index=False,
            float_format="%.2f",
        )
    else:
        logger.error(f"Cannot find bank account transactions file matching {bos_statement_file_pattern}")
    logger.info("")

    eod_balances_file_patterns = [
        os.path.join(get_wpp_input_dir(), f)
        for f in [
            "EOD BalancesReport_*.xml",
            "EndOfDayBalanceExtract_*.xml",
            "EndOfDayBalanceExtract_*.zip",
        ]
    ]
    eod_balances_xml_files = getMatchingFileNames(eod_balances_file_patterns)
    if eod_balances_xml_files:
        for eod_balances_xml_file in eod_balances_xml_files:
            logger.info(f"Importing Bank Account balances from file {eod_balances_xml_file}")
            importBankOfScotlandBalancesXMLFile(db_conn, eod_balances_xml_file)
    else:
        logger.error("Cannot find bank account balances file matching one of {}".format(",".join(eod_balances_file_patterns)))
    logger.info("")

    add_misc_data_to_db(db_conn)
    excel_writer.close()


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", type=str, help="Generate verbose log file.")
    args = parser.parse_args()
    return args


def main() -> None:
    import time
    import warnings

    warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

    global logger
    log_file = get_wpp_update_database_log_file(dt.datetime.today())
    logger = setup_logger(__name__, log_file)

    start_time = time.time()

    # Get command line arguments
    args = get_args() if not is_running_via_pytest() else argparse.Namespace()
    if not args:
        return

    os.makedirs(get_wpp_input_dir(), exist_ok=True)
    os.makedirs(get_wpp_static_input_dir(), exist_ok=True)
    os.makedirs(get_wpp_report_dir(), exist_ok=True)

    logger.info(f"Beginning Import of data into the database, at {dt.datetime.today().strftime('%Y-%m-%d %H:%M:%S')}")

    db_conn = get_or_create_db(get_wpp_db_file(), logger)
    importAllData(db_conn)

    elapsed_time = time.time() - start_time
    time.strftime("%S", time.gmtime(elapsed_time))

    logger.info(f"Finished at {dt.datetime.today().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("----------------------------------------------------------------------------------------")
    # input("Press enter to end.")


if __name__ == "__main__":
    main()
