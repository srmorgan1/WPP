import os

import pytest

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

# Define the database file for testing
TEST_DB_FILE = "/Users/steve/Development/PycharmProjects/WPP/tests/test_WPP_DB.db"


@pytest.fixture
def db_conn():
    # Setup: create a new database connection for testing
    conn = get_or_create_db(TEST_DB_FILE)
    yield conn
    # Teardown: close the database connection and remove the test database file
    conn.close()
    os.remove(TEST_DB_FILE)


def test_get_or_create_db(db_conn):
    assert os.path.exists(TEST_DB_FILE)


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
    id = get_id(cursor, "SELECT ID FROM Properties WHERE property_ref = 'test_ref';")
    assert id is not None


def test_get_id_from_ref(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO Properties (property_ref) VALUES ('test_ref');")
    id = get_id_from_ref(cursor, "Properties", "property", "test_ref")
    assert id is not None


def test_get_id_from_key_table(db_conn):
    cursor = db_conn.cursor()
    id = get_id_from_key_table(cursor, "fund", "test_value")
    assert id is not None


def test_importBankOfScotlandTransactionsXMLFile(db_conn):
    # Assuming a sample XML file exists for testing
    sample_xml_file = "/path/to/sample_transactions.xml"
    errors, duplicates = importBankOfScotlandTransactionsXMLFile(db_conn, sample_xml_file)
    assert len(errors) == 0
    assert len(duplicates) == 0


def test_importBankOfScotlandBalancesXMLFile(db_conn):
    # Assuming a sample XML file exists for testing
    sample_xml_file = "/path/to/sample_balances.xml"
    importBankOfScotlandBalancesXMLFile(db_conn, sample_xml_file)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM AccountBalances;")
    balances = cursor.fetchall()
    assert len(balances) > 0


def test_importPropertiesFile(db_conn):
    # Assuming a sample Excel file exists for testing
    sample_xls_file = "/path/to/sample_properties.xlsx"
    importPropertiesFile(db_conn, sample_xls_file)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM Properties;")
    properties = cursor.fetchall()
    assert len(properties) > 0


def test_importEstatesFile(db_conn):
    # Assuming a sample Excel file exists for testing
    sample_xls_file = "/path/to/sample_estates.xlsx"
    importEstatesFile(db_conn, sample_xls_file)
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
    sample_xls_file = "/path/to/sample_bank_accounts.xlsx"
    importBankAccounts(db_conn, sample_xls_file)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM Accounts;")
    accounts = cursor.fetchall()
    assert len(accounts) > 0


def test_importIrregularTransactionReferences(db_conn):
    # Assuming a sample Excel file exists for testing
    sample_xls_file = "/path/to/sample_irregular_refs.xlsx"
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
    sample_xls_file = "/path/to/sample_qube_eod_balances.xlsx"
    importQubeEndOfDayBalancesFile(db_conn, sample_xls_file)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM Charges;")
    charges = cursor.fetchall()
    assert len(charges) > 0


def test_add_misc_data_to_db(db_conn):
    add_misc_data_to_db(db_conn)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM Properties WHERE property_name IS NOT NULL;")
    properties = cursor.fetchall()
    assert len(properties) > 0


def test_importAllData(db_conn):
    importAllData(db_conn)
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM Properties;")
    properties = cursor.fetchall()
    assert len(properties) > 0
