import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from wpp.config import get_wpp_db_dir

#
# SQL
#
SELECT_LAST_RECORD_ID_SQL = "SELECT seq FROM sqlite_sequence WHERE name = ?;"
SELECT_TENANT_NAME_SQL = "SELECT tenant_name FROM Tenants WHERE tenant_ref = ?;"

#
# Tables
#
CREATE_PROPERTIES_TABLE = """
CREATE TABLE Properties (
    ID               INTEGER PRIMARY KEY AUTOINCREMENT,
    property_ref     TEXT  NOT NULL,
    property_name     TEXT
);
"""

CREATE_BLOCKS_TABLE = """
CREATE TABLE Blocks (
    ID                INTEGER PRIMARY KEY AUTOINCREMENT,
    block_ref         TEXT NOT NULL,
    block_name        TEXT,
    type              TEXT,
    property_id       INTEGER REFERENCES Properties (ID)
);
"""

CREATE_TENANTS_TABLE = """
CREATE TABLE Tenants (
    ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_ref     TEXT NOT NULL,
    tenant_name    TEXT,
    service_charge DOUBLE,
    block_id       INTEGER REFERENCES Blocks (ID)
);
"""

CREATE_SUGGESTED_TENANTS_TABLE = """
CREATE TABLE SuggestedTenants (
    ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id      INTEGER REFERENCES Tenants (ID),
    transaction_id INTEGER REFERENCES Transactions (ID)
);
"""

CREATE_TRANSACTIONS_TABLE = """
CREATE TABLE Transactions (
    ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    type           TEXT  NOT NULL,
    amount         DOUBLE  NOT NULL,
    description    TEXT,
    pay_date       DATE    NOT NULL,
    tenant_id      INTEGER REFERENCES Tenants (ID),
    account_id     INTEGER REFERENCES Accounts (ID)
);
"""

CREATE_CHARGES_TABLE = """
CREATE TABLE Charges (
    ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id        INTEGER    NOT NULL,
    category_id    INTEGER    NOT NULL,
    type_id        INTEGER    NOT NULL,
    at_date        DATE    NOT NULL,
    amount         DOUBLE,
    block_id       INTEGER REFERENCES Blocks (ID)
);
"""

CREATE_ACCOUNTS_TABLE = """
CREATE TABLE Accounts (
    ID                  INTEGER PRIMARY KEY AUTOINCREMENT,
    sort_code           TEXT  NOT NULL,
    account_number      TEXT  NOT NULL,
    account_type        TEXT,
    property_or_block   TEXT,
    client_ref          TEXT,
    account_name        TEXT  NOT NULL,
    block_id            INTEGER REFERENCES Blocks (ID)
);
"""

CREATE_ACCOUNT_BALANCES_TABLE = """
CREATE TABLE AccountBalances (
    ID                  INTEGER PRIMARY KEY AUTOINCREMENT,
    current_balance     DOUBLE NOT NULL,
    available_balance   DOUBLE NOT NULL,
    at_date             DATE NOT NULL,
    account_id          INTEGER REFERENCES Accounts (ID)
);
"""

CREATE_IRREGULAR_TRANSACTION_REFS_TABLE = """
CREATE TABLE IrregularTransactionRefs (
    ID                          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_ref                  TEXT NOT NULL,
    transaction_ref_pattern     TEXT NOT NULL
);
"""

CREATE_KEY_TABLE = """
CREATE TABLE Key_{} (
    ID             INTEGER PRIMARY KEY AUTOINCREMENT,
    value          TEXT
);
"""

#
# Indices
#
CREATE_PROPERTIES_INDEX = """
CREATE UNIQUE INDEX Index_Properties ON Properties (
    property_ref,
    property_name
);
"""

CREATE_BLOCKS_INDEX = """
CREATE UNIQUE INDEX Index_Blocks ON Blocks (
    block_ref,
    property_id,
    block_name,
    type
);
"""

CREATE_TENANTS_INDEX = """
CREATE UNIQUE INDEX Index_Tenants ON Tenants (
    tenant_ref,
    block_id,
    tenant_name
);
"""

CREATE_SUGGESTED_TENANTS_INDEX = """
CREATE UNIQUE INDEX Index_SuggestedTenants ON SuggestedTenants (
    tenant_id,
    transaction_id
);
"""

CREATE_TRANSACTIONS_INDEX = """
CREATE UNIQUE INDEX Index_Transactions ON Transactions (
    tenant_id,
    description,
    pay_date,
    account_id,
    type,
    amount
);
"""

CREATE_CHARGES_INDEX = """
CREATE UNIQUE INDEX Index_Charges ON Charges (
    block_id,
    fund_id,
    category_id,
    type_id,
    at_date
);
"""

CREATE_ACCOUNTS_INDEX = """
CREATE UNIQUE INDEX Index_Accounts ON Accounts (
    block_id,
    sort_code,
    account_number,
    account_type,
    property_or_block,
    account_name,
    client_ref
);
"""

CREATE_ACCOUNT_BALANCES_INDEX = """
CREATE UNIQUE INDEX Index_AccountBalances ON AccountBalances (
    account_id,
    at_date,
    current_balance,
    available_balance
);
"""

CREATE_IRREGULAR_TRANSACTION_REFS_INDEX = """
CREATE UNIQUE INDEX Index_IrregularTransactionRefs ON IrregularTransactionRefs (
    transaction_ref_pattern,
    tenant_ref
);
"""

CREATE_KEY_INDEX = """
CREATE UNIQUE INDEX Index_Key_{0} ON Key_{0} (
    value
);
"""


def _create_and_index_tables(db_conn: sqlite3.Connection, logger: logging.Logger = logging.getLogger()) -> None:
    try:
        csr = db_conn.cursor()
        csr.execute("begin")

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
        csr.execute(CREATE_KEY_TABLE.format("fund"))
        csr.execute(CREATE_KEY_TABLE.format("category"))
        csr.execute(CREATE_KEY_TABLE.format("type"))

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
        csr.execute(CREATE_KEY_INDEX.format("fund"))
        csr.execute(CREATE_KEY_INDEX.format("category"))
        csr.execute(CREATE_KEY_INDEX.format("type"))
        csr.execute("end")
        db_conn.commit()
    except db_conn.Error as err:
        logger.exception(err)
        csr.execute("rollback")
        sys.exit(1)


def get_or_create_db(db_file: Path, logger: logging.Logger = logging.getLogger()) -> sqlite3.Connection:
    init_db = not db_file.exists()
    get_wpp_db_dir().mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_file)
    if init_db:
        _create_and_index_tables(conn, logger)
    return conn


def get_last_insert_id(db_cursor: sqlite3.Cursor, table_name: str) -> int:
    db_cursor.execute(SELECT_LAST_RECORD_ID_SQL, (table_name,))
    _id = db_cursor.fetchone()
    if _id:
        return _id[0]
    else:
        raise RuntimeError(f"Failed to get last insert ID from table {table_name}")


def get_single_value(db_cursor: sqlite3.Cursor, sql: str, args_tuple: tuple = ()) -> Any | None:
    db_cursor.execute(sql, args_tuple)
    value = db_cursor.fetchone()
    if value:
        return value[0]
    else:
        return None


def checkTenantExists(db_cursor: sqlite3.Cursor, tenant_ref: str) -> bool:
    tenant_name = get_single_value(db_cursor, SELECT_TENANT_NAME_SQL, (tenant_ref,))
    return tenant_name is not None


def getTenantName(db_cursor: sqlite3.Cursor, tenant_ref: str) -> str:
    tenant_name = get_single_value(db_cursor, SELECT_TENANT_NAME_SQL, (tenant_ref,))
    if tenant_name is None:
        raise ValueError(f"Tenant with reference '{tenant_ref}' does not exist")
    return tenant_name


def get_data(db_cursor: sqlite3.Cursor, sql: str, args_tuple: tuple = ()) -> list[tuple]:
    db_cursor.execute(sql, args_tuple)
    values = db_cursor.fetchall()
    return values if values else []


def get_db_connection(db_file: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_file)
    return conn


def join_sql_queries(query_sql: str, sql1: str, sql2: str) -> str:
    sql1 = sql1.replace(";", "")
    sql2 = sql2.replace(";", "")

    sql = query_sql.format(sql1, sql2)
    return sql


def union_sql_queries(sql1: str, sql2: str, order_by_clause: str | None = None) -> str:
    sql1 = sql1.replace(";", "")
    sql2 = sql2.replace(";", "")

    sql = f"""
    {sql1}
    UNION ALL
    {sql2}
    """
    if order_by_clause:
        sql += " " + order_by_clause
    sql += ";"
    return sql


def run_sql_query(
    db_conn: sqlite3.Connection,
    sql: str,
    args_tuple: tuple,
    logger: logging.Logger = logging.getLogger(),
) -> pd.DataFrame:
    try:
        df = pd.read_sql_query(sql, db_conn, params=args_tuple)
        return df
    except db_conn.Error as err:
        # traceback.print_tb(ex.__traceback__)
        logger.exception(err)
        logger.error("The SQL that caused the failure is:")
        logger.error(sql)
        raise
    except Exception as ex:
        # traceback.print_tb(ex.__traceback__)
        logger.exception(ex)
        raise
