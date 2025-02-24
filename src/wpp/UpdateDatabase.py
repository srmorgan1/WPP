import xml.etree.ElementTree as et
from dateutil import parser
import sqlite3
import argparse
import pandas as pd
import datetime as dt
import zipfile
import glob
import os
import re
from typing import Any, Optional, Tuple, List, Union, IO
from openpyxl import load_workbook

from wpp.config import (
    get_wpp_input_dir,
    get_wpp_report_dir,
    get_wpp_db_file,
    get_wpp_excel_log_file,
    get_wpp_update_database_log_file,
)
from wpp.db import get_or_create_db, get_single_value, get_last_insert_id
from wpp.calendars import BUSINESS_DAY
from wpp.logger import get_log_file

# from wpp.ref_matcher import getPropertyBlockAndTenantRefs
from wpp.utils import getLongestCommonSubstring

#
# Constants
#
CLIENT_CREDIT_ACCOUNT_NUMBER = "06000792"

# Set up logger
log_file = get_wpp_update_database_log_file(dt.datetime.today())
logger = get_log_file(__name__, log_file)

#
# SQL
#
INSERT_PROPERTY_SQL = (
    "INSERT INTO Properties (property_ref, property_name) VALUES (?, Null);"
)
INSERT_BLOCK_SQL = "INSERT INTO Blocks (block_ref, block_name, type, property_id) VALUES (?, Null, ?, ?);"
INSERT_BLOCK_SQL2 = (
    "INSERT INTO Blocks (block_ref, block_name, type, property_id) VALUES (?, ?, ?, ?);"
)
INSERT_TENANT_SQL = (
    "INSERT INTO Tenants (tenant_ref, tenant_name, block_id) VALUES (?, ?, ?);"
)
INSERT_SUGGESTED_TENANT_SQL = (
    "INSERT INTO SuggestedTenants (tenant_id, transaction_id) VALUES (?, ?);"
)
INSERT_TRANSACTION_SQL = "INSERT INTO Transactions (type, amount, description, pay_date, tenant_id, account_id) VALUES (?, ?, ?, ?, ?, ?);"
INSERT_CHARGES_SQL = "INSERT INTO Charges (fund_id, category_id, type_id, at_date, amount, block_id) VALUES (?, ?, ?, ?, ?, ?);"
INSERT_BANK_ACCOUNT_SQL = "INSERT INTO Accounts (sort_code, account_number, account_type, property_or_block, client_ref, account_name, block_id) VALUES (?, ?, ?, ?, ?, ?, ?);"
INSERT_BANK_ACCOUNT_BALANCE_SQL = "INSERT INTO AccountBalances (current_balance, available_balance, at_date, account_id) VALUES (?, ?, ?, ?);"
INSERT_KEY_TABLE_SQL = "INSERT INTO Key_{} (value) VALUES (?);"
INSERT_IRREGULAR_TRANSACTION_REF_SQL = "INSERT INTO IrregularTransactionRefs (tenant_ref, transaction_ref_pattern) VALUES (?, ?);"

SELECT_TENANT_ID_SQL = "SELECT tenant_id FROM Tenants WHERE tenant_ref = ?;"
SELECT_ID_FROM_REF_SQL = "SELECT ID FROM {} WHERE {}_ref = '{}';"
SELECT_ID_FROM_KEY_TABLE_SQL = "SELECT ID FROM Key_{} WHERE value = ?;"
SELECT_PROPERTY_ID_FROM_REF_SQL = (
    "SELECT ID FROM Properties WHERE property_ref = ? AND property_name IS NULL;"
)
SELECT_TRANSACTION_SQL = "SELECT ID FROM Transactions WHERE tenant_id = ? AND description = ? AND pay_date = ? AND account_id = ? and type = ? AND amount between (?-0.005) and (?+0.005);"
SELECT_CHARGES_SQL = "SELECT ID FROM Charges WHERE fund_id = ? AND category_id = ? and type_id = ? and block_id = ? and at_date = ?;"
SELECT_BANK_ACCOUNT_SQL = (
    "SELECT ID FROM Blocks WHERE ID = ? AND account_number IS Null;"
)
SELECT_BANK_ACCOUNT_SQL1 = (
    "SELECT ID FROM Accounts WHERE sort_code = ? AND account_number = ?;"
)
SELECT_BANK_ACCOUNT_BALANCE_SQL = (
    "SELECT ID FROM AccountBalances WHERE at_date = ? AND account_id = ?;"
)
SELECT_TENANT_NAME_SQL = "SELECT tenant_name FROM Tenants WHERE tenant_ref = ?;"
SELECT_BLOCK_NAME_SQL = "SELECT block_name FROM Blocks WHERE block_ref = ?;"
SELECT_TENANT_NAME_BY_ID_SQL = "SELECT tenant_name FROM Tenants WHERE ID = ?;"
SELECT_IRREGULAR_TRANSACTION_TENANT_REF_SQL = "select tenant_ref from IrregularTransactionRefs where instr(?, transaction_ref_pattern) > 0;"
SELECT_IRREGULAR_TRANSACTION_REF_ID_SQL = "select ID from IrregularTransactionRefs where tenant_ref = ? and transaction_ref_pattern = ?;"
SELECT_ALL_IRREGULAR_TRANSACTION_REFS_SQL = (
    "select tenant_ref, transaction_ref_pattern from IrregularTransactionRefs;"
)

UPDATE_BLOCK_ACCOUNT_NUMBER_SQL = (
    "UPDATE Blocks SET account_number = ? WHERE ID = ? AND account_number IS Null;"
)
UPDATE_PROPERTY_DETAILS_SQL = "UPDATE Properties SET property_name = ? WHERE ID = ?;"
UPDATE_BLOCK_NAME_SQL = "UPDATE Blocks SET block_name = ? WHERE ID = ?;"
UPDATE_TENANT_NAME_SQL = "UPDATE Tenants SET tenant_name = ? WHERE ID = ?;"

# Charge types
AUTH_CREDITORS = "Auth Creditors"
AVAILABLE_FUNDS = "Available Funds"
SC_FUND = "SC Fund"

# Regular expressions
PBT_REGEX = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d)-(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX2 = re.compile(
    r"(?:^|\s+|,)(\d\d\d)\s-\s(\d\d)\s-\s(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)"
)
PBT_REGEX3 = re.compile(r"(?:^|\s+|,)(\d\d\d)-0?(\d\d)-(\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX4 = re.compile(r"(?:^|\s+|,)(\d\d)-0?(\d\d)-(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_NO_TERMINATING_SPACE = re.compile(
    r"(?:^|\s+|,)(\d\d\d)-(\d\d)-(\d\d\d)(?:$|\s*|,|/)"
)
PBT_REGEX_NO_BEGINNING_SPACE = re.compile(
    r"(?:^|\s*|,)(\d\d\d)-(\d\d)-(\d\d\d)(?:$|\s+|,|/)"
)
PBT_REGEX_SPECIAL_CASES = re.compile(
    r"(?:^|\s+|,|\.)(\d\d\d)-{1,2}0?(\d\d)-{1,2}(\w{2,5})\s?(?:DC)?(?:$|\s+|,|/)",
    re.ASCII,
)
PBT_REGEX_NO_HYPHENS = re.compile(
    r"(?:^|\s+|,)(\d\d\d)\s{0,2}0?(\d\d)\s{0,2}(\d\d\d)(?:$|\s+|,|/)"
)
PBT_REGEX_NO_HYPHENS_SPECIAL_CASES = re.compile(
    r"(?:^|\s+|,)(\d\d\d)\s{0,2}0?(\d\d)\s{0,2}(\w{3})(?:$|\s+|,|/)", re.ASCII
)
PBT_REGEX_FWD_SLASHES = re.compile(
    r"(?:^|\s+|,)(\d\d\d)/0?(\d\d)/(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)"
)
PT_REGEX = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d\d)(?:$|\s+|,|/)")
PB_REGEX = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d)(?:$|\s+|,|/)")
P_REGEX = re.compile(r"(?:^|\s+)(\d\d\d)(?:$|\s+)")


def get_id(
    db_cursor: sqlite3.Cursor, sql: str, args_tuple: Tuple = ()
) -> Optional[int]:
    return get_single_value(db_cursor, sql, args_tuple)


def get_id_from_ref(
    db_cursor: sqlite3.Cursor, table_name: str, field_name: str, ref_name: str
) -> Optional[int]:
    sql = SELECT_ID_FROM_REF_SQL.format(table_name, field_name, ref_name)
    db_cursor.execute(sql)
    id = db_cursor.fetchone()
    if id:
        return id[0]
    else:
        return None


def get_id_from_key_table(
    db_cursor: sqlite3.Cursor, key_table_name: str, value: str
) -> Optional[int]:
    sql = SELECT_ID_FROM_KEY_TABLE_SQL.format(key_table_name)
    db_cursor.execute(sql, (value,))
    id = db_cursor.fetchone()
    if id:
        return id[0]
    else:
        sql = INSERT_KEY_TABLE_SQL.format(key_table_name)
        db_cursor.execute(sql, (value,))
        return get_last_insert_id(db_cursor, "Key_{}".format(key_table_name))


def open_files(file_paths: List[str]) -> List[IO]:
    files = []
    for file_path in file_paths:
        ext = os.path.splitext(file_path)
        if ext == ".zip":
            # A zip file may contain multiple zipped files
            zfile = zipfile.ZipFile(file_path)
            for finfo in zfile.infolist():
                # Mac OSX zip files contain a directory we don't want
                if "__MACOSX" not in finfo.filename:
                    files.append(zfile.open(finfo))
        else:
            files.append(open(file_path))
    return files


# Open a file, which can be within a zip file
def open_file(file_path: str) -> IO:
    ext = os.path.splitext(file_path)
    if ext[1].lower() == ".zip":
        # A zip file may contain multiple zipped files, however we only want the first one
        zfile = zipfile.ZipFile(file_path)
        files = [
            finfo for finfo in zfile.infolist() if "__MACOSX" not in finfo.filename
        ]
        if len(files) > 1:
            raise ValueError(
                "Zip file {} must contain only only one zipped file".format(file_path)
            )
        else:
            return zfile.open(files[0])
    else:
        return open(file_path)


def getMatchingFileNames(file_paths: Union[str, List[str]]) -> List[str]:
    files = []
    if not isinstance(file_paths, list):
        file_paths = [file_paths]

    for file_path in file_paths:
        files.extend(glob.glob(file_path))
    return sorted(files, key=os.path.getctime)


def getLatestMatchingFileName(file_path: str) -> Optional[str]:
    files = glob.glob(file_path)
    if files:
        return max(files, key=os.path.getctime)
    else:
        return None


def getLatestMatchingFileNameInDir(wpp_dir: str, file_name_glob: str) -> Optional[str]:
    files = glob.glob(os.path.join(wpp_dir, file_name_glob))
    if files:
        return max(files, key=os.path.getctime)
    else:
        return None


def checkTenantExists(db_cursor: sqlite3.Cursor, tenant_ref: str) -> Optional[str]:
    tenant_name = get_single_value(db_cursor, SELECT_TENANT_NAME_SQL, (tenant_ref,))
    return tenant_name


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
        # one in the tenant name of >= 4 chars, then this is a match.
        return len(lcss) >= 4
    else:
        return False


def removeDCReferencePostfix(tenant_ref: Optional[str]) -> Optional[str]:
    # Remove 'DC' from parsed tenant references paid by debit card
    if tenant_ref is not None and tenant_ref[-2:] == "DC":
        tenant_ref = tenant_ref[:-2].strip()
    return tenant_ref


def correctKnownCommonErrors(
    property_ref: str, block_ref: str, tenant_ref: Optional[str]
) -> Tuple[str, str, Optional[str]]:
    # Correct known errors in the tenant payment references
    if property_ref == "094" and tenant_ref is not None and tenant_ref[-3] == "O":
        tenant_ref = tenant_ref[:-3] + "0" + tenant_ref[-2:]
    return property_ref, block_ref, tenant_ref


def recodeSpecialPropertyReferenceCases(
    property_ref: str, block_ref: str, tenant_ref: Optional[str]
) -> Tuple[str, str, Optional[str]]:
    if property_ref == "020" and block_ref == "020-03":
        # Block 020-03 belongs to a different property group, call this 020A.
        property_ref = "020A"
    elif property_ref == "064" and block_ref == "064-01":
        property_ref = "064A"
    return property_ref, block_ref, tenant_ref


def recodeSpecialBlockReferenceCases(
    property_ref: str, block_ref: str, tenant_ref: Optional[str]
) -> Tuple[str, str, Optional[str]]:
    if property_ref == "101" and block_ref == "101-02":
        # Block 101-02 is wrong, change this to 101-01
        block_ref = "101-01"
        tenant_ref = tenant_ref.replace("101-02", "101-01")
    return property_ref, block_ref, tenant_ref


def getPropertyBlockAndTenantRefsFromRegexMatch(
    match: re.Match,
) -> Tuple[str, str, str]:
    property_ref, block_ref, tenant_ref = None, None, None
    if match:
        property_ref = match.group(1)
        block_ref = "{}-{}".format(match.group(1), match.group(2))
        tenant_ref = "{}-{}-{}".format(match.group(1), match.group(2), match.group(3))
    return property_ref, block_ref, tenant_ref


def doubleCheckTenantRef(
    db_cursor: sqlite3.Cursor, tenant_ref: str, reference: str
) -> bool:
    tenant_name = checkTenantExists(db_cursor, tenant_ref)
    if tenant_name:
        return matchTransactionRef(tenant_name, reference)
    else:
        return False


def postProcessPropertyBlockTenantRefs(
    property_ref: Optional[str], block_ref: Optional[str], tenant_ref: Optional[str]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # Ignore some property and tenant references, and recode special cases
    # e.g. Block 020-03 belongs to a different property than the other 020-xx blocks.
    if tenant_ref is not None and ("Z" in tenant_ref or "Y" in tenant_ref):
        return None, None, None
    elif (
        property_ref is not None
        and property_ref.isnumeric()
        and int(property_ref) >= 900
    ):
        return None, None, None
    property_ref, block_ref, tenant_ref = recodeSpecialPropertyReferenceCases(
        property_ref, block_ref, tenant_ref
    )
    property_ref, block_ref, tenant_ref = recodeSpecialBlockReferenceCases(
        property_ref, block_ref, tenant_ref
    )
    return property_ref, block_ref, tenant_ref


def checkForIrregularTenantRefInDatabase(
    reference: str, db_cursor: Optional[sqlite3.Cursor]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # Look for known irregular transaction refs which we know some tenants use
    if db_cursor:
        tenant_ref = get_single_value(
            db_cursor, SELECT_IRREGULAR_TRANSACTION_TENANT_REF_SQL, (reference,)
        )
        if tenant_ref:
            return getPropertyBlockAndTenantRefs(tenant_ref)  # Parse tenant reference
        # else:
        #    transaction_ref_data = get_data(db_cursor, SELECT_ALL_IRREGULAR_TRANSACTION_REFS_SQL)
        #    for tenant_ref, transaction_ref_pattern in transaction_ref_data:
        #        pass
    return None, None, None


def getPropertyBlockAndTenantRefs(
    reference: str, db_cursor: Optional[sqlite3.Cursor] = None
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    return getPropertyBlockAndTenantRefsImpl(reference, db_cursor)


def getPropertyBlockAndTenantRefsImpl(
    reference: str, db_cursor: Optional[sqlite3.Cursor] = None
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # TODO: refactor to use chain of responsibilty pattern here instead of nested ifs
    property_ref, block_ref, tenant_ref = None, None, None

    if not isinstance(reference, str):
        return None, None, None

    # if '133-' in reference:
    #    print(reference)

    # Try to match property, block and tenant
    description = str(reference).strip()

    # Check the database for irregular transaction references first
    property_ref, block_ref, tenant_ref = checkForIrregularTenantRefInDatabase(
        description, db_cursor
    )
    if property_ref and block_ref and tenant_ref:
        return property_ref, block_ref, tenant_ref

    # Then check various regular expression rules
    match = re.search(PBT_REGEX, description)
    if match:
        property_ref, block_ref, tenant_ref = (
            getPropertyBlockAndTenantRefsFromRegexMatch(match)
        )
        # if db_cursor and not checkTenantExists(db_cursor, tenant_ref):
        #    return None, None, None
    else:
        match = re.search(PBT_REGEX_FWD_SLASHES, description)
        if match:
            property_ref, block_ref, tenant_ref = (
                getPropertyBlockAndTenantRefsFromRegexMatch(match)
            )
            if db_cursor and not doubleCheckTenantRef(db_cursor, tenant_ref, reference):
                return None, None, None
        else:
            match = re.search(
                PBT_REGEX2, description
            )  # Match tenant with spaces between hyphens
            if match:
                property_ref, block_ref, tenant_ref = (
                    getPropertyBlockAndTenantRefsFromRegexMatch(match)
                )
                if db_cursor and not doubleCheckTenantRef(
                    db_cursor, tenant_ref, reference
                ):
                    return None, None, None
            else:
                match = re.search(PBT_REGEX3, description)  # Match tenant with 2 digits
                if match:
                    property_ref, block_ref, tenant_ref = (
                        getPropertyBlockAndTenantRefsFromRegexMatch(match)
                    )
                    if db_cursor and not doubleCheckTenantRef(
                        db_cursor, tenant_ref, reference
                    ):
                        tenant_ref = "{}-{}-0{}".format(
                            match.group(1), match.group(2), match.group(3)
                        )
                        if not doubleCheckTenantRef(db_cursor, tenant_ref, reference):
                            return None, None, None
                else:
                    match = re.search(
                        PBT_REGEX4, description
                    )  # Match property with 2 digits
                    if match:
                        property_ref, block_ref, tenant_ref = (
                            getPropertyBlockAndTenantRefsFromRegexMatch(match)
                        )
                        if db_cursor and not checkTenantExists(db_cursor, tenant_ref):
                            property_ref = "0{}".format(match.group(1))
                            block_ref = "{}-{}".format(property_ref, match.group(2))
                            tenant_ref = "{}-{}".format(block_ref, match.group(3))
                            if not checkTenantExists(db_cursor, tenant_ref):
                                return None, None, None
                    else:
                        # Try to match property, block and tenant special cases
                        match = re.search(PBT_REGEX_SPECIAL_CASES, description)
                        if match:
                            property_ref = match.group(1)
                            block_ref = "{}-{}".format(match.group(1), match.group(2))
                            tenant_ref = "{}-{}-{}".format(
                                match.group(1), match.group(2), match.group(3)
                            )
                            if db_cursor:
                                tenant_ref = removeDCReferencePostfix(tenant_ref)
                                if not doubleCheckTenantRef(
                                    db_cursor, tenant_ref, reference
                                ):
                                    property_ref, block_ref, tenant_ref = (
                                        correctKnownCommonErrors(
                                            property_ref, block_ref, tenant_ref
                                        )
                                    )
                                    if not doubleCheckTenantRef(
                                        db_cursor, tenant_ref, reference
                                    ):
                                        return None, None, None
                            elif not (
                                (
                                    property_ref
                                    in [
                                        "093",
                                        "094",
                                        "095",
                                        "096",
                                        "099",
                                        "124",
                                        "132",
                                        "133",
                                        "134",
                                    ]
                                )
                                or (
                                    property_ref in ["020", "022", "039", "053", "064"]
                                    and match.group(3)[-1] != "Z"
                                )
                            ):
                                return None, None, None
                        else:
                            # Match property and block only
                            match = re.search(PB_REGEX, description)
                            if match:
                                property_ref = match.group(1)
                                block_ref = "{}-{}".format(
                                    match.group(1), match.group(2)
                                )
                            else:
                                # Match property and tenant only
                                # Prevent this case from matching for now, or move to the end of the match blocks
                                match = re.search(PT_REGEX, description) and False
                                if match:
                                    pass
                                    # property_ref = match.group(1)
                                    # tenant_ref = match.group(2)  # Non-unique tenant ref, may be useful
                                    # block_ref = '01'   # Null block indicates that the tenant and block can't be matched uniquely
                                else:
                                    # Match without hyphens, or with no terminating space.
                                    # These cases can only come from parsed transaction references.
                                    # in which case we can double check that the data exists in and matches the database.
                                    match = (
                                        re.search(PBT_REGEX_NO_HYPHENS, description)
                                        or re.search(
                                            PBT_REGEX_NO_HYPHENS_SPECIAL_CASES,
                                            description,
                                        )
                                        or re.search(
                                            PBT_REGEX_NO_TERMINATING_SPACE, description
                                        )
                                        or re.search(
                                            PBT_REGEX_NO_BEGINNING_SPACE, description
                                        )
                                    )
                                    if match:
                                        property_ref, block_ref, tenant_ref = (
                                            getPropertyBlockAndTenantRefsFromRegexMatch(
                                                match
                                            )
                                        )
                                        if db_cursor and not doubleCheckTenantRef(
                                            db_cursor, tenant_ref, reference
                                        ):
                                            property_ref, block_ref, tenant_ref = (
                                                correctKnownCommonErrors(
                                                    property_ref, block_ref, tenant_ref
                                                )
                                            )
                                            if not doubleCheckTenantRef(
                                                db_cursor, tenant_ref, reference
                                            ):
                                                return None, None, None
                                    # else:
                                    #    # Match property reference only
                                    #    match = re.search(P_REGEX, description)
                                    #    if match:
                                    #        property_ref = match.group(1)
                                    #    else:
                                    #        return None, None, None
    return postProcessPropertyBlockTenantRefs(property_ref, block_ref, tenant_ref)


def getTenantID(csr: sqlite3.Cursor, tenant_ref: str) -> None:
    # sql = SELECT_TENANT_ID_SQL.format(tenant_ref)
    csr.execute(SELECT_TENANT_ID_SQL, (tenant_ref))


# Helper function to get text from an XML element and ensure it is not None
def get_element_text(parent_element: et.Element, child_element_name: str) -> str:
    child_element = parent_element.find(child_element_name)
    if child_element is None or child_element.text is None:
        raise ValueError(f"Missing or empty field: {child_element_name}")
    return child_element.text


def importBankOfScotlandTransactionsXMLFile(
    db_conn: sqlite3.Connection, transactions_xml_file: str
) -> Tuple[List[List[Any]], List[List[Any]]]:
    errors_list = []
    duplicate_transactions = []

    with open_file(transactions_xml_file) as f:
        xml = f.read()
        if type(xml) is bytes:
            xml = str(xml, "utf-8")
        xml = xml.replace("\n", "")
        schema = "PreviousDayTransactionExtract"
        xsd = "https://isite.bankofscotland.co.uk/Schemas/{}.xsd".format(schema)
        xml = re.sub(
            r"""<({})\s+(xmlns=(?:'|")){}(?:'|")\s*>""".format(schema, xsd),
            r"<\1>",
            xml,
        )
    tree = et.fromstring(xml)

    num_transactions_added_to_db = 0
    num_import_errors = 0
    tenant_id = None

    try:
        csr = db_conn.cursor()
        csr.execute("begin")
        for transaction in tree.iter("TransactionRecord"):
            sort_code = get_element_text(transaction, "SortCode")
            account_number = get_element_text(transaction, "AccountNumber")
            transaction_type = get_element_text(transaction, "TransactionType")
            amount = get_element_text(transaction, "TransactionAmount")
            description = get_element_text(transaction, "TransactionDescription")
            pay_date = get_element_text(transaction, "TransactionPostedDate")

            # Only load transactions from the client credit account
            if account_number != CLIENT_CREDIT_ACCOUNT_NUMBER:
                continue

            pay_date = parser.parse(pay_date, dayfirst=True).strftime("%Y-%m-%d")

            # Parse the description field to determine the property, block and tenant that it belongs to
            property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefs(
                description, csr
            )

            # If uniquely identified the property, block and tenant, save in the DB
            if tenant_ref:
                if property_ref and block_ref:
                    account_id = get_id(
                        csr, SELECT_BANK_ACCOUNT_SQL1, (sort_code, account_number)
                    )
                    tenant_id = get_id_from_ref(csr, "Tenants", "tenant", tenant_ref)
                    if tenant_id:
                        transaction_id = get_id(
                            csr,
                            SELECT_TRANSACTION_SQL,
                            (
                                tenant_id,
                                description,
                                pay_date,
                                account_id,
                                transaction_type,
                                amount,
                                amount,
                            ),
                        )
                        if not transaction_id:
                            csr.execute(
                                INSERT_TRANSACTION_SQL,
                                (
                                    transaction_type,
                                    amount,
                                    description,
                                    pay_date,
                                    tenant_id,
                                    account_id,
                                ),
                            )
                            logger.debug(
                                "\tAdding transaction {}".format(
                                    str(
                                        (
                                            sort_code,
                                            account_number,
                                            transaction_type,
                                            amount,
                                            description,
                                            pay_date,
                                            tenant_ref,
                                        )
                                    )
                                )
                            )
                            num_transactions_added_to_db += 1
                        else:
                            duplicate_transactions.append(
                                [
                                    pay_date,
                                    transaction_type,
                                    float(amount),
                                    tenant_ref,
                                    description,
                                ]
                            )
                    else:
                        num_import_errors += 1
                        logger.debug(
                            "Cannot find tenant with reference '{}'. Ignoring transaction {}".format(
                                tenant_ref,
                                str(
                                    (
                                        pay_date,
                                        sort_code,
                                        account_number,
                                        transaction_type,
                                        amount,
                                        description,
                                    )
                                ),
                            )
                        )
                        errors_list.append(
                            [
                                pay_date,
                                sort_code,
                                account_number,
                                transaction_type,
                                float(amount),
                                description,
                                "Cannot find tenant with reference '{}'".format(
                                    tenant_ref
                                ),
                            ]
                        )
                # elif property_ref:
                # TODO: check if the property only has one block, if so we set block_ref to '01' and upload.
                # TODO: else check if there is only one property with this tenant ref. If so, we then know the block and can upload (at least as a suggestion)
                # pass
            # elif property_ref or (property_ref and block_ref):
            # TODO: try to make some kind of match from the description against the tenant name, and save
            # them in the suggested tenant references table
            # If we can't match anything, list all of the possible tenants that have not had a transaction allocated this month?
            # Maybe the last part should go in the report script
            # pass
            else:
                num_import_errors += 1
                logger.debug(
                    "Cannot determine tenant from description '{}'. Ignoring transaction {}".format(
                        description,
                        str(
                            (
                                pay_date,
                                sort_code,
                                account_number,
                                transaction_type,
                                amount,
                                description,
                            )
                        ),
                    )
                )
                errors_list.append(
                    [
                        pay_date,
                        sort_code,
                        account_number,
                        transaction_type,
                        float(amount),
                        description,
                        "Cannot determine tenant from description",
                    ]
                )

        csr.execute("end")
        db_conn.commit()
        if num_import_errors:
            logger.info(
                "Unable to import {} transactions into the database. See the Data_Import_Issues Excel file for details. Add tenant references to 001 GENERAL CREDITS CLIENTS WITHOUT IDENTS.xlsx and run import again.".format(
                    num_import_errors
                )
            )
        logger.info(
            f"{num_transactions_added_to_db} Bank Of Scotland transactions added to the database."
        )
        return errors_list, duplicate_transactions

    except db_conn.Error as err:
        logger.error(str(err))
        logger.error(
            "The data which caused the failure is: "
            + str(
                (
                    sort_code,
                    account_number,
                    transaction_type,
                    amount,
                    description,
                    pay_date,
                    tenant_id,
                )
            )
        )
        logger.error(
            "No Bank Of Scotland transactions have been added to the database."
        )
        logger.exception(err)
        csr.execute("rollback")
    except Exception as ex:
        logger.error(str(ex))
        logger.exception(ex)
        logger.error(
            "The data which caused the failure is: "
            + str(
                (
                    sort_code,
                    account_number,
                    transaction_type,
                    amount,
                    description,
                    pay_date,
                    tenant_id,
                )
            )
        )
        logger.error(
            "No Bank Of Scotland transactions have been added to the database."
        )
        csr.execute("rollback")

    return [], []


def importBankOfScotlandBalancesXMLFile(
    db_conn: sqlite3.Connection, balances_xml_file: str
) -> None:
    with open_file(balances_xml_file) as f:
        xml = f.read()
        if isinstance(xml, bytes):
            xml = str(xml, "utf-8")
        xml = xml.replace("\n", "")
        for schema in ["BalanceDetailedReport", "EndOfDayBalanceExtract"]:
            xsd = "https://isite.bankofscotland.co.uk/Schemas/{}.xsd".format(schema)
            xml = re.sub(
                r"""<({})\s+(xmlns=(?:'|")){}(?:'|")\s*>""".format(schema, xsd),
                r"<\1>",
                xml,
            )
            # xml = xml.replace(" {}".format(xsd), '').replace(xsd, '')
    tree = et.fromstring(xml)

    num_balances_added_to_db = 0
    # accounts = []

    try:
        csr = db_conn.cursor()
        csr.execute("begin")
        for reporting_day in tree.iter("ReportingDay"):
            at_date = get_element_text(reporting_day, "Date")
            at_date = parser.parse(at_date, dayfirst=True).strftime("%Y-%m-%d")
            for balance in reporting_day.iter("BalanceRecord"):
                sort_code = get_element_text(balance, "SortCode")
                account_number = get_element_text(balance, "AccountNumber")
                client_ref = (
                    client_ref_element.text
                    if (client_ref_element := balance.find("ClientRef")) is not None
                    else None
                )
                account_name = get_element_text(balance, "LongName")

                account_type = ""
                if client_ref and "RENT" in client_ref.upper():
                    account_type = "GR"
                elif client_ref and "BANK" in client_ref.upper():
                    account_type = "CL"
                elif client_ref and "RES" in client_ref.upper():
                    account_type = "RE"
                else:
                    account_type = "NA"
                # elif client_ref: raise ValueError(f'Cannot determine account type from client reference {client_ref}')

                current_balance = get_element_text(balance, "CurrentBalance")
                available_balance = get_element_text(balance, "AvailableBalance")

                if sort_code and account_number:
                    account_id = get_id(
                        csr, SELECT_BANK_ACCOUNT_SQL1, (sort_code, account_number)
                    )
                    if account_id:
                        account_balance_id = get_id(
                            csr, SELECT_BANK_ACCOUNT_BALANCE_SQL, (at_date, account_id)
                        )
                        if not account_balance_id:
                            csr.execute(
                                INSERT_BANK_ACCOUNT_BALANCE_SQL,
                                (
                                    current_balance,
                                    available_balance,
                                    at_date,
                                    account_id,
                                ),
                            )
                            logger.debug(
                                "\tAdding bank balance {}".format(
                                    str(
                                        (
                                            sort_code,
                                            account_number,
                                            account_type,
                                            client_ref,
                                            account_name,
                                            at_date,
                                            current_balance,
                                            available_balance,
                                        )
                                    )
                                )
                            )
                            num_balances_added_to_db += 1
                    else:
                        pass
                        # accounts.append((sort_code, account_number, account_type, 'Block', client_ref, account_name))
                else:
                    logger.warning(
                        "Cannot determine bank account. Ignoring balance record {}".format(
                            str(
                                (
                                    sort_code,
                                    account_number,
                                    account_type,
                                    client_ref,
                                    account_name,
                                    at_date,
                                    current_balance,
                                    available_balance,
                                )
                            )
                        )
                    )

        csr.execute("end")
        db_conn.commit()
        logger.info(
            f"{num_balances_added_to_db} Bank Of Scotland account balances added to the database."
        )

        # accounts_df = pd.DataFrame(accounts, columns=['Sort Code', 'Account Number', 'Account Type', 'PropertyOrBlock', 'Client Reference', 'Account Name'])
        # ef = get_wpp_input_dir() + r'/accounts_temp.xlsx'
        # excel_writer = pd.ExcelWriter(ef, engine='openpyxl')
        # accounts_df.to_excel(excel_writer, index=False)
        # excel_writer.close()
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error(
            "The data which caused the failure is: "
            + str(
                (
                    sort_code,
                    account_number,
                    account_type,
                    client_ref,
                    account_name,
                    at_date,
                    current_balance,
                    available_balance,
                )
            )
        )
        logger.error(
            "No Bank Of Scotland account balances have been added to the database."
        )
        logger.exception(err)
        csr.execute("rollback")
    except Exception as ex:
        logger.error(str(ex))
        logger.error(
            "The data which caused the failure is: "
            + str(
                (
                    sort_code,
                    account_number,
                    account_type,
                    client_ref,
                    account_name,
                    at_date,
                    current_balance,
                    available_balance,
                )
            )
        )
        logger.error(
            "No Bank Of Scotland account balances have been added to the database."
        )
        logger.exception(ex)
        csr.execute("rollback")
        # charges = {}


def importPropertiesFile(db_conn: sqlite3.Connection, properties_xls_file: str) -> None:
    # Read Excel spreadsheet into dataframe
    properties_df = pd.read_excel(properties_xls_file)
    properties_df.fillna("", inplace=True)

    num_properties_added_to_db = 0
    num_blocks_added_to_db = 0
    num_tenants_added_to_db = 0

    # Import into DB
    try:
        csr = db_conn.cursor()
        csr.execute("begin")
        for index, row in properties_df.iterrows():
            reference = row["Reference"]
            tenant_name = row["Name"]
            # If the tenant reference begins with a '9' or contains a 'Y' or 'Z',then ignore this data
            if (
                reference is None
                or reference[0] == "9"
                or "Y" in reference.upper()
                or "Z" in reference.upper()
            ):
                continue

            property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefs(
                reference
            )
            if (property_ref, block_ref, tenant_ref) == (None, None, None):
                logger.warning(
                    f"\tUnable to parse tenant reference {reference}, will not add to the database."
                )
                continue
            property_id = get_id_from_ref(csr, "Properties", "property", property_ref)
            if not property_id:
                csr.execute(INSERT_PROPERTY_SQL, (property_ref,))
                logger.debug(f"\tAdding property {property_ref} to the database")
                num_properties_added_to_db += 1
                property_id = get_last_insert_id(csr, "Properties")

            block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)
            if not block_id:
                if (
                    block_ref[-2:] == "00"
                ):  # Estates are identified by the 00 at the end of the block reference
                    block_type = "P"
                else:
                    block_type = "B"
                csr.execute(INSERT_BLOCK_SQL, (block_ref, block_type, property_id))
                logger.debug(f"\tAdding block {block_ref} to the database")
                num_blocks_added_to_db += 1
                block_id = get_last_insert_id(csr, "Blocks")

            tenant_id = get_id_from_ref(csr, "Tenants", "tenant", tenant_ref)
            if tenant_ref and not tenant_id:
                csr.execute(INSERT_TENANT_SQL, (tenant_ref, tenant_name, block_id))
                logger.debug(f"\tAdding tenant {tenant_ref} to the database")
                num_tenants_added_to_db += 1
            else:
                old_tenant_name = get_single_value(
                    csr, SELECT_TENANT_NAME_BY_ID_SQL, (tenant_id,)
                )
                if tenant_name and tenant_name != old_tenant_name:
                    csr.execute(UPDATE_TENANT_NAME_SQL, (tenant_name, tenant_id))
                    logger.info(
                        f"Updated tenant name to {tenant_name} for tenant reference {tenant_ref}"
                    )
        csr.execute("end")
        db_conn.commit()
        logger.info(f"{num_properties_added_to_db} properties added to the database.")
        logger.info(f"{num_blocks_added_to_db} blocks added to the database.")
        logger.info(f"{num_tenants_added_to_db} tenants added to the database.")
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error(
            "The data which caused the failure is: "
            + str((reference, tenant_name, property_ref, block_ref, tenant_ref))
        )
        logger.error("No properties, blocks or tenants have been added to the database")
        csr.execute("rollback")
        raise
    except Exception as ex:
        logger.error(str(ex))
        logger.error(
            "The data which caused the failure is: "
            + str((reference, tenant_name, property_ref, block_ref, tenant_ref))
        )
        logger.error(
            "No properties, blocks or tenants have been added to the database."
        )
        csr.execute("rollback")
        raise


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
            if (
                reference is None
                or reference[0] == "9"
                or "Y" in reference.upper()
                or "Z" in reference.upper()
            ):
                continue

            # Update property to be an estate, if the property name has not already been set
            property_id = get_id_from_ref(csr, "Properties", "property", reference)
            if property_id:
                if (
                    get_id(csr, SELECT_PROPERTY_ID_FROM_REF_SQL, (reference,))
                    == property_id
                ):
                    csr.execute(UPDATE_PROPERTY_DETAILS_SQL, (estate_name, property_id))
                    num_estates_added_to_db += 1

                # Add a '00' block for the estate service charges, if not already present
                block_ref = reference + "-00"
                block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)
                if not block_id:
                    csr.execute(
                        INSERT_BLOCK_SQL2, (block_ref, estate_name, "P", property_id)
                    )
                    num_blocks_added_to_db += 1
        csr.execute("end")
        db_conn.commit()
        logger.info(f"{num_estates_added_to_db} estates added to the database.")
        logger.info(f"{num_blocks_added_to_db} estate blocks added to the database.")
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error(
            "The data which caused the failure is: " + str((reference, estate_name))
        )
        logger.error("No estates or estate blocks have been added to the database")
        csr.execute("rollback")
        raise
    except Exception as ex:
        logger.error(str(ex))
        logger.error(
            "The data which caused the failure is: " + str((reference, estate_name))
        )
        logger.error("No estates or estate blocks have been added to the database.")
        csr.execute("rollback")
        raise


def addPropertyToDB(
    db_conn: sqlite3.Connection, property_ref: str, rethrow_exception: bool = False
) -> Optional[int]:
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
) -> Optional[int]:
    block_id = None
    try:
        csr = db_conn.cursor()
        csr.execute("begin")

        if block_ref:
            block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)
            if not block_id:
                if property_ref:
                    if block_ref[-2:] == "00":
                        block_type = "P"
                    else:
                        block_type = "B"
                    property_id = get_id_from_ref(
                        csr, "Properties", "property", property_ref
                    )
                    csr.execute(INSERT_BLOCK_SQL, (block_ref, block_type, property_id))
                    logger.debug(f"\tAdding block {block_ref}")
                    block_id = get_last_insert_id(csr, "Blocks")

        csr.execute("end")
        db_conn.commit()
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error(
            "The data which caused the failure is: " + str((property_ref, block_ref))
        )
        logger.error("Unable to add property or block to the database")
        logger.exception(err)
        csr.execute("rollback")
        if rethrow_exception:
            raise
    except Exception as ex:
        logger.error(str(ex))
        logger.exception(ex)
        logger.error(
            "The data which caused the failure is: " + str((property_ref, block_ref))
        )
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
) -> Optional[int]:
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
        logger.error(
            "The data which caused the failure is: " + str((block_ref, tenant_ref))
        )
        logger.error("Unable to add tenant to the database")
        logger.exception(err)
        csr.execute("rollback")
        if rethrow_exception:
            raise
    except Exception as ex:
        logger.error(str(ex))
        logger.exception(ex)
        logger.error(
            "The data which caused the failure is: " + str((block_ref, tenant_ref))
        )
        logger.error("Unable to add tenant to the database")
        csr.execute("rollback")
        if rethrow_exception:
            raise
    return tenant_id


def importBlockBankAccountNumbers(
    db_conn: sqlite3.Connection, bos_reconciliations_file: str
) -> None:
    # Read Excel spreadsheet into dataframe
    bank_accounts_df = pd.read_excel(bos_reconciliations_file, "Accounts", dtype=str)

    num_bank_accounts_added_to_db = 0

    try:
        csr = db_conn.cursor()
        csr.execute("begin")
        for index, row in bank_accounts_df.iterrows():
            block_ref = row["Property Reference"]
            account_number = row["Account Number"]

            block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)
            if block_id:
                id = get_id(csr, SELECT_BANK_ACCOUNT_SQL, (block_id,))
                if id:
                    csr.execute(
                        UPDATE_BLOCK_ACCOUNT_NUMBER_SQL, (account_number, block_id)
                    )
                    logger.debug(
                        f"\tAdding bank account number {account_number} for block {block_id}"
                    )
                    num_bank_accounts_added_to_db += 1
        csr.execute("end")
        db_conn.commit()
        logger.info(
            f"{num_bank_accounts_added_to_db} bank account numbers added to the database."
        )
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error(
            "The data which caused the failure is: " + str((block_ref, account_number))
        )
        logger.error("No bank account numbers have been added to the database")
        logger.exception(err)
        csr.execute("rollback")
    except Exception as ex:
        logger.error(str(ex))
        logger.error(
            "The data which caused the failure is: " + str((block_ref, account_number))
        )
        logger.error("No bank account numbers have been added to the database.")
        logger.exception(ex)
        csr.execute("rollback")
        # charges = {}


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
            if (
                property_or_block.upper() == "PROPERTY"
                or property_or_block.upper() == "P"
            ):
                property_block = "P"
            elif (
                property_or_block.upper() == "BLOCK" or property_or_block.upper() == "B"
            ):
                property_block = "B"
            elif property_or_block == "" or property_or_block is None:
                property_block = ""
            else:
                raise ValueError(
                    f"Unknown property/block type {property_or_block} for bank account ({sort_code}, {account_number})"
                )

            property_ref, block_ref, _ = getPropertyBlockAndTenantRefs(reference)

            if (
                property_block == "P"
                and block_ref is not None
                and block_ref[-2:] != "00"
            ):
                raise ValueError(
                    f"Block reference ({reference}) for an estate must end in 00, for bank account ({sort_code}, {account_number})"
                )

            block_id = get_id_from_ref(csr, "Blocks", "block", reference)
            id = get_id(csr, SELECT_BANK_ACCOUNT_SQL1, (sort_code, account_number))
            if sort_code and account_number and not id:
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
                logger.debug(
                    f"\tAdding bank account ({sort_code}, {account_number}) for property {reference}"
                )
                num_bank_accounts_added_to_db += 1

        csr.execute("end")
        db_conn.commit()
        logger.info(
            f"{num_bank_accounts_added_to_db} bank accounts added to the database."
        )
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error(
            "The data which caused the failure is: "
            + str(
                (reference, sort_code, account_number, account_type, property_or_block)
            )
        )
        logger.error("No bank accounts have been added to the database")
        csr.execute("rollback")
        raise
    except Exception as ex:
        logger.error(str(ex))
        logger.error(
            "The data which caused the failure is: "
            + str(
                (reference, sort_code, account_number, account_type, property_or_block)
            )
        )
        logger.error("No bank accounts have been added to the database.")
        csr.execute("rollback")
        raise


def importIrregularTransactionReferences(
    db_conn: sqlite3.Connection, anomalous_refs_file: str
) -> None:
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

            id = get_id(
                csr,
                SELECT_IRREGULAR_TRANSACTION_REF_ID_SQL,
                (tenant_reference, payment_reference_pattern),
            )
            if tenant_reference and not id:
                csr.execute(
                    INSERT_IRREGULAR_TRANSACTION_REF_SQL,
                    (tenant_reference, payment_reference_pattern),
                )
                logger.debug(
                    f"\tAdding irregular transaction reference pattern ({tenant_reference}) for tenant {payment_reference_pattern}"
                )
                num_anomalous_refs_added_to_db += 1

        csr.execute("end")
        db_conn.commit()
        logger.info(
            f"{num_anomalous_refs_added_to_db} irregular transaction reference patterns added to the database."
        )
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error(
            "No irregular transaction reference patterns have been added to the database"
        )
        logger.error(
            "The data which caused the failure is: "
            + str((tenant_reference, payment_reference_pattern))
        )
        csr.execute("rollback")
        raise
    except Exception as ex:
        logger.error(str(ex))
        logger.error(
            "No irregular transaction reference patterns have been added to the database."
        )
        logger.error(
            "The data which caused the failure is: "
            + str((tenant_reference, payment_reference_pattern))
        )
        csr.execute("rollback")
        raise


def calculateSCFund(
    auth_creditors: float, available_funds: float, property_ref: str, block_ref: str
) -> float:
    # TODO: This should be encoded in a user-supplied rules spreadsheet for generality
    if property_ref == "035":
        return available_funds
    else:
        return auth_creditors + available_funds


def importQubeEndOfDayBalancesFile(
    db_conn: sqlite3.Connection, qube_eod_balances_xls_file: str
) -> None:
    # nested_dict = lambda: defaultdict(nested_dict)
    # charges = nested_dict()

    num_charges_added_to_db = 0

    # Read in the Qube balances report spreadsheet
    qube_eod_balances_workbook = load_workbook(
        qube_eod_balances_xls_file, read_only=True, data_only=True
    )
    qube_eod_balances_workbook_sheet = qube_eod_balances_workbook.worksheets[0]

    # Check that this Qube balances report has some of the expected cells (that it is the correct report)
    A1_cell_value = qube_eod_balances_workbook_sheet.cell(1, 1).value
    B1_cell_value = qube_eod_balances_workbook_sheet.cell(1, 2).value
    produced_date_cell_value = qube_eod_balances_workbook_sheet.cell(3, 1).value
    if not isinstance(produced_date_cell_value, str):
        raise ValueError(
            f"The produced date cell value is not a string: {produced_date_cell_value}"
        )
    cell_values_actual = [
        qube_eod_balances_workbook_sheet.cell(5, i + 1).value for i in range(0, 4)
    ]
    cell_values_check = [
        "Property / Fund",
        "Bank",
        "Excluded VAT",
        "Auth Creditors",
        "Available Funds",
    ]
    if not (
        A1_cell_value == "Property Management"
        and B1_cell_value == "Funds Available in Property Funds"
        and all(x[0] == x[1] for x in zip(cell_values_actual, cell_values_check))
    ):
        logger.error("The spreadsheet {} does not look like a Qube balances report.")

    # Get date that the Qube report was produced from the spreadsheet, and calculate the Qube COB date from that
    at_date_str = " ".join(produced_date_cell_value.split()[-3:])
    at_date = (parser.parse(at_date_str, dayfirst=True) - BUSINESS_DAY).strftime(
        "%Y-%m-%d"
    )

    # Read in the data table from the spreadsheet
    qube_eod_balances_df = pd.read_excel(
        qube_eod_balances_xls_file, usecols="B:G", skiprows=4
    )

    # Column names in Qube report are associated with the wrong values - fix them
    qube_eod_balances_df.columns = [
        "PropertyCode / Fund",
        "PropertyName / Category",
        "Bank",
        "Excluded VAT",
        "Auth Creditors",
        "Available Funds",
    ]

    # Drop all empty rows and replace 'nan' values with 0
    qube_eod_balances_df.dropna(how="all", inplace=True)
    qube_eod_balances_df.fillna(0, inplace=True)

    try:
        csr = db_conn.cursor()
        csr.execute("begin")
        found_property = False
        property_ref = None
        block_ref = None
        block_name = None
        block_ref, fund, category, auth_creditors, block_id = (
            None,
            None,
            None,
            None,
            None,
        )

        type_id_auth_creditors = get_id_from_key_table(csr, "type", AUTH_CREDITORS)
        type_id_available_funds = get_id_from_key_table(csr, "type", AVAILABLE_FUNDS)
        type_id_sc_fund = get_id_from_key_table(csr, "type", SC_FUND)

        for i in range(0, qube_eod_balances_df.shape[0]):
            property_code_or_fund = qube_eod_balances_df.iloc[i]["PropertyCode / Fund"]
            property_name_or_category = qube_eod_balances_df.iloc[i][
                "PropertyName / Category"
            ]

            try_property_ref, try_block_ref, _ = getPropertyBlockAndTenantRefs(
                property_code_or_fund
            )
            if try_property_ref and try_block_ref:
                found_property = True
                property_ref = try_property_ref
                block_ref = try_block_ref
                block_name = property_name_or_category
            elif found_property:
                if property_code_or_fund in [
                    "Service Charge",
                    "Rent",
                    "Tenant Recharge",
                    "Admin Fund",
                    "Reserve",
                ]:
                    fund = property_code_or_fund
                    category = property_name_or_category
                    fund_id = get_id_from_key_table(csr, "fund", fund)
                    category_id = get_id_from_key_table(csr, "category", category)

                    auth_creditors = qube_eod_balances_df.iloc[i][AUTH_CREDITORS]
                    available_funds = qube_eod_balances_df.iloc[i][AVAILABLE_FUNDS]
                    sc_fund = calculateSCFund(
                        auth_creditors, available_funds, property_ref, block_ref
                    )

                    # charges[property_ref][block_ref][fund][category][AUTH_CREDITORS] = auth_creditors
                    # charges[property_ref][block_ref][fund][category][AVAILABLE_FUNDS] = available_funds
                    # charges[property_ref][block_ref][fund][category][SC_FUND] = sc_fund

                    # If the property exists then add the block if it doesn't exist,
                    # otherwise find the existing block ID. This adds the xxx-00 estate references.
                    property_id = get_id_from_ref(
                        csr, "Properties", "property", property_ref
                    )
                    if property_id:
                        block_id = get_id_from_ref(csr, "Blocks", "block", block_ref)
                        if not block_id:
                            if block_ref[-2:] == "00":
                                block_type = "P"
                            else:
                                block_type = "B"
                            csr.execute(
                                INSERT_BLOCK_SQL, (block_ref, block_type, property_id)
                            )
                            logger.debug(f"\tAdding block {block_ref}")
                            block_id = get_id_from_ref(
                                csr, "Blocks", "block", block_ref
                            )

                    if block_id:
                        # Update block name
                        if not get_id(csr, SELECT_BLOCK_NAME_SQL, (block_ref,)):
                            csr.execute(UPDATE_BLOCK_NAME_SQL, (block_name, block_id))
                            logger.debug(
                                f"\tAdding block name {block_name} for block reference {block_ref}"
                            )

                        # Add available funds charge
                        charges_id = get_id(
                            csr,
                            SELECT_CHARGES_SQL,
                            (
                                fund_id,
                                category_id,
                                type_id_available_funds,
                                block_id,
                                at_date,
                            ),
                        )
                        if not charges_id:
                            csr.execute(
                                INSERT_CHARGES_SQL,
                                (
                                    fund_id,
                                    category_id,
                                    type_id_available_funds,
                                    at_date,
                                    available_funds,
                                    block_id,
                                ),
                            )
                            logger.debug(
                                "\tAdding charge {}".format(
                                    str(
                                        (
                                            fund,
                                            category,
                                            AVAILABLE_FUNDS,
                                            at_date,
                                            block_ref,
                                            available_funds,
                                        )
                                    )
                                )
                            )
                            num_charges_added_to_db += 1

                        if property_code_or_fund in [
                            "Service Charge",
                            "Tenant Recharge",
                        ]:
                            # Add auth creditors charge
                            charges_id = get_id(
                                csr,
                                SELECT_CHARGES_SQL,
                                (
                                    fund_id,
                                    category_id,
                                    type_id_auth_creditors,
                                    block_id,
                                    at_date,
                                ),
                            )
                            if not charges_id:
                                csr.execute(
                                    INSERT_CHARGES_SQL,
                                    (
                                        fund_id,
                                        category_id,
                                        type_id_auth_creditors,
                                        at_date,
                                        auth_creditors,
                                        block_id,
                                    ),
                                )
                                logger.debug(
                                    "\tAdding charge for {}".format(
                                        str(
                                            (
                                                fund,
                                                category,
                                                AUTH_CREDITORS,
                                                at_date,
                                                block_ref,
                                                auth_creditors,
                                            )
                                        )
                                    )
                                )
                                num_charges_added_to_db += 1

                            # Add SC Fund charge
                            charges_id = get_id(
                                csr,
                                SELECT_CHARGES_SQL,
                                (
                                    fund_id,
                                    category_id,
                                    type_id_sc_fund,
                                    block_id,
                                    at_date,
                                ),
                            )
                            if not charges_id:
                                csr.execute(
                                    INSERT_CHARGES_SQL,
                                    (
                                        fund_id,
                                        category_id,
                                        type_id_sc_fund,
                                        at_date,
                                        sc_fund,
                                        block_id,
                                    ),
                                )
                                logger.debug(
                                    "\tAdding charge for {}".format(
                                        str(
                                            (
                                                fund,
                                                category,
                                                SC_FUND,
                                                at_date,
                                                block_ref,
                                                sc_fund,
                                            )
                                        )
                                    )
                                )
                                num_charges_added_to_db += 1
                    else:
                        logger.warning(
                            f"Cannot determine the block for the Qube balances from block reference {block_ref}"
                        )

                elif property_code_or_fund == "Property Totals":
                    found_property = False
            else:
                pass
                # logger.info(f"Ignoring data with block reference '{property_code_or_fund}'")

        csr.execute("end")
        db_conn.commit()
        logger.info(f"{num_charges_added_to_db} charges added to the database.")
    except db_conn.Error as err:
        logger.error(str(err))
        logger.error(
            "The data which caused the failure is: "
            + str((block_ref, fund, category, at_date, auth_creditors, block_id))
        )
        logger.error("No Qube balances have been added to the database.")
        logger.exception(err)
        csr.execute("rollback")
        # charges = {}
    except Exception as ex:
        logger.error(str(ex))
        logger.error(
            "The data which caused the failure is: "
            + str((block_ref, fund, category, at_date, auth_creditors, block_id))
        )
        logger.error("No Qube balances have been added to the database.")
        logger.exception(ex)
        csr.execute("rollback")
        # charges = {}
    # return charges


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

    irregular_transaction_refs_file_pattern = os.path.join(
        get_wpp_input_dir(), "001 GENERAL CREDITS CLIENTS WITHOUT IDENTS.xlsx"
    )
    irregular_transaction_refs_file = getLatestMatchingFileName(
        irregular_transaction_refs_file_pattern
    )
    if irregular_transaction_refs_file:
        logger.info(
            f"Importing irregular transaction references from file {irregular_transaction_refs_file}"
        )
        importIrregularTransactionReferences(db_conn, irregular_transaction_refs_file)
    else:
        logger.error(
            f"Cannot find irregular transaction references file matching {irregular_transaction_refs_file_pattern}"
        )
    logger.info("")

    properties_file_pattern = os.path.join(get_wpp_input_dir(), "Properties*.xlsx")
    tenants_file_pattern = os.path.join(get_wpp_input_dir(), "Tenants*.xlsx")
    properties_xls_file = getLatestMatchingFileName(
        properties_file_pattern
    ) or getLatestMatchingFileName(tenants_file_pattern)
    if properties_xls_file:
        logger.info(f"Importing Properties from file {properties_xls_file}")
        importPropertiesFile(db_conn, properties_xls_file)
    else:
        logger.error(f"Cannot find Properties file matching {properties_file_pattern}")
    logger.info("")

    estates_file_pattern = os.path.join(get_wpp_input_dir(), "Estates*.xlsx")
    estates_xls_file = getLatestMatchingFileName(estates_file_pattern)
    if estates_xls_file:
        logger.info(f"Importing Estates from file {estates_xls_file}")
        importEstatesFile(db_conn, estates_xls_file)
    else:
        logger.error(f"Cannot find Estates file matching {estates_file_pattern}")
    logger.info("")

    qube_eod_balances_file_pattern = os.path.join(get_wpp_input_dir(), "Qube*EOD*.xlsx")
    qube_eod_balances_files = getMatchingFileNames(qube_eod_balances_file_pattern)
    if qube_eod_balances_files:
        for qube_eod_balances_file in qube_eod_balances_files:
            logger.info(f"Importing Qube balances from file {qube_eod_balances_file}")
            importQubeEndOfDayBalancesFile(db_conn, qube_eod_balances_file)
    else:
        logger.error(
            f"Cannot find Qube EOD Balances file matching {qube_eod_balances_file_pattern}"
        )
    logger.info("")

    accounts_file_pattern = os.path.join(get_wpp_input_dir(), "Accounts.xlsx")
    accounts_file = getLatestMatchingFileName(accounts_file_pattern)
    if accounts_file:
        logger.info(f"Importing bank accounts from file {accounts_file}")
        importBankAccounts(db_conn, accounts_file)
    else:
        logger.error(
            f"ERROR: Cannot find account numbers file matching {accounts_file_pattern}"
        )
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
            logger.info(
                f"Importing Bank Account Transactions from file {bos_statement_xml_file}"
            )
            errors, duplicates = importBankOfScotlandTransactionsXMLFile(
                db_conn, bos_statement_xml_file
            )
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
        logger.error(
            f"Cannot find bank account transactions file matching {bos_statement_file_pattern}"
        )
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
            logger.info(
                f"Importing Bank Account balances from file {eod_balances_xml_file}"
            )
            importBankOfScotlandBalancesXMLFile(db_conn, eod_balances_xml_file)
    else:
        logger.error(
            "Cannot find bank account balances file matching one of {}".format(
                ",".join(eod_balances_file_patterns)
            )
        )
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

    start_time = time.time()

    # Get command line arguments
    args = get_args()
    print(args)

    os.makedirs(get_wpp_input_dir(), exist_ok=True)
    os.makedirs(get_wpp_report_dir(), exist_ok=True)

    logger.info(
        "Beginning Import of data into the database, at {}\n".format(
            dt.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    db_conn = get_or_create_db(get_wpp_db_file(), logger)
    importAllData(db_conn)

    elapsed_time = time.time() - start_time
    time.strftime("%S", time.gmtime(elapsed_time))

    logger.info("Done in {} seconds.".format(round(elapsed_time, 1)))
    logger.info(
        "----------------------------------------------------------------------------------------"
    )
    # input("Press enter to end.")


if __name__ == "__main__":
    main()
