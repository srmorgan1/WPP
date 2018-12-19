import xml.etree.ElementTree as et
from dateutil import parser
import sqlite3
import argparse
import pandas as pd
import numpy as np
from collections import defaultdict
from datetime import datetime
#from zipfile import ZipFile
import xlrd
import glob
import sys
import os
import re

# NB: This must be set to the correct location
WPP_ROOT_DIR = r'/Users/steve/Work/WPP'

WPP_INPUT_DIR = WPP_ROOT_DIR + '/Inputs'
WPP_LOG_DIR = WPP_ROOT_DIR + '/Logs'
WPP_DB_DIR = WPP_ROOT_DIR + '/Database'
WPP_DB_FILE = WPP_DB_DIR + r'/WPP_DB.db'
WPP_LOG_FILE = WPP_LOG_DIR + r'/Log_{}.txt'

CLIENT_CREDIT_ACCOUNT_NUMBER = '06000792'

#
# Tables
#
CREATE_PROPERTIES_TABLE = '''
CREATE TABLE Properties (
    ID               INTEGER PRIMARY KEY AUTOINCREMENT,
    property_ref     TEXT  NOT NULL,
    property_name     TEXT,
    number_of_blocks INTEGER
);
'''

CREATE_BLOCKS_TABLE = '''
CREATE TABLE Blocks (
    ID                INTEGER PRIMARY KEY AUTOINCREMENT,
    block_ref         TEXT NOT NULL,
    block_name        TEXT,
    type              TEXT,
    number_of_tenants INTEGER,
    property_id       INTEGER REFERENCES Properties (ID)
);
'''

CREATE_TENANTS_TABLE = '''
CREATE TABLE Tenants (
    ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_ref     TEXT NOT NULL,
    tenant_name    TEXT,
    service_charge DOUBLE,
    block_id       INTEGER REFERENCES Blocks (ID)
);
'''

CREATE_SUGGESTED_TENANTS_TABLE = '''
CREATE TABLE SuggestedTenants (
    ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id      INTEGER REFERENCES Tenants (ID),
    transaction_id INTEGER REFERENCES Transactions (ID) 
);
'''

CREATE_TRANSACTIONS_TABLE = '''
CREATE TABLE Transactions (
    ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    sort_code      TEXT  NOT NULL,
    account_number TEXT  NOT NULL,
    type           TEXT  NOT NULL,
    amount         DOUBLE  NOT NULL,
    description    TEXT,
    pay_date       DATE    NOT NULL,
    tenant_id      INTEGER REFERENCES Tenants (ID) 
);
'''

CREATE_CHARGES_TABLE = '''
CREATE TABLE Charges (
    ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id        INTEGER    NOT NULL,
    category_id    INTEGER    NOT NULL,
    type_id        INTEGER    NOT NULL,
    at_date        DATE    NOT NULL,
    amount         DOUBLE,
    block_id       INTEGER REFERENCES Blocks (ID)
);
'''

CREATE_ACCOUNTS_TABLE = '''
CREATE TABLE Accounts (
    ID                  INTEGER PRIMARY KEY AUTOINCREMENT,
    sort_code           TEXT  NOT NULL,
    account_number      TEXT  NOT NULL,
    account_type        TEXT,
    property_or_block   TEXT,
    client_ref          TEXT,
    account_name        TEXT  NOT NULL,
    block_id             INTEGER
);
'''

CREATE_ACCOUNT_BALANCES_TABLE = '''
CREATE TABLE AccountBalances (
    ID                  INTEGER PRIMARY KEY AUTOINCREMENT,
    current_balance     DOUBLE NOT NULL,
    available_balance   DOUBLE NOT NULL,
    at_date             DATE NOT NULL,
    account_id          INTEGER REFERENCES Accounts (ID)
);
'''

CREATE_IRREGULAR_TRANSACTION_REFS_TABLE = '''
CREATE TABLE IrregularTransactionRefs (
    ID                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_ref     TEXT NOT NULL,
    tenant_ref          TEXT NOT NULL
);
'''

CREATE_KEY_TABLE = '''
CREATE TABLE Key_{} (
    ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    value          TEXT
);
'''

#
# Indices
#
CREATE_PROPERTIES_INDEX = '''
CREATE UNIQUE INDEX Index_Properties ON Properties (
    property_ref,
    property_name,
    number_of_blocks
);
'''

CREATE_BLOCKS_INDEX = '''
CREATE UNIQUE INDEX Index_Blocks ON Blocks (
    block_ref,
    property_id,
    block_name,
    type,
    number_of_tenants
);
'''

CREATE_TENANTS_INDEX = '''
CREATE UNIQUE INDEX Index_Tenants ON Tenants (
    tenant_ref,
    block_id,
    tenant_name
);
'''

CREATE_SUGGESTED_TENANTS_INDEX = '''
CREATE UNIQUE INDEX Index_SuggestedTenants ON SuggestedTenants (
    tenant_id,
    transaction_id
);
'''

CREATE_TRANSACTIONS_INDEX = '''
CREATE UNIQUE INDEX Index_Transactions ON Transactions (
    tenant_id,
    description,
    pay_date,
    sort_code,
    account_number,
    type,
    amount
);
'''

CREATE_CHARGES_INDEX = '''
CREATE UNIQUE INDEX Index_Charges ON Charges (
    block_id,
    fund_id,
    category_id,
    type_id,
    at_date
);
'''

CREATE_ACCOUNTS_INDEX = '''
CREATE UNIQUE INDEX Index_Accounts ON Accounts (
    block_id,
    sort_code,
    account_number,
    account_type,
    property_or_block,
    account_name,
    client_ref
);
'''

CREATE_ACCOUNT_BALANCES_INDEX = '''
CREATE UNIQUE INDEX Index_AccountBalances ON AccountBalances (
    account_id,
    at_date,
    current_balance,
    available_balance
);
'''

CREATE_IRREGULAR_TRANSACTION_REFS_INDEX = '''
CREATE UNIQUE INDEX Index_IrregularTransactionRefs ON IrregularTransactionRefs (
    transaction_ref,
    tenant_ref
);
'''

CREATE_KEY_INDEX = '''
CREATE UNIQUE INDEX Index_Key_{0} ON Key_{0} (
    value
);
'''

#
# SQL
#
INSERT_PROPERTY_SQL = "INSERT INTO Properties (property_ref, property_name, number_of_blocks) VALUES (?, Null, 0);"
INSERT_BLOCK_SQL = "INSERT INTO Blocks (block_ref, block_name, type, number_of_tenants, property_id) VALUES (?, Null, ?, 0, ?);"
INSERT_TENANT_SQL = "INSERT INTO Tenants (tenant_ref, tenant_name, block_id) VALUES (?, ?, ?);"
INSERT_SUGGESTED_TENANT_SQL = "INSERT INTO SuggestedTenants (tenant_id, transaction_id) VALUES (?, ?);"
INSERT_TRANSACTION_SQL = "INSERT INTO Transactions (sort_code, account_number, type, amount, description, pay_date, tenant_id) VALUES (?, ?, ?, ?, ?, ?, ?);"
INSERT_CHARGES_SQL = "INSERT INTO Charges (fund_id, category_id, type_id, at_date, amount, block_id) VALUES (?, ?, ?, ?, ?, ?);"
INSERT_BANK_ACCOUNT_SQL = "INSERT INTO Accounts (sort_code, account_number, account_type, property_or_block, client_ref, account_name, block_id) VALUES (?, ?, ?, ?, ?, ?, ?)"
INSERT_BANK_ACCOUNT_BALANCE_SQL = "INSERT INTO AccountBalances (current_balance, available_balance, at_date, account_id) VALUES (?, ?, ?, ?)"
INSERT_KEY_TABLE_SQL = "INSERT INTO Key_{} (value) VALUES (?);"

SELECT_TENANT_ID_SQL = "SELECT tenant_id FROM Tenants WHERE tenant_ref = ?;"
SELECT_LAST_RECORD_ID_SQL = "SELECT seq FROM sqlite_sequence WHERE name = ?;"
SELECT_ID_FROM_REF_SQL = "SELECT ID FROM {} WHERE {}_ref = '{}';"
SELECT_ID_FROM_KEY_TABLE_SQL = "SELECT ID FROM Key_{} WHERE value = ?;"
SELECT_TRANSACTION_SQL = "SELECT ID FROM Transactions WHERE tenant_id = ? AND description = ? AND pay_date = ? AND sort_code = ? and account_number = ? and type = ? AND amount between (?-0.005) and (?+0.005);"
SELECT_CHARGES_SQL = "SELECT ID FROM Charges WHERE fund_id = ? AND category_id = ? and type_id = ? and block_id = ? and at_date = ?;"
SELECT_BANK_ACCOUNT_SQL = "SELECT ID FROM Blocks WHERE ID = ? AND account_number IS Null;"
SELECT_BANK_ACCOUNT_SQL1 = "SELECT ID FROM Accounts WHERE sort_code = ? AND account_number = ?;"
SELECT_BANK_ACCOUNT_BALANCE_SQL = "SELECT ID FROM AccountBalances WHERE at_date = ? AND account_id = ?;"
SELECT_TENANT_NAME_SQL = "SELECT tenant_name FROM Tenants WHERE tenant_ref = ?;"
SELECT_BLOCK_NAME_SQL = "SELECT block_name FROM Blocks WHERE block_ref = ?;"
SELECT_IRREGULAR_TRANSACTION_TENANT_REF_SQL = "select tenant_ref, transaction_ref from IrregularTransactionRefs where instr(?, transaction_ref) > 0;"

UPDATE_BLOCK_ACCOUNT_NUMBER_SQL = "UPDATE Blocks SET account_number = ? WHERE ID = ? AND account_number IS Null;"
UPDATE_PROPERTY_DETAILS_SQL = "UPDATE Properties SET property_name = ? WHERE property_ref = ?;"
UPDATE_BLOCK_NAME_SQL = "UPDATE Blocks SET block_name = ? WHERE ID = ?;"

# Charge types
AUTH_CREDITORS = 'Auth Creditors'
AVAILABLE_FUNDS = 'Available Funds'
SC_FUND = 'SC Fund'

# Regular expressions
PBT_REGEX = re.compile(r'(?:^|\s+|,)(\d\d\d)-(\d\d)-(\d\d\d)(?:$|\s+|,)')
PBT_REGEX_NO_TERMINATING_SPACE = re.compile(r'(?:^|\s+|,)(\d\d\d)-(\d\d)-(\d\d\d)(?:$|\s*|,)')
PBT_REGEX_SPECIAL_CASES = re.compile(r'(?:^|\s+|,)(\d\d\d)-(\d\d)-(\w{2,5})(?:$|\s+|,)', re.ASCII)
PBT_REGEX_NO_HYPHENS = re.compile(r'(?:^|\s+|,)(\d\d\d)\s{0,1}(\d\d)\s{0,1}(\d\d\d)(?:$|\s+|,)')
PT_REGEX = re.compile(r'(?:^|\s+|,)(\d\d\d)-(\d\d\d)(?:$|\s+|,)')
PB_REGEX = re.compile(r'(?:^|\s+|,)(\d\d\d)-(\d\d)(?:$|\s+|,)')
P_REGEX = re.compile(r'(?:^|\s+)(\d\d\d)(?:$|\s+)')

def log(*args, **kwargs):
    today = datetime.today()
    log_file = WPP_LOG_FILE.format(today.strftime('%Y-%m-%d'))
    with open(log_file, 'a+') as lf:
        print(*args, **kwargs, file=lf)


def print_and_log(*args, **kwargs):
    print(*args, **kwargs)
    log(*args, **kwargs)


def get_or_create_db(db_file):
    init_db = not os.path.exists(db_file)
    os.makedirs(WPP_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(db_file)
    if init_db:
        create_and_index_tables(conn)
    return conn


def get_last_insert_id(db_cursor, table_name):
    db_cursor.execute(SELECT_LAST_RECORD_ID_SQL, (table_name,))
    id = db_cursor.fetchone()
    if id:
        return id[0]
    else:
        return None


def get_single_value(db_cursor, sql, args_tuple):
    db_cursor.execute(sql, args_tuple)
    value = db_cursor.fetchone()
    if value:
        return value[0]
    else:
        return None


def get_data(db_cursor, sql, args_tuple):
    db_cursor.execute(sql, args_tuple)
    values = db_cursor.fetchall()
    return values if values else None


def get_id(db_cursor, sql, args_tuple):
    return get_single_value(db_cursor, sql, args_tuple)


def get_id_from_ref(db_cursor, table_name, field_name, ref_name):
    sql = SELECT_ID_FROM_REF_SQL.format(table_name, field_name, ref_name)
    db_cursor.execute(sql)
    id = db_cursor.fetchone()
    if id:
        return id[0]
    else:
        return None


def get_id_from_key_table(db_cursor, key_table_name, value):
    sql = SELECT_ID_FROM_KEY_TABLE_SQL.format(key_table_name)
    db_cursor.execute(sql, (value,))
    id = db_cursor.fetchone()
    if id:
        return id[0]
    else:
        sql = INSERT_KEY_TABLE_SQL.format(key_table_name)
        db_cursor.execute(sql, (value,))
        return get_last_insert_id(db_cursor, 'Key_{}'.format(key_table_name))


def create_and_index_tables(db_conn):
    try:
        csr = db_conn.cursor()
        csr.execute('begin')

        # Create tables
        csr.execute(CREATE_PROPERTIES_TABLE)
        csr.execute(CREATE_BLOCKS_TABLE)
        csr.execute(CREATE_TENANTS_TABLE)
        csr.execute(CREATE_TRANSACTIONS_TABLE)
        csr.execute(CREATE_CHARGES_TABLE)
        csr.execute(CREATE_ACCOUNTS_TABLE)
        csr.execute(CREATE_ACCOUNT_BALANCES_TABLE)
        csr.execute(CREATE_SUGGESTED_TENANTS_TABLE)
        csr.execute(CREATE_IRREGULAR_TRANSACTION_REFS_TABLE)
        csr.execute(CREATE_KEY_TABLE.format('fund'))
        csr.execute(CREATE_KEY_TABLE.format('category'))
        csr.execute(CREATE_KEY_TABLE.format('type'))

        # Create indices
        csr.execute(CREATE_PROPERTIES_INDEX)
        csr.execute(CREATE_BLOCKS_INDEX)
        csr.execute(CREATE_TENANTS_INDEX)
        csr.execute(CREATE_TRANSACTIONS_INDEX)
        csr.execute(CREATE_CHARGES_INDEX)
        csr.execute(CREATE_ACCOUNTS_INDEX)
        csr.execute(CREATE_ACCOUNT_BALANCES_INDEX)
        csr.execute(CREATE_SUGGESTED_TENANTS_INDEX)
        csr.execute(CREATE_IRREGULAR_TRANSACTION_REFS_INDEX)
        csr.execute(CREATE_KEY_INDEX.format('fund'))
        csr.execute(CREATE_KEY_INDEX.format('category'))
        csr.execute(CREATE_KEY_INDEX.format('type'))
        csr.execute('end')
        db_conn.commit()
    except db_conn.Error as err:
        print_and_log(err)
        csr.execute('rollback')
        sys.exit(1)


def getMatchingFiles(file_paths):
    files = []
    if not isinstance(file_paths, list):
        file_paths = [file_paths]

    for file_path in file_paths:
        files.extend(glob.glob(file_path))
    return sorted(files, key=os.path.getctime)


def getLatestMatchingFile(file_path):
    files = glob.glob(file_path)
    if files:
        return max(files ,key=os.path.getctime)
    else:
        return None


def getLatestMatchingFileInDir(wpp_dir, file_name_glob):
    files = glob.glob(os.path.join(wpp_dir, file_name_glob))
    if files:
        return max(files ,key=os.path.getctime)
    else:
        return None


def getLongestCommonSubstring(string1, string2):
    answer = ''
    len1, len2 = len(string1), len(string2)
    for i in range(len1):
        for j in range(len2):
            lcs_temp=0
            match=''
            while ((i+lcs_temp < len1) and (j+lcs_temp<len2) and string1[i+lcs_temp] == string2[j+lcs_temp]):
                match += string2[j+lcs_temp]
                lcs_temp+=1
            if (len(match) > len(answer)):
                answer = match
    return answer


def checkTenantExists(db_cursor, tenant_ref):
    tenant_name = get_single_value(db_cursor, SELECT_TENANT_NAME_SQL, (tenant_ref,))
    return tenant_name


def matchTransactionRef(tenant_name, transaction_reference):
    if tenant_name:
        lcss = getLongestCommonSubstring(tenant_name.lower(), transaction_reference.lower())
        # Assume that if the transaction reference has a substring matching
        # one in the tenant name of >= 4 chars, then this is a match.
        return len(lcss) >= 4
    else:
        return False


def recodeSpecialReferenceCases(property_ref, block_ref, tenant_ref):
    # Block 020-03 belongs to a different property group, call this 020A.
    if property_ref == '020' and block_ref == '020-03':
        property_ref = '020A'
    # Remove 'DC' from parsed tenant references paid by debit card
    if tenant_ref is not None and tenant_ref[-2:] == 'DC':
        tenant_ref = tenant_ref[:-2]
    return property_ref, block_ref, tenant_ref


def getPropertyBlockAndTenantRefsFromRegexMatch(match):
    property_ref, block_ref, tenant_ref = None, None, None
    if match:
        property_ref = match.group(1)
        block_ref = '{}-{}'.format(match.group(1), match.group(2))
        tenant_ref = '{}-{}-{}'.format(match.group(1), match.group(2), match.group(3))
    return property_ref, block_ref, tenant_ref


def getPropertyBlockAndTenantRefs(reference, db_cursor = None):
    description = str(reference)
    property_ref, block_ref, tenant_ref = None, None, None

    if type(reference) != str:
        return None, None, None

    # Try to match property, block and tenant
    match = re.search(PBT_REGEX, description)
    if match:
        property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
    else:
        # Try to match property, block and tenant special cases
        match = re.search(PBT_REGEX_SPECIAL_CASES, description)
        if match:
            property_ref = match.group(1)
            if (property_ref in ['094', '095', '096', '099', '124']) or (property_ref in ['020', '022', '039', '053', '064'] and match.group(3)[-1] != 'Z'):
                block_ref = '{}-{}'.format(match.group(1), match.group(2))
                tenant_ref = '{}-{}-{}'.format(match.group(1), match.group(2), match.group(3))
            else:
                property_ref = None
        else:
            match = re.search(PB_REGEX, description)
            if match:
                property_ref = match.group(1)
                block_ref = '{}-{}'.format(match.group(1), match.group(2))
            else:
                match = re.search(PT_REGEX, description)
                if match:
                    pass
                    #property_ref = match.group(1)
                    #tenant_ref = match.group(2)  # Non-unique tenant ref, may be useful
                    # block_ref = '01'   # Null block indicates that the tenant and block can't be matched uniquely
                else:
                    # Match without hyphens, or with no terminating space.
                    # These cases can only come from parsed transaction references.
                    # in which case we can double check that the data exists in and matches the database
                    match = re.search(PBT_REGEX_NO_HYPHENS, description)
                    if match:
                        property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
                    else:
                        match = re.search(PBT_REGEX_NO_TERMINATING_SPACE, description)
                        if match:
                            property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)

                    if match and db_cursor:
                        tenant_name = checkTenantExists(db_cursor, tenant_ref)
                        if tenant_name:
                            if not matchTransactionRef(tenant_name, reference): return None, None, None
                        else:
                            return None, None, None
                    else:
                        # Match property reference only
                        match = re.search(P_REGEX, description)
                        if match:
                            property_ref = match.group(1)
                        else:
                            # Last resort - look for known irregular transaction refs which we know some tenants use
                            if db_cursor:
                                tenant_ref = get_single_value(db_cursor, SELECT_IRREGULAR_TRANSACTION_TENANT_REF_SQL, (reference,))
                                return getPropertyBlockAndTenantRefs(tenant_ref)
                            else:
                                return None, None, None

    # Ignore some property and tenant references, and recode special cases
    # #e.g. Block 020-03 belongs to a different property than the other 020-xx blocks.
    if tenant_ref is not None and ('Z' in tenant_ref or 'Y' in tenant_ref): return None, None, None
    elif property_ref is not None and property_ref.isnumeric() and int(property_ref) >= 900: return None, None, None
    property_ref, block_ref, tenant_ref = recodeSpecialReferenceCases(property_ref, block_ref, tenant_ref)
    return property_ref, block_ref, tenant_ref


def getTenantID(csr, tenant_ref):
    #sql = SELECT_TENANT_ID_SQL.format(tenant_ref)
    result = csr.execute(SELECT_TENANT_ID_SQL, (tenant_ref))


def importBankOfScotlandTransactionsXMLFile(db_conn, transactions_xml_file):
    with open(transactions_xml_file) as f:
        xml = f.read()
        xml = xml.replace(' xmlns="https://isite.bankofscotland.co.uk/Schemas/PreviousDayTransactionExtract.xsd"', '')
    tree = et.fromstring(xml)

    num_transactions_added_to_db = 0
    tenant_id = None

    try:
        csr = db_conn.cursor()
        csr.execute('begin')
        for transaction in tree.iter('TransactionRecord'):
            sort_code = transaction.find('SortCode').text
            account_number = transaction.find('AccountNumber').text
            transaction_type = transaction.find('TransactionType').text
            amount = transaction.find('TransactionAmount').text
            description = transaction.find('TransactionDescription').text
            pay_date = transaction.find('TransactionPostedDate').text
            pay_date = parser.parse(pay_date).strftime('%Y-%m-%d')

            # Only load transactions from the client credit account
            if account_number != CLIENT_CREDIT_ACCOUNT_NUMBER: continue

            # Parse the description field to determine the property, block and tenant that it belongs to
            property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefs(description, csr)

            # If uniquely identified the property, block and tenant, save in the DB
            if tenant_ref:
                if property_ref and block_ref:
                    tenant_id = get_id_from_ref(csr, 'Tenants', 'tenant', tenant_ref)
                    transaction_id = get_id(csr, SELECT_TRANSACTION_SQL, (tenant_id, description, pay_date, sort_code, account_number, transaction_type, amount, amount))
                    if not transaction_id:
                        csr.execute(INSERT_TRANSACTION_SQL, (sort_code, account_number, transaction_type, amount, description, pay_date, tenant_id))
                        log("\tAdding transaction {}".format(str((sort_code, account_number, transaction_type, amount, description, pay_date, tenant_ref))))
                        num_transactions_added_to_db += 1
                #elif property_ref:
                    # TODO: check if the property only has one block, if so we set block_ref to '01' and upload.
                    # TODO: else check if there is only one property with this tenant ref. If so, we then know the block and can upload (at least as a suggestion)
                    #pass
            #elif property_ref or (property_ref and block_ref):
                # TODO: try to make some kind of match from the description against the tenant name, and save
                # them in the suggested tenant references table
                # If we can't match anything, list all of the possible tenants that have not had a transaction allocated this month?
                # Maybe the last part should go in the report script
                #pass
            else:
                log("\tWARNING: cannot determine tenant from description '{}'. Ignoring transaction {}".format(
                    description, str((sort_code, account_number, transaction_type, amount, description, pay_date))))

        csr.execute('end')
        db_conn.commit()
        print_and_log("{} Bank Of Scotland transactions added to the database.".format(num_transactions_added_to_db))
    except db_conn.Error as err:
        print_and_log('ERROR: ' + str(err))
        print_and_log('The data which caused the failure is: ' + str((sort_code, account_number, transaction_type, amount, description, pay_date, tenant_id)))
        print_and_log('No Bank Of Scotland transactions have been added to the database.')
        csr.execute('rollback')
    except Exception as ex:
        print_and_log('ERROR: ' + str(ex))
        print_and_log('The data which caused the failure is: ' + str((sort_code, account_number, transaction_type, amount, description, pay_date, tenant_id)))
        print_and_log('No Bank Of Scotland transactions have been added to the database.')
        csr.execute('rollback')


def importBankOfScotlandBalancesXMLFile(db_conn, balances_xml_file):
    with open(balances_xml_file) as f:
        xml = f.read()
        xml = xml.replace('\n', '')
        xml = xml.replace(" xmlns='https://isite.bankofscotland.co.uk/Schemas/BalanceDetailedReport.xsd'", '')
    tree = et.fromstring(xml)

    num_balances_added_to_db = 0
    #accounts = []

    try:
        csr = db_conn.cursor()
        csr.execute('begin')
        for reporting_day in tree.iter('ReportingDay'):
            at_date = reporting_day.find('Date').text
            at_date = parser.parse(at_date).strftime('%Y-%m-%d')
            for balance in reporting_day.iter('BalanceRecord'):
                sort_code = balance.find('SortCode').text
                account_number = balance.find('AccountNumber').text
                client_ref = balance.find('ClientRef').text
                account_name = balance.find('LongName').text
                account_type = ''
                if client_ref and 'RENT' in client_ref.upper(): account_type = 'GR'
                elif client_ref and 'BANK' in client_ref.upper(): account_type = 'CL'
                elif client_ref and 'RES' in client_ref.upper(): account_type = 'RE'
                elif client_ref: raise ValueError('Cannot determine account type from client reference {}'.format(client_ref))

                current_balance = balance.find('CurrentBalance').text
                available_balance = balance.find('AvailableBalance').text

                if sort_code and account_number:
                    account_id = get_id(csr, SELECT_BANK_ACCOUNT_SQL1, (sort_code, account_number))
                    if account_id:
                        account_balance_id = get_id(csr, SELECT_BANK_ACCOUNT_BALANCE_SQL, (at_date, account_id))
                        if not account_balance_id:
                            csr.execute(INSERT_BANK_ACCOUNT_BALANCE_SQL, (current_balance, available_balance, at_date, account_id))
                            log("\tAdding bank balance {}".format(str((sort_code, account_number, account_type, client_ref, account_name, at_date, current_balance, available_balance))))
                            num_balances_added_to_db += 1
                    else:
                        pass
                        #accounts.append((sort_code, account_number, account_type, 'Block', client_ref, account_name))
                else:
                    log("\tWARNING: cannot determine bank account. Ignoring balance record {}".format(
                        str((sort_code, account_number, account_type, client_ref, account_name, at_date, current_balance, available_balance))))

        csr.execute('end')
        db_conn.commit()
        print_and_log("{} Bank Of Scotland account balances added to the database.".format(num_balances_added_to_db))

        #accounts_df = pd.DataFrame(accounts, columns=['Sort Code', 'Account Number', 'Account Type', 'PropertyOrBlock', 'Client Reference', 'Account Name'])
        #ef = WPP_INPUT_DIR + r'/accounts_temp.xlsx'
        #excel_writer = pd.ExcelWriter(ef, engine='xlsxwriter')
        #accounts_df.to_excel(excel_writer, index=False)
        #excel_writer.close()
    except db_conn.Error as err:
        print_and_log('ERROR: ' + str(err))
        print_and_log('The data which caused the failure is: ' + str((sort_code, account_number, account_type, client_ref, account_name, at_date, current_balance, available_balance)))
        print_and_log('No Bank Of Scotland account balances have been added to the database.')
        csr.execute('rollback')
    except Exception as ex:
        print_and_log('ERROR: ' + str(ex))
        print_and_log('The data which caused the failure is: ' + str((sort_code, account_number, account_type, client_ref, account_name, at_date, current_balance, available_balance)))
        print_and_log('No Bank Of Scotland account balances have been added to the database.')
        csr.execute('rollback')
        charges = {}


def importPropertiesFile(db_conn, properties_xls_file):
    # Read Excel spreadsheet into dataframe
    properties_df = pd.read_excel(properties_xls_file)

    num_properties_added_to_db = 0
    num_blocks_added_to_db = 0
    num_tenants_added_to_db = 0

    # Import into DB
    try:
        csr = db_conn.cursor()
        csr.execute('begin')
        for index, row in properties_df.iterrows():
            reference = row['Reference']
            tenant_name = row['Name']
            # If the property reference begins with a '9' or contains a 'Y' or 'Z',then ignore this data
            if reference is None or reference[0] == '9' or 'Y' in reference.upper() or 'Z' in reference.upper(): continue
            property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefs(reference)
            if (property_ref, block_ref, tenant_ref) == (None, None, None):
                log('\tINFO: will not add tenant with reference {}'.format(reference))
                continue
            property_id = get_id_from_ref(csr, 'Properties', 'property', property_ref)
            if not property_id:
                csr.execute(INSERT_PROPERTY_SQL, (property_ref,))
                log("\tAdding property {}".format(property_ref))
                num_properties_added_to_db += 1
                property_id = get_last_insert_id(csr, 'Properties')

            block_id = get_id_from_ref(csr, 'Blocks', 'block', block_ref)
            if not block_id:
                if block_ref[-2:] == '00':
                    block_type = 'P'
                else:
                    block_type = 'B'
                csr.execute(INSERT_BLOCK_SQL, (block_ref, block_type, property_id))
                log("\tAdding block {}".format(block_ref))
                num_blocks_added_to_db += 1
                block_id = get_last_insert_id(csr, 'Blocks')

            tenant_id = get_id_from_ref(csr, 'Tenants', 'tenant', tenant_ref)
            if not tenant_id:
                csr.execute(INSERT_TENANT_SQL, (tenant_ref, tenant_name, block_id))
                log("\tAdding tenant {}".format(tenant_ref))
                num_tenants_added_to_db += 1
        csr.execute('end')
        db_conn.commit()
        print_and_log("{} properties added to the database.".format(num_properties_added_to_db))
        print_and_log("{} blocks added to the database.".format(num_blocks_added_to_db))
        print_and_log("{} tenants added to the database.".format(num_tenants_added_to_db))
    except db_conn.Error as err:
        print_and_log('ERROR: ' + str(err))
        print_and_log('The data which caused the failure is: ' + str((reference, property_ref, block_ref, tenant_ref)))
        print_and_log('No properties, blocks or tenants have been added to the database')
        csr.execute('rollback')
    except Exception as ex:
        print_and_log('ERROR: ' + str(ex))
        print_and_log('The data which caused the failure is: ' + str((reference, property_ref, block_ref, tenant_ref)))
        print_and_log('No properties, blocks or tenants have been added to the database.')
        csr.execute('rollback')
        charges = {}


def addPropertyToDB(db_conn, property_ref, rethrow_exception = False):
    property_id = None
    try:
        csr = db_conn.cursor()
        csr.execute('begin')

        if property_ref:
            property_id = get_id_from_ref(csr, 'Properties', 'property', property_ref)
            if not property_id:
                csr.execute(INSERT_PROPERTY_SQL, (property_ref,))
                log("\tAdding property {}".format(property_ref))
                property_id = get_last_insert_id(csr, 'Properties')

        csr.execute('end')
        db_conn.commit()
    except db_conn.Error as err:
        print_and_log('ERROR: ' + str(err))
        print_and_log('The data which caused the failure is: ' + property_ref)
        print_and_log('Unable to add property {} to the database'.format(property_ref))
        csr.execute('rollback')
        if rethrow_exception: raise
    except Exception as ex:
        print_and_log('ERROR: ' + str(ex))
        print_and_log('Unable to add property {} to the database'.format(property_ref))
        csr.execute('rollback')
        if rethrow_exception: raise
    return property_id


def addBlockToDB(db_conn, property_ref, block_ref, rethrow_exception = False):
    block_id = None
    try:
        csr = db_conn.cursor()
        csr.execute('begin')

        if block_ref:
            block_id = get_id_from_ref(csr, 'Blocks', 'block', block_ref)
            if not block_id:
                if property_ref:
                    if block_ref[-2:] == '00':
                        block_type = 'P'
                    else:
                        block_type = 'B'
                    property_id = get_id_from_ref(csr, 'Properties', 'property', property_ref)
                    csr.execute(INSERT_BLOCK_SQL, (block_ref, block_type, property_id))
                    log("\tAdding block {}".format(block_ref))
                    block_id = get_last_insert_id(csr, 'Blocks')

        csr.execute('end')
        db_conn.commit()
    except db_conn.Error as err:
        print_and_log('ERROR: ' + str(err))
        print_and_log('The data which caused the failure is: ' + str((property_ref, block_ref)))
        print_and_log('Unable to add property or block to the database')
        csr.execute('rollback')
        if rethrow_exception: raise
    except Exception as ex:
        print_and_log('ERROR: ' + str(ex))
        print_and_log('The data which caused the failure is: ' + str((property_ref, block_ref)))
        print_and_log('Unable to add property or block to the database')
        csr.execute('rollback')
        if rethrow_exception: raise
    return block_id


def addTenantToDB(db_conn, block_ref, tenant_ref, tenant_name, rethrow_exception = False):
    tenant_id = None
    try:
        csr = db_conn.cursor()
        csr.execute('begin')

        if tenant_ref:
            tenant_id = get_id_from_ref(csr, 'Tenants', 'tenant', tenant_ref)
            if not tenant_id:
                block_id = get_id_from_ref(csr, 'Blocks', 'block', block_ref)
                if block_id:
                    csr.execute(INSERT_TENANT_SQL, (tenant_ref, tenant_name, block_id))
                    log("\tAdding tenant {}".format(tenant_ref))
                    tenant_id = get_last_insert_id(csr, 'Tenants')

        csr.execute('end')
        db_conn.commit()
    except db_conn.Error as err:
        print_and_log('ERROR: ' + str(err))
        print_and_log('The data which caused the failure is: ' + str((block_ref, tenant_ref)))
        print_and_log('Unable to add tenant to the database')
        csr.execute('rollback')
        if rethrow_exception: raise
    except Exception as ex:
        print_and_log('ERROR: ' + str(ex))
        print_and_log('The data which caused the failure is: ' + str((block_ref, tenant_ref)))
        print_and_log('Unable to add tenant to the database')
        csr.execute('rollback')
        if rethrow_exception: raise
    return tenant_id


def importBlockBankAccountNumbers(db_conn, bos_reconciliations_file):
    # Read Excel spreadsheet into dataframe
    bank_accounts_df = pd.read_excel(bos_reconciliations_file, 'Accounts')

    num_bank_accounts_added_to_db = 0

    try:
        csr = db_conn.cursor()
        csr.execute('begin')
        for index, row in bank_accounts_df.iterrows():
            block_ref = row['Property Reference']
            account_number = row['Account Number']

            block_id = get_id_from_ref(csr, 'Blocks', 'block', block_ref)
            if block_id:
                id = get_id(csr, SELECT_BANK_ACCOUNT_SQL, (block_id,))
                if id:
                    csr.execute(UPDATE_BLOCK_ACCOUNT_NUMBER_SQL, (account_number, block_id))
                    log('\tAdding bank account number {} for block {}'.format(account_number, block_id))
                    num_bank_accounts_added_to_db += 1
        csr.execute('end')
        db_conn.commit()
        print_and_log("{} bank account numbers added to the database.".format(num_bank_accounts_added_to_db))
    except db_conn.Error as err:
        print_and_log('ERROR: ' + str(err))
        print_and_log('The data which caused the failure is: ' + str((block_ref, account_number)))
        print_and_log('No bank account numbers have been added to the database')
        csr.execute('rollback')
    except Exception as ex:
        print_and_log('ERROR: ' + str(ex))
        print_and_log('The data which caused the failure is: ' + str((block_ref, account_number)))
        print_and_log('No bank account numbers have been added to the database.')
        csr.execute('rollback')
        charges = {}


def importBankAccounts(db_conn, bank_accounts_file):
    # Read Excel spreadsheet into dataframe
    bank_accounts_df = pd.read_excel(bank_accounts_file, 'Accounts', dtype=str)
    bank_accounts_df.replace('nan', '', inplace=True)

    num_bank_accounts_added_to_db = 0

    try:
        csr = db_conn.cursor()
        csr.execute('begin')
        for index, row in bank_accounts_df.iterrows():
            reference = row['Reference']
            sort_code = row['Sort Code']
            account_number = row['Account Number']
            account_type = row['Account Type']
            property_or_block = row['Property Or Block']
            client_ref = row['Client Reference']
            account_name = row['Account Name']

            if property_or_block.upper() == 'PROPERTY' or property_or_block.lower() == 'P':
                property_ref, block_ref, _ = getPropertyBlockAndTenantRefs(reference)
                if block_ref[-2:] == '00':
                    block_id = get_id_from_ref(csr, 'Blocks', 'block', reference)
                    id = get_id(csr, SELECT_BANK_ACCOUNT_SQL1, (sort_code, account_number))
                    if not id:
                        csr.execute(INSERT_BANK_ACCOUNT_SQL, (sort_code, account_number, account_type, 'P', client_ref, account_name, block_id))
                        log('\tAdding bank account ({}, {}) for property {}'.format(sort_code, account_number, reference))
                        num_bank_accounts_added_to_db += 1
                else:
                    raise ValueError('Block reference ({}) for an estate must end in 00, for bank account ({}, {})'.format(reference, sort_code, account_number))
            elif property_or_block.upper() == 'BLOCK' or property_or_block.lower() == 'B':
                block_id = get_id_from_ref(csr, 'Blocks', 'block', reference)
                id = get_id(csr, SELECT_BANK_ACCOUNT_SQL1, (sort_code, account_number))
                if not id:
                    csr.execute(INSERT_BANK_ACCOUNT_SQL, (sort_code, account_number, account_type, 'B', client_ref, account_name, block_id))
                    log('\tAdding bank account ({}, {}) for property {}'.format(sort_code, account_number, reference))
                    num_bank_accounts_added_to_db += 1
            else:
                raise ValueError('Unknown property/block type {} for bank account ({}, {})'.format(property_or_block, sort_code, account_number))
        csr.execute('end')
        db_conn.commit()
        print_and_log("{} bank accounts added to the database.".format(num_bank_accounts_added_to_db))
    except db_conn.Error as err:
        print_and_log('ERROR: ' + str(err))
        print_and_log('The data which caused the failure is: ' + str((reference, sort_code, account_number)))
        print_and_log('No bank accounts have been added to the database')
        csr.execute('rollback')
    except Exception as ex:
        print_and_log('ERROR: ' + str(ex))
        print_and_log('The data which caused the failure is: ' + str((reference, sort_code, account_number)))
        print_and_log('No bank accounts have been added to the database.')
        csr.execute('rollback')


def calculateSCFund(auth_creditors, available_funds, property_ref, block_ref):
    # This should be encoded in a user-supplied rules spreadsheet for generality
    if property_ref == '035':
        return available_funds
    else:
        return auth_creditors + available_funds


def importQubeEndOfDayBalancesFile(db_conn, qube_eod_balances_xls_file):
    nested_dict = lambda: defaultdict(nested_dict)
    #charges = nested_dict()

    num_charges_added_to_db = 0

    # Read in the Qube balances report spreadsheet
    qube_eod_balances_workbook = xlrd.open_workbook(qube_eod_balances_xls_file)
    qube_eod_balances_workbook_sheet = qube_eod_balances_workbook.sheet_by_index(0)

    # Check that this Qube balances report has some of the expected cells (that it is the correct report)
    A1_cell_value = qube_eod_balances_workbook_sheet.cell_value(0, 0)
    B1_cell_value = qube_eod_balances_workbook_sheet.cell_value(0, 1)
    produced_date_cell_value = qube_eod_balances_workbook_sheet.cell_value(2, 0)
    cell_values_actual = [qube_eod_balances_workbook_sheet.cell_value(4, i) for i in range(0,4)]
    cell_values_check = ['Property / Fund', 'Bank', 'Excluded VAT', 'Auth Creditors', 'Available Funds']
    if not (A1_cell_value == 'Property Management' and B1_cell_value == 'Funds Available in Property Funds'
            and all(x[0] == x[1] for x in zip(cell_values_actual, cell_values_check))):
        print_and_log('ERROR: the spreadsheet {} does not look like a Qube balances report.')
        return None

    # Get date that the Qube report was produced from the spreadsheet
    at_date_str = ' '.join(produced_date_cell_value.split()[-3:])
    at_date = parser.parse(at_date_str).strftime('%Y-%m-%d')
    today = datetime.today()
    #if at_date != today:
    #    print_and_log('WARNING: Qube Balances Excel file produced on {}'.format(at_date))

    # Read in the data table from the spreadsheet
    qube_eod_balances_df = pd.read_excel(qube_eod_balances_xls_file, usecols='B:G', skiprows=4)

    # Column names in Qube report are associated with the wrong values - fix them
    qube_eod_balances_df.columns = ['PropertyCode / Fund', 'PropertyName / Category', 'Bank', 'Excluded VAT', 'Auth Creditors', 'Available Funds']

    # Drop all empty rows and replace 'nan' values with 0
    qube_eod_balances_df.dropna(how='all', inplace=True)
    qube_eod_balances_df.fillna(0, inplace=True)

    try:
        csr = db_conn.cursor()
        csr.execute('begin')
        found_property = False
        property_ref = None
        block_ref = None
        block_name = None
        block_ref, fund, category, auth_creditors, block_id = None, None, None, None, None

        type_id_auth_creditors = get_id_from_key_table(csr, 'type', AUTH_CREDITORS)
        type_id_available_funds = get_id_from_key_table(csr, 'type', AVAILABLE_FUNDS)
        type_id_sc_fund = get_id_from_key_table(csr, 'type', SC_FUND)

        for i in range(0, qube_eod_balances_df.shape[0]):
            property_code_or_fund = qube_eod_balances_df.iloc[i]['PropertyCode / Fund']
            property_name_or_category = qube_eod_balances_df.iloc[i]['PropertyName / Category']

            try_property_ref, try_block_ref, _ = getPropertyBlockAndTenantRefs(property_code_or_fund)
            if try_property_ref and try_block_ref:
                found_property = True
                property_ref = try_property_ref
                block_ref = try_block_ref
                block_name = property_name_or_category
            elif found_property:
                if property_code_or_fund in ['Service Charge', 'Rent', 'Tenant Recharge', 'Admin Fund', 'Reserve']:
                    fund = property_code_or_fund
                    category = property_name_or_category
                    fund_id = get_id_from_key_table(csr, 'fund', fund)
                    category_id = get_id_from_key_table(csr, 'category', category)

                    auth_creditors = qube_eod_balances_df.iloc[i][AUTH_CREDITORS]
                    available_funds = qube_eod_balances_df.iloc[i][AVAILABLE_FUNDS]
                    sc_fund = calculateSCFund(auth_creditors, available_funds, property_ref, block_ref)

                    #charges[property_ref][block_ref][fund][category][AUTH_CREDITORS] = auth_creditors
                    #charges[property_ref][block_ref][fund][category][AVAILABLE_FUNDS] = available_funds
                    #charges[property_ref][block_ref][fund][category][SC_FUND] = sc_fund

                    # If the property exists then add the block if it doesn't exist,
                    # otherwise find the existing block ID. This adds the xxx-00 estate references.
                    property_id = get_id_from_ref(csr, 'Properties', 'property', property_ref)
                    if property_id:
                        block_id = get_id_from_ref(csr, 'Blocks', 'block', block_ref)
                        if not block_id:
                            if block_ref[-2:] == '00':
                                block_type = 'P'
                            else:
                                block_type = 'B'
                            csr.execute(INSERT_BLOCK_SQL, (block_ref, block_type, property_id))
                            log("\tAdding block {}".format(block_ref))
                            block_id = get_id_from_ref(csr, 'Blocks', 'block', block_ref)

                    if block_id:
                        # Update block name
                        if not get_id(csr, SELECT_BLOCK_NAME_SQL, (block_ref,)):
                            csr.execute(UPDATE_BLOCK_NAME_SQL, (block_name, block_id))
                            log("\tAdding block name {} for block reference {}".format(block_name, block_ref))

                        # Add available funds charge
                        charges_id = get_id(csr, SELECT_CHARGES_SQL, (fund_id, category_id, type_id_available_funds, block_id, at_date))
                        if not charges_id:
                            csr.execute(INSERT_CHARGES_SQL, (fund_id, category_id, type_id_available_funds, at_date, available_funds, block_id))
                            log("\tAdding charge {}".format(str((fund, category, AVAILABLE_FUNDS, at_date, block_ref, available_funds))))
                            num_charges_added_to_db += 1

                        if property_code_or_fund in ['Service Charge', 'Tenant Recharge']:
                            # Add auth creditors charge
                            charges_id = get_id(csr, SELECT_CHARGES_SQL, (fund_id, category_id, type_id_auth_creditors, block_id, at_date))
                            if not charges_id:
                                csr.execute(INSERT_CHARGES_SQL, (fund_id, category_id, type_id_auth_creditors, at_date, auth_creditors, block_id))
                                log("\tAdding charge for {}".format(str((fund, category, AUTH_CREDITORS, at_date, block_ref, auth_creditors))))
                                num_charges_added_to_db += 1

                            # Add SC Fund charge
                            charges_id = get_id(csr, SELECT_CHARGES_SQL, (fund_id, category_id, type_id_sc_fund, block_id, at_date))
                            if not charges_id:
                                csr.execute(INSERT_CHARGES_SQL, (fund_id, category_id, type_id_sc_fund, at_date, sc_fund, block_id))
                                log("\tAdding charge for {}".format(str((fund, category, SC_FUND, at_date, block_ref, sc_fund))))
                                num_charges_added_to_db += 1
                    else:
                        log('WARNING: cannot determine the block for the Qube balances from block reference {}'.format(block_ref))

                elif property_code_or_fund == 'Property Totals':
                    found_property = False
            else:
                pass
                #log("Ignoring data with block reference '{}'".format(property_code_or_fund))

        csr.execute('end')
        db_conn.commit()
        print_and_log("{} charges added to the database.".format(num_charges_added_to_db))
    except db_conn.Error as err:
        print_and_log('ERROR: ' + str(err))
        print_and_log('The data which caused the failure is: ' + str((block_ref, fund, category, at_date, auth_creditors, block_id)))
        print_and_log('No Qube balances have been added to the database.')
        csr.execute('rollback')
        #charges = {}
    except Exception as ex:
        print_and_log('ERROR: ' + str(ex))
        print_and_log('The data which caused the failure is: ' + str((block_ref, fund, category, at_date, auth_creditors, block_id)))
        print_and_log('No Qube balances have been added to the database.')
        csr.execute('rollback')
        #charges = {}
    #return charges


def add_misc_data_to_db(db_conn):
    # Add account number and property name for some properties
    try:
        csr = db_conn.cursor()
        csr.execute('begin')

        csr.execute(UPDATE_PROPERTY_DETAILS_SQL, ('St Winefrides Estate', '020'))
        csr.execute(UPDATE_PROPERTY_DETAILS_SQL, ('Sand Wharf Estate', '034'))
        csr.execute(UPDATE_PROPERTY_DETAILS_SQL, ('Hensol Castle Park', '036'))
        csr.execute(UPDATE_PROPERTY_DETAILS_SQL, ('Farmleigh Estate', '074'))
        csr.execute(UPDATE_PROPERTY_DETAILS_SQL, ('St Fagans Rise', '095'))
        csr.execute('end')
        db_conn.commit()
    except db_conn.Error as err:
        print_and_log('ERROR: ' + str(err))
        print_and_log('No miscellaneous data has been added to the database.')
        csr.execute('rollback')
        charges = {}
    except Exception as ex:
        print_and_log('ERROR: ' + str(ex))
        print_and_log('No miscellaneous data has been added to the database.')
        csr.execute('rollback')
        charges = {}

def importAllData(db_conn):
    properties_file_pattern = os.path.join(WPP_INPUT_DIR, 'Properties*.xlsx')
    properties_xls_file = getLatestMatchingFile(properties_file_pattern)
    if properties_xls_file:
        print_and_log('Importing Properties from file {}'.format(properties_xls_file))
        importPropertiesFile(db_conn, properties_xls_file)
    else:
        print_and_log("Cannot find Properties file matching {}".format(properties_file_pattern))
    print_and_log()

    qube_eod_balances_file_pattern = os.path.join(WPP_INPUT_DIR, 'Qube*Balances*.xlsx')
    qube_eod_balances_files = getMatchingFiles(qube_eod_balances_file_pattern)
    if qube_eod_balances_files:
        for qube_eod_balances_file in qube_eod_balances_files:
            print_and_log('Importing Qube balances from file {}'.format(qube_eod_balances_file))
            charges = importQubeEndOfDayBalancesFile(db_conn, qube_eod_balances_file)
    else:
        print_and_log("Cannot find Qube EOD Balances file matching {}".format(qube_eod_balances_file_pattern))
    print_and_log()

    accounts_file_pattern = os.path.join(WPP_INPUT_DIR, 'Accounts.xlsx')
    accounts_file = getLatestMatchingFile(accounts_file_pattern)
    if accounts_file:
        print_and_log('Importing bank accounts from file {}'.format(accounts_file))
        importBankAccounts(db_conn, accounts_file)
    else:
        print_and_log("Cannot find account numbers file matching {}".format(properties_file_pattern))
    print_and_log()

    bos_statement_file_pattern = os.path.join(WPP_INPUT_DIR, 'PreviousDayTransactionExtract_*.xml')
    bos_statement_xml_files= getMatchingFiles(bos_statement_file_pattern)
    if bos_statement_xml_files:
        for bos_statement_xml_file in bos_statement_xml_files:
            print_and_log('Importing Bank Account Transactions from file {}'.format(bos_statement_xml_file))
            importBankOfScotlandTransactionsXMLFile(db_conn, bos_statement_xml_file)
    else:
        print_and_log("Cannot find bank account transactions file matching {}".format(bos_statement_file_pattern))
    print_and_log()

    eod_balances_file_patterns = [os.path.join(WPP_INPUT_DIR, f) for f in ['EOD BalancesReport_*.xml', 'EndOfDayBalanceExtract_*.xml']]
    eod_balances_xml_files = getMatchingFiles(eod_balances_file_patterns)
    if eod_balances_xml_files:
        for eod_balances_xml_file in eod_balances_xml_files:
            print_and_log('Importing Bank Account balances from file {}'.format(eod_balances_xml_file))
            importBankOfScotlandBalancesXMLFile(db_conn, eod_balances_xml_file)
    else:
        print_and_log("Cannot find bank account balances file matching {}".format(eod_balances_file_pattern))
    print_and_log()

    add_misc_data_to_db(db_conn)


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', type=str, help='Generate verbose log file.')
    args = parser.parse_args()
    return args


def main():
    import time
    start_time = time.time()

    # Get command line arguments
    args = get_args()

    os.makedirs(WPP_INPUT_DIR, exist_ok=True)
    os.makedirs(WPP_LOG_DIR, exist_ok=True)

    print_and_log('Beginning Import of data into the database, at {}\n'.format(start_time))

    db_conn = get_or_create_db(WPP_DB_FILE)
    charges = importAllData(db_conn)

    elapsed_time = time.time() - start_time
    #time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
    time.strftime("%S", time.gmtime(elapsed_time))

    print_and_log('Done in {} seconds.'.format(round(elapsed_time, 1)), end='\n')
    #input("Press enter to end.")

if __name__ == "__main__":
    main()