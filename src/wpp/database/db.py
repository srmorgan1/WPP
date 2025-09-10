import logging
import sqlite3
import sys
from abc import abstractmethod
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from ..config import get_wpp_db_dir

# ============================================================================
# Database Provider Pattern
# ============================================================================


class DatabaseProvider(Protocol):
    """Protocol for database connection providers."""

    @abstractmethod
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        ...

    @abstractmethod
    def should_close_connection(self) -> bool:
        """Whether this provider manages connection lifecycle."""
        ...


class CliDatabaseProvider:
    """Database provider for CLI applications that manages its own connections."""

    def __init__(self, db_file: Path | str | None = None, logger: logging.Logger | None = None):
        self.db_file = db_file
        self.logger = logger or logging.getLogger(__name__)
        self._connection: sqlite3.Connection | None = None

    def get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = get_or_create_db(self.db_file, self.logger)
        return self._connection

    def should_close_connection(self) -> bool:
        """CLI provider manages its own connections."""
        return True


class WebDatabaseProvider:
    """Database provider for web applications that uses shared in-memory connections."""

    def __init__(self, shared_connection: sqlite3.Connection | None = None):
        """Initialize with shared connection, creating it if not provided."""
        if shared_connection is None:
            shared_connection = get_shared_web_db_connection()
        self.shared_connection = shared_connection

    def get_connection(self) -> sqlite3.Connection:
        """Get the shared database connection."""
        return self.shared_connection

    def should_close_connection(self) -> bool:
        """Web provider does not manage connection lifecycle."""
        return False


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

CREATE_ACCOUNTS_CL_UNIQUENESS_INDEX = """
CREATE UNIQUE INDEX Index_Accounts_CL_Per_Block ON Accounts (block_id, account_type)
WHERE account_type = 'CL';
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
        csr.execute(CREATE_ACCOUNTS_CL_UNIQUENESS_INDEX)
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


def _is_running_in_web_app() -> bool:
    """Detect if we're running in a web app context (FastAPI server)."""
    import inspect
    import sys

    # Check if FastAPI is loaded (more reliable than stack inspection)
    if "fastapi" in sys.modules:
        return True

    # Check the call stack for FastAPI-related modules
    for frame_info in inspect.stack():
        frame = frame_info.frame
        if "fastapi" in str(frame.f_code.co_filename).lower():
            return True

        # Check if any of the loaded modules indicate web app context
        if hasattr(frame, "f_globals") and "fastapi" in frame.f_globals:
            return True

    # Check if we're being called from the API services
    current_module = inspect.currentframe()
    if current_module:
        caller_frame = current_module.f_back
        if caller_frame and "api" in str(caller_frame.f_code.co_filename).lower():
            return True

    return False


# Thread-safe singleton for shared web app database connection
def get_shared_web_db_connection():
    """Get the shared web app database connection (thread-safe singleton).

    This function ensures that only one in-memory database connection is created
    for the web app, even when called from multiple threads simultaneously.

    Note: Uses check_same_thread=False to allow cross-thread access, which is safe
    for our read-heavy workload with careful write coordination.
    """
    if not hasattr(get_shared_web_db_connection, "_connection"):
        logger = logging.getLogger(__name__)
        logger.info("Initializing shared in-memory SQLite database for web app")
        # Enable cross-thread access for web app shared connection
        get_shared_web_db_connection._connection = sqlite3.connect(
            ":memory:",
            detect_types=0,
            check_same_thread=False,  # Allow access from multiple threads
        )
        _create_and_index_tables(get_shared_web_db_connection._connection, logger)
    return get_shared_web_db_connection._connection


def get_or_create_db(db_file: Path | str | None = None, logger: logging.Logger = logging.getLogger()) -> sqlite3.Connection:
    """Get or create database connection.

    Args:
        db_file: Path to database file, or None to use default, or ":memory:" for in-memory
        logger: Logger instance

    Returns:
        SQLite database connection
    """
    from wpp.config import get_web_app_use_memory_db, get_wpp_db_file

    # No longer needed - using thread-safe function instead

    # Check if explicit :memory: is requested
    if db_file == ":memory:":
        logger.info("Using in-memory SQLite database (explicitly requested)")
        conn = sqlite3.connect(":memory:", detect_types=0, check_same_thread=False)
        # Always initialize schema for in-memory database
        _create_and_index_tables(conn, logger)
        return conn

    # For web apps, check if memory database is configured
    # Apply web app config when running in web app context, regardless of db_file parameter
    use_memory = False
    if _is_running_in_web_app():
        use_memory = get_web_app_use_memory_db()
        logger.debug(f"Web app detected, memory database setting: {use_memory}")

    if use_memory:
        # Use shared in-memory database for web app to ensure consistency
        return get_shared_web_db_connection()
    else:
        # Use file-based database for CLI tools
        if db_file is None:
            db_file = get_wpp_db_file()

        init_db = not Path(db_file).exists()
        get_wpp_db_dir().mkdir(parents=True, exist_ok=True)
        # Disable deprecated date adapters to prevent Python 3.12+ warnings
        # For web apps, enable cross-thread access to prevent threading issues
        check_same_thread = not _is_running_in_web_app()
        conn = sqlite3.connect(db_file, detect_types=0, check_same_thread=check_same_thread)
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
    # Disable deprecated date adapters to prevent Python 3.12+ warnings
    # For web apps, enable cross-thread access to prevent threading issues
    check_same_thread = not _is_running_in_web_app()
    conn = sqlite3.connect(db_file, detect_types=0, check_same_thread=check_same_thread)
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


def get_unique_date_from_charges(db_conn: sqlite3.Connection, logger: logging.Logger = logging.getLogger()) -> str | None:
    """Get the single unique date from the charges table at_date column.

    Returns the unique date as a string if exactly one unique date exists,
    otherwise returns None and logs a warning.

    Args:
        db_conn: Database connection
        logger: Logger instance for warnings

    Returns:
        str | None: The unique date string or None if not exactly one unique date
    """
    try:
        cursor = db_conn.cursor()

        # First check if Charges table exists and has data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Charges'")
        if not cursor.fetchone():
            logger.warning("Charges table does not exist")
            return None

        # Check total count of records in Charges table
        cursor.execute("SELECT COUNT(*) FROM Charges")
        total_count = cursor.fetchone()[0]
        logger.info(f"Charges table has {total_count} total records")

        # Get all distinct dates
        cursor.execute("SELECT DISTINCT at_date FROM Charges ORDER BY at_date")
        unique_dates = cursor.fetchall()
        logger.info(f"Found {len(unique_dates)} distinct dates in Charges table")

        if len(unique_dates) == 0:
            logger.warning("No dates found in Charges table")
            return None
        elif len(unique_dates) == 1:
            date_str = unique_dates[0][0]
            logger.info(f"Found unique date in Charges table: {date_str}")
            return date_str
        else:
            dates_list = [row[0] for row in unique_dates]
            logger.warning(f"Expected exactly one unique date in Charges table, found {len(unique_dates)}: {dates_list}")
            # Return the most recent date as fallback
            most_recent = max(dates_list)
            logger.info(f"Returning most recent date as fallback: {most_recent}")
            return most_recent
    except Exception as e:
        logger.error(f"Error getting unique date from charges: {e}")
        return None
