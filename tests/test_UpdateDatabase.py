import os
from pathlib import Path

import pytest

from wpp.config import get_wpp_db_dir, get_wpp_input_dir, set_wpp_root_dir
from wpp.db import get_data
from wpp.UpdateDatabase import (
    add_misc_data_to_db,
    addBlockToDB,
    addPropertyToDB,
    addTenantToDB,
    calculateSCFund,
    get_id,
    get_id_from_key_table,
    get_id_from_ref,
    get_last_insert_id,
    get_or_create_db,
    get_single_value,
    importAllData,
    importBankAccounts,
    importBankOfScotlandBalancesXMLFile,
    importBankOfScotlandTransactionsXMLFile,
    importBlockBankAccountNumbers,
    importEstatesFile,
    importIrregularTransactionReferences,
    importPropertiesFile,
    importQubeEndOfDayBalancesFile,
)
from wpp.utils import getLatestMatchingFileName, getMatchingFileNames, open_file

# Define paths
SCRIPT_DIR = Path(__file__).resolve().parent
WPP_ROOT_DIR = SCRIPT_DIR / "Data"


@pytest.fixture
def setup_wpp_root_dir():
    # _clean_up_output_dirs()
    set_wpp_root_dir(str(WPP_ROOT_DIR))
    # Make output dirs
    # WPP_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    # WPP_LOG_DIR.mkdir(parents=True, exist_ok=True)
    # WPP_DB_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Teardown code
    # _clean_up_output_dirs()

@pytest.fixture
def db_file(setup_wpp_root_dir):
    # Define the database file for testing
    return Path(get_wpp_db_dir() / "test_WPP_DB.db")

@pytest.fixture
def db_conn(db_file):
    # Setup: create a new database connection for testing
    conn = get_or_create_db(db_file)
    yield conn
    # Teardown: close the database connection and remove the test database file
    conn.close()
    os.remove(db_file)


def test_get_or_create_db(db_conn, db_file):
    assert os.path.exists(db_file)


def test_create_and_index_tables(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    assert len(tables) > 0


def test_get_last_insert_id(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO Properties (property_ref) VALUES ('test_ref');")
    last_id = get_last_insert_id(cursor, "Properties")
    assert last_id is not None


def test_get_single_value(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO Properties (property_ref) VALUES ('test_ref');")
    value = get_single_value(cursor, "SELECT property_ref FROM Properties WHERE property_ref = 'test_ref';")
    assert value == "test_ref"


def test_get_data(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO Properties (property_ref) VALUES ('test_ref');")
    data = get_data(cursor, "SELECT property_ref FROM Properties;")
    assert len(data) > 0


def test_get_id(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO Properties (property_ref) VALUES ('test_ref');")
    _id = get_id(cursor, "SELECT ID FROM Properties WHERE property_ref = 'test_ref';")
    assert _id is not None


def test_get_id_from_ref(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO Properties (property_ref) VALUES ('test_ref');")
    _id = get_id_from_ref(cursor, "Properties", "property", "test_ref")
    assert _id is not None


def test_get_id_from_key_table(db_conn):
    cursor = db_conn.cursor()
    _id = get_id_from_key_table(cursor, "fund", "test_value")
    assert _id is not None


def test_importBankOfScotlandTransactionsXMLFile(db_conn):
    # Assuming a sample XML file exists for testing
    transactions_file_pattern = os.path.join(get_wpp_input_dir(), "PreviousDayTransactionExtract_*.zip")
    transactions_xml_filename = getLatestMatchingFileName(transactions_file_pattern)
    transactions_xml_file = open_file(transactions_xml_filename)
    errors, duplicates = importBankOfScotlandTransactionsXMLFile(db_conn, transactions_xml_file)
    assert len(errors) == 18
    assert len(duplicates) == 0


def test_importBankOfScotlandBalancesXMLFile(db_conn):
    # Assuming a sample XML file exists for testing
    eod_balances_file_pattern = os.path.join(get_wpp_input_dir(), "EndOfDayBalanceExtract_*.zip")
    eod_balances_xml_file = getLatestMatchingFileName(eod_balances_file_pattern)
    importBankOfScotlandBalancesXMLFile(db_conn, eod_balances_xml_file)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM AccountBalances;")
    balances = cursor.fetchall()
    assert len(balances) > 0


def test_importPropertiesFile(db_conn):
    # Assuming a sample Excel file exists for testing
    tenants_file_pattern = os.path.join(get_wpp_input_dir(), "Tenants*.xlsx")
    properties_xls_file = getLatestMatchingFileName(tenants_file_pattern)
    importPropertiesFile(db_conn, properties_xls_file)
    cursor = db_conn.cursor()
    cursor.execute("SELECT ID FROM Properties;")
    properties = cursor.fetchall()
    assert len(properties) == 136


def test_importEstatesFile(db_conn):
    # Assuming a sample Excel file exists for testing
    estates_file_pattern = os.path.join(get_wpp_input_dir(), "Estates*.xlsx")
    estates_xls_file = getLatestMatchingFileName(estates_file_pattern)
    importEstatesFile(db_conn, estates_xls_file)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM Properties WHERE property_name IS NOT NULL;")
    estates = cursor.fetchall()
    assert len(estates) > 0


def test_addPropertyToDB(db_conn):
    property_id = addPropertyToDB(db_conn, "test_ref")
    assert property_id is not None


def test_addBlockToDB(db_conn):
    addPropertyToDB(db_conn, "test_ref")
    block_id = addBlockToDB(db_conn, "test_ref", "test_block")
    assert block_id is not None


def test_addTenantToDB(db_conn):
    addPropertyToDB(db_conn, "test_ref")
    addBlockToDB(db_conn, "test_ref", "test_block")
    tenant_id = addTenantToDB(db_conn, "test_block", "test_tenant", "Test Tenant")
    assert tenant_id is not None


def test_importBlockBankAccountNumbers(db_conn):
    # Assuming a sample Excel file exists for testing
    sample_xls_file = "/path/to/sample_bank_accounts.xlsx"
    importBlockBankAccountNumbers(db_conn, sample_xls_file)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM Blocks WHERE account_number IS NOT NULL;")
    accounts = cursor.fetchall()
    assert len(accounts) > 0


def test_importBankAccounts(db_conn):
    # Assuming a sample Excel file exists for testing
    sample_xls_file_pattern = os.path.join(get_wpp_input_dir(), "sample_bank_accounts.xlsx")
    sample_xls_file = getLatestMatchingFileName(sample_xls_file_pattern)
    importBankAccounts(db_conn, sample_xls_file)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM Accounts;")
    accounts = cursor.fetchall()
    assert len(accounts) > 0


def test_importIrregularTransactionReferences(db_conn):
    # Assuming a sample Excel file exists for testing
    sample_xls_file_patttern = os.path.join(get_wpp_input_dir(), "sample_irregular_refs.xlsx")
    sample_xls_file = getLatestMatchingFileName(sample_xls_file_pattern)
    importIrregularTransactionReferences(db_conn, sample_xls_file)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM IrregularTransactionRefs;")
    refs = cursor.fetchall()
    assert len(refs) > 0


def test_calculateSCFund():
    result = calculateSCFund(100, 200, "035", "test_block")
    assert result == 200
    result = calculateSCFund(100, 200, "034", "test_block")
    assert result == 300


def test_importQubeEndOfDayBalancesFile(db_conn):
    # Assuming a sample Excel file exists for testing
    sample_xls_file_pattern = os.path.join(get_wpp_input_dir(), "Qube*EOD*.xlsx")
    sample_xls_file = getLatestMatchingFileName(sample_xls_file_pattern)
    importQubeEndOfDayBalancesFile(db_conn, sample_xls_file)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM Charges;")
    charges = cursor.fetchall()
    assert len(charges) > 0


@pytest.mark.skip("Skip")
def test_add_misc_data_to_db(db_conn):
    add_misc_data_to_db(db_conn)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM Properties WHERE property_name IS NOT NULL;")
    properties = cursor.fetchall()
    assert len(properties) > 0


@pytest.mark.skip("Skip")
def test_importAllData(db_conn):
    importAllData(db_conn)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM Properties;")
    properties = cursor.fetchall()
    assert len(properties) > 0
