from dateutil import parser
import argparse
import datetime as dt
import sqlite3
import pandas as pd
import logging
import copy
import sys
import os
from typing import Optional, Tuple, Any, cast

from .config import (
    WPP_REPORT_DIR,
    WPP_LOG_DIR,
    WPP_DB_FILE,
    WPP_REPORT_FILE,
)
from .calendars import BUSINESS_DAY

WPP_LOG_FILE = WPP_LOG_DIR + r"/Log_RunReports_{}.txt"


#
# Set up Logging
#
class STDOutFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.INFO  # | record.levelno == logging.DEBUG


class STDErrFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not record.levelno == logging.INFO | record.levelno == logging.DEBUG


today = dt.datetime.today()
os.makedirs(WPP_LOG_DIR, exist_ok=True)
log_file = WPP_LOG_FILE.format(today.strftime("%Y-%m-%d"))
logFormatter = logging.Formatter(
    "%(asctime)s - %(levelname)s: - %(message)s", "%H:%M:%S"
)
logger = logging.getLogger()
handler = logging.FileHandler(log_file)
handler.setFormatter(logFormatter)
logger.addHandler(handler)

handler = logging.StreamHandler()
handler.setFormatter(logFormatter)
handler.addFilter(STDOutFilter())
logger.addHandler(handler)

logger.setLevel(logging.INFO)

#
# SQL
#
SELECT_TOTAL_PAID_SC_BY_TENANT_SQL = """
SELECT
    tenant_ref as 'Tenant Reference',
    tenant_name as 'Tenant Name',
    sum(amount) AS 'Total Paid SC'
FROM
    Transactions,
    Tenants
WHERE
    Transactions.tenant_id = Tenants.ID
    AND pay_date BETWEEN ? AND ?
    AND Transactions.type != 'PAY'
GROUP BY tenant_ref
ORDER BY tenant_ref;
"""

SELECT_TOTAL_PAID_SC_BY_BLOCK_SQL = """
SELECT
    block_ref AS Reference,
    block_name as 'Name',
    sum(amount) AS 'Total Paid SC',
    Accounts.account_number as 'Account Number'
FROM
    Transactions
    INNER JOIN Tenants ON Transactions.tenant_id = Tenants.ID
    INNER JOIN Blocks ON Tenants.block_id = Blocks.ID
    INNER JOIN Properties ON Blocks.property_id = Properties.ID
    LEFT OUTER JOIN Accounts ON Accounts.block_id = Blocks.ID
WHERE
    pay_date BETWEEN ? AND ?
    AND Transactions.type != 'PAY'
    AND Accounts.account_type = 'CL'
    AND Properties.property_name IS NULL
GROUP BY block_ref --, account_type
--ORDER BY block_ref;
"""

SELECT_TOTAL_PAID_SC_BY_PROPERTY_SQL = """
SELECT
    property_ref AS Reference,
    property_name as 'Name',
    sum(amount) AS 'Total Paid SC',
    Accounts.account_number as 'Account Number'
FROM
    Transactions
    INNER JOIN Tenants ON Transactions.tenant_id = Tenants.ID
    INNER JOIN Blocks ON Tenants.block_id = Blocks.ID
    INNER JOIN Properties ON Blocks.property_id = Properties.ID
    LEFT OUTER JOIN Accounts ON Accounts.block_id = (SELECT ID FROM Blocks b where b.block_ref = (property_ref || '-00'))
WHERE
    pay_date BETWEEN ? AND ?
    AND Transactions.type != 'PAY'
    AND Accounts.account_type = 'CL'
    AND Properties.property_name NOT NULL
GROUP BY property_ref
--ORDER BY property_ref;
"""

SELECT_NON_PAY_TYPE_TRANSACTIONS = """
SELECT
    block_ref AS 'Block',
    block_name as 'Block Name',
    tenant_ref as 'Tenant Reference',
    tenant_name as 'Tenant Name',
    amount as 'Amount',
    Transactions.type as 'Payment Type',
    description as 'Description'
FROM
    Transactions
    INNER JOIN Tenants ON Transactions.tenant_id = Tenants.ID
    INNER JOIN Blocks ON Tenants.block_id = Blocks.ID
    INNER JOIN Properties ON Blocks.property_id = Properties.ID
WHERE
    pay_date BETWEEN ? AND ?
    AND Transactions.type != 'PAY'
ORDER BY block_ref, Transactions.type, description;
"""

SELECT_PAY_TYPE_TRANSACTIONS = """
SELECT
    block_ref AS 'Block',
    block_name as 'Block Name',
    tenant_ref as 'Tenant Reference',
    tenant_name as 'Tenant Name',
    amount as 'Amount',
    Transactions.type as 'Payment Type',
    description as 'Description'
FROM
    Transactions
    INNER JOIN Tenants ON Transactions.tenant_id = Tenants.ID
    INNER JOIN Blocks ON Tenants.block_id = Blocks.ID
    INNER JOIN Properties ON Blocks.property_id = Properties.ID
WHERE
    pay_date BETWEEN ? AND ?
    AND Transactions.type = 'PAY'
ORDER BY block_ref, Transactions.type, description;
"""

QUBE_BOS_REPORT_BY_BLOCK_SQL = """
SELECT
    Blocks.ID as block_id,
    block_ref as 'Block',
    block_name as 'Block Name',
    sum(case when Key_fund.value = 'Service Charge' then amount end) as 'SC Fund',
    sum(case when Key_fund.value = 'Reserve' then amount end) as Reserve,
    sum(case when Key_fund.value in ('Tenant Recharge', 'Admin Fund') then amount end) as Admin,
    sum(case when Key_fund.value = 'Rent' then amount end) as 'Qube GR',
    sum(amount) as 'Qube Total'
FROM Charges, Properties, Blocks, Key_Category, Key_fund, Key_type
WHERE
    Properties.ID = Blocks.property_id
    AND Blocks.ID = Charges.block_id
    AND Key_category.ID = Charges.category_id
    AND Key_fund.ID = Charges.fund_id
    AND Key_type.ID = Charges.type_id
    AND
    (
    (Key_fund.value = 'Service Charge' AND (Key_category.value like '%Service Charge%' OR Key_category.value = 'Roof Replacement Reserves') AND Key_type.value = 'SC Fund') OR
    (Key_fund.value = 'Reserve' AND Key_type.value = 'Available Funds') OR
    (Key_fund.value = 'Tenant Recharge' AND Key_category.value like '%Tenant Recharge%' AND Key_type.value = 'SC Fund') OR
    (Key_fund.value = 'Rent' AND Key_category.value = 'Ground Rent' AND Key_type.value = 'Available Funds') OR
    (Key_fund.value = 'Admin Fund' AND Key_type.value = 'Available Funds')
    )
    AND Charges.at_date BETWEEN ? AND ?
    AND Blocks.type = 'B'
    AND Properties.property_name IS NULL
GROUP BY Blocks.ID
ORDER BY Blocks.block_ref;
"""

QUBE_BOS_REPORT_BY_PROPERTY_SQL = """
SELECT
    Properties.ID as property_id,
    property_ref as 'Property',
    property_name as 'Property Name',
    sum(case when Key_fund.value = 'Service Charge' then amount end) as 'SC Fund',
    sum(case when Key_fund.value = 'Reserve' then amount end) as Reserve,
    sum(case when Key_fund.value in ('Tenant Recharge', 'Admin Fund') then amount end) as Admin,
    sum(case when Key_fund.value = 'Rent' then amount end) as 'Qube GR',
    sum(amount) as 'Qube Total'
FROM
    Charges, Properties, Blocks, Key_Category, Key_fund, Key_type
WHERE
    Properties.ID = Blocks.property_id
    AND Blocks.ID = Charges.block_id
    AND Key_category.ID = Charges.category_id
    AND Key_fund.ID = Charges.fund_id
    AND Key_type.ID = Charges.type_id
    AND
    (
    (Key_fund.value = 'Service Charge' AND Key_category.value like '%Service Charge%' AND Key_type.value = 'SC Fund') OR
    (Key_fund.value = 'Reserve' AND Key_type.value = 'Available Funds') OR
    (Key_fund.value = 'Tenant Recharge' AND Key_category.value like '%Tenant Recharge%' AND Key_type.value = 'SC Fund') OR
    (Key_fund.value = 'Rent' AND Key_category.value = 'Ground Rent' AND Key_type.value = 'Available Funds') OR
    (Key_fund.value = 'Admin Fund' AND Key_type.value = 'Available Funds')
    )
    AND Charges.at_date BETWEEN ? AND ?
    AND Properties.property_name NOT NULL
GROUP BY Properties.ID
ORDER BY Properties.property_ref
"""

BOS_ACCOUNT_BALANCES_BY_BLOCK_SQL = """
SELECT
    Accounts.block_id,
    sum(case when account_type in ('CL', 'RE') then current_balance end) as 'BOS Non-GR',
    sum(case when account_type = 'GR' then current_balance end) as 'BOS GR',
    sum(current_balance) as BOS
FROM
    Accounts, AccountBalances, Blocks
WHERE
    AccountBalances.account_id = Accounts.ID
    AND Accounts.block_id = Blocks.ID
    AND AccountBalances.at_date = ?
    AND Blocks.type = 'B'
    --AND Accounts.property_or_block = ?
GROUP BY Accounts.block_id;
"""

BOS_ACCOUNT_BALANCES_BY_PROPERTY_SQL = """
SELECT
    Properties.ID as property_id,
    sum(case when account_type in ('CL', 'RE') then current_balance end) as 'BOS Non-GR',
    sum(case when account_type = 'GR' then current_balance end) as 'BOS GR',
    sum(current_balance) as BOS
FROM
    Properties, Blocks, Accounts, AccountBalances
WHERE
    Properties.ID = Blocks.property_id
    AND Blocks.ID = Accounts.block_id
    AND AccountBalances.account_id = Accounts.ID
    AND AccountBalances.at_date = ?
    AND Blocks.type = 'P'
    --AND Accounts.property_or_block = ?
GROUP BY Properties.ID
"""

QUBE_BOS_SHEET_BY_BLOCK_SQL = """
SELECT
    a.'Block' as 'Property / Block',
    a.'Block Name' as 'Name',
    a.'SC Fund',
    a.Reserve,
    a.Admin,
    a.'Qube GR' as GR,
    a.'Qube Total',
    b.BOS,
    b.'BOS GR',
    (a.'Qube Total' - b.BOS) as 'Discrepancy',
    (a.'Qube GR' - b.'BOS GR') as 'Discrepancy GR'
FROM
({}) a
LEFT OUTER JOIN
({}) b
ON a.block_id = b.block_id;
"""


QUBE_BOS_SHEET_BY_PROPERTY_SQL = """
SELECT
    a.'Property' as 'Property / Block',
    a.'Property Name' as 'Name',
    a.'SC Fund',
    a.Reserve,
    a.Admin,
    a.'Qube GR' as GR,
    a.'Qube Total',
    b.BOS,
    b.'BOS GR',
    (a.'Qube Total' - b.BOS) as 'Discrepancy',
    (a.'Qube GR' - b.'BOS GR') as 'Discrepancy GR'
FROM
({}) a
LEFT OUTER JOIN
({}) b
ON a.property_id = b.property_id;
"""

BLOCKS_NOT_IN_COMREC_REPORT = """
SELECT DISTINCT
    block_ref AS 'Block'
FROM
    Transactions
    INNER JOIN Tenants ON Transactions.tenant_id = Tenants.ID
    INNER JOIN Blocks ON Tenants.block_id = Blocks.ID
    INNER JOIN Properties ON Blocks.property_id = Properties.ID
WHERE
    pay_date BETWEEN ? AND ?
    AND Transactions.type != 'PAY'
    AND block_ref NOT IN
    (
        -- Doesn't have a block account in the Accounts table
        SELECT DISTINCT block_ref FROM Accounts, Blocks WHERE Accounts.property_or_block = 'B' AND Accounts.block_id = Blocks.ID ORDER BY block_ref
    )
    AND property_ref NOT IN
    (
        -- And also ddoesn't have an estate (-00) account
        SELECT DISTINCT property_ref FROM Accounts, Blocks, Properties WHERE Blocks.block_ref LIKE '%-00' AND Accounts.block_id = Blocks.ID AND Blocks.property_id = Properties.ID ORDER BY property_ref
    )
ORDER BY block_ref
"""


def get_db_connection(db_file: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_file)
    return conn


def join_sql_queries(query_sql: str, sql1: str, sql2: str) -> str:
    sql1 = sql1.replace(";", "")
    sql2 = sql2.replace(";", "")

    sql = query_sql.format(sql1, sql2)
    return sql


def union_sql_queries(
    sql1: str, sql2: str, order_by_clause: Optional[str] = None
) -> str:
    sql1 = sql1.replace(";", "")
    sql2 = sql2.replace(";", "")

    sql = """
    {}
    UNION ALL
    {}
    """.format(sql1, sql2)
    if order_by_clause:
        sql += " " + order_by_clause
    sql += ";"
    return sql


def run_sql_query(
    db_conn: sqlite3.Connection, sql: str, args_tuple: Tuple
) -> pd.DataFrame:
    try:
        df = pd.read_sql_query(sql, db_conn, params=args_tuple)
        return df
    except db_conn.Error as err:
        logging.error(str(err))
        # traceback.print_tb(ex.__traceback__)
        logging.exception(err)
        logging.error("The SQL that caused the failure is:")
        logging.error(sql)
        raise
    except Exception as ex:
        logging.error(str(ex))
        # traceback.print_tb(ex.__traceback__)
        logging.exception(ex)
        raise


def get_single_value(
    db_cursor: sqlite3.Cursor, sql: str, args_tuple: Tuple = ()
) -> Optional[Any]:
    db_cursor.execute(sql, args_tuple)
    value = db_cursor.fetchone()
    if value:
        return value[0]
    else:
        return None


def add_column_totals(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) > 0:
        df = df.append(df.sum(numeric_only=True).rename("Total"))
        df.iloc[-1:, 0] = "TOTAL"
    return df


def add_extra_rows(df: pd.DataFrame) -> pd.DataFrame:
    pd.options.mode.chained_assignment = None
    select = df["Property / Block"] == "050-01"
    row = copy.copy(df[select])
    row["Name"] = row["Name"] + " GR"
    row[["Qube Total", "BOS", "Discrepancy"]] = row[["GR", "BOS GR", "Discrepancy GR"]]
    row[["Property / Block", "SC Fund", "Reserve", "Admin"]] = [
        "050-01A",
        0.0,
        0.0,
        0.0,
    ]
    row.reset_index()

    qube_total, qube_gr = None, None
    try:
        qube_total = df.loc[select, "Qube Total"].iloc[0]
        qube_gr = df.loc[select, "GR"].iloc[0]
    except Exception:
        pass
    if qube_total is not None and qube_gr is not None:
        df.loc[select, ["Qube Total"]] = qube_total - qube_gr

    bos_gr, bos = None, None
    try:
        bos = df.loc[select, "BOS"].iloc[0]
        bos_gr = df.loc[select, "BOS GR"].iloc[0]
    except Exception:
        pass
    if bos is not None and bos_gr is not None:
        df.loc[select, ["BOS"]] = bos - bos_gr

    df.loc[select, "GR"] = 0.0
    df = df.append(row)
    return df


def checkDataIsPresent(
    db_conn: sqlite3.Connection, qube_date: str, bos_date: str
) -> bool:
    is_data_present = True

    csr = db_conn.cursor()
    sql = "select count(ID) from Transactions where pay_date = ?"
    count: int = cast(int, get_single_value(csr, sql, (bos_date,)))
    logging.info(f"{count} Bank Of Scotland transactions found for date {bos_date}")
    is_data_present = is_data_present and (count > 0)

    sql = "select count(ID) from AccountBalances where at_date = ?"
    count = cast(int, get_single_value(csr, sql, (bos_date,)))
    logging.info(
        f"{count} Bank Of Scotland account balance records found for date {bos_date}"
    )
    is_data_present = is_data_present and (count > 0)

    sql = "select count(ID) from Charges where at_date = ?"
    count = cast(int, get_single_value(csr, sql, (qube_date,)))
    logging.info(f"{count} Qube charge records found for date {qube_date}")
    is_data_present = is_data_present and (count > 0)
    return is_data_present


def runReports(db_conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    # Get start and end dates for this calendar month
    # today = dt.date.today()
    # year = int(today.strftime("%Y"))
    # month = int(today.strftime("%m"))
    # month_name = today.strftime("%b")
    # last_day_of_month = calendar.monthrange(year, month)[-1]
    # start_date = "{}-{}-{}".format(year, month, "1")
    # end_date = "{}-{}-{}".format(year, month, last_day_of_month)

    qube_date = (
        parser.parse(args.qube_date, dayfirst=False).strftime("%Y-%m-%d")
        if args.qube_date
        else (dt.date.today() - BUSINESS_DAY).strftime("%Y-%m-%d")
    )
    bos_date = (
        parser.parse(args.bos_date, dayfirst=False).strftime("%Y-%m-%d")
        if args.bos_date
        else qube_date
    )
    logging.info(f"Qube Date: {qube_date}")
    logging.info(f"Bank Of Scotland Transactions and Account Balances Date: {bos_date}")

    if not checkDataIsPresent(db_conn, qube_date, bos_date):
        logging.error(
            f"The required data is not in the database. Unable to run the reports for Qube date {qube_date} and BoS transactions date {bos_date}"
        )
        sys.exit(1)

    # Create a Pandas Excel writer using openpyxl as the engine.
    excel_report_file = WPP_REPORT_FILE.format(qube_date)
    logging.info(f"Creating Excel spreadsheet report file {excel_report_file}")
    excel_writer = pd.ExcelWriter(excel_report_file, engine="openpyxl")

    # Run SC total transactions by block (COMREC) report for given run date
    logging.info(f"Running COMREC report for {bos_date}")
    sql = union_sql_queries(
        SELECT_TOTAL_PAID_SC_BY_PROPERTY_SQL,
        SELECT_TOTAL_PAID_SC_BY_BLOCK_SQL,
        "ORDER BY Reference",
    )
    logging.debug(sql)
    df = run_sql_query(db_conn, sql, (bos_date,) * 4)
    df = add_column_totals(df)
    df.to_excel(
        excel_writer,
        sheet_name="COMREC {}".format(bos_date),
        index=False,
        float_format="%.2f",
    )
    df = run_sql_query(db_conn, BLOCKS_NOT_IN_COMREC_REPORT, (bos_date,) * 2)
    blocks = df["Block"].tolist()
    if len(blocks) > 0:
        logging.info(
            "Blocks which have transactions but are missing from the COMREC report because there is no bank account for that block: {}".format(
                ", ".join(blocks)
            )
        )

    # Non-DC/PAY type transactions
    logging.info(f"Running Transactions report for {bos_date}")
    logging.debug(SELECT_NON_PAY_TYPE_TRANSACTIONS)
    df = run_sql_query(db_conn, SELECT_NON_PAY_TYPE_TRANSACTIONS, (bos_date,) * 2)
    df = add_column_totals(df)
    df.to_excel(
        excel_writer, sheet_name="Transactions", index=False, float_format="%.2f"
    )

    # DC/PAY type transactions
    logging.info(f"Running DC & PAY Transactions report for {bos_date}")
    logging.debug(SELECT_PAY_TYPE_TRANSACTIONS)
    df = run_sql_query(db_conn, SELECT_PAY_TYPE_TRANSACTIONS, (bos_date,) * 2)
    df = add_column_totals(df)
    df.to_excel(
        excel_writer,
        sheet_name="DC & PAY Transactions",
        index=False,
        float_format="%.2f",
    )

    # Run Qube BOS By Block report for given run date
    # logging.info(f'Running Qube BOS By Block report for {qube_date}')
    qube_by_block_sql = join_sql_queries(
        QUBE_BOS_SHEET_BY_BLOCK_SQL,
        QUBE_BOS_REPORT_BY_BLOCK_SQL,
        BOS_ACCOUNT_BALANCES_BY_BLOCK_SQL,
    )
    # logging.debug(qube_by_block_sql)
    # qube_by_block_df = run_sql_query(db_conn, qube_by_block_sql, (qube_date, qube_date, bos_date))
    # qube_by_block_df = add_extra_rows(qube_by_block_df)
    # qube_by_block_df = qube_by_block_df.sort_values(by='Property / Block')
    # qube_by_block_df = add_column_totals(qube_by_block_df)
    # qube_by_block_df.drop(['BOS GR', 'Discrepancy GR'], axis=1, inplace=True)
    # qube_by_block_df.to_excel(excel_writer, sheet_name='Qube BOS By Block {}'.format(qube_date), index=False, float_format = '%.2f')

    # Run Qube BOS By Property report for given run date
    # logging.info(f'Running Qube BOS By Property report for {qube_date}')
    qube_by_property_sql = join_sql_queries(
        QUBE_BOS_SHEET_BY_PROPERTY_SQL,
        QUBE_BOS_REPORT_BY_PROPERTY_SQL,
        BOS_ACCOUNT_BALANCES_BY_PROPERTY_SQL,
    )
    # logging.debug(qube_by_property_sql)
    # qube_by_property_df = run_sql_query(db_conn, qube_by_property_sql, (qube_date, qube_date, bos_date))
    # qube_by_property_df = qube_by_property_df.sort_values(by='Property / Block')
    # qube_by_property_df = add_column_totals(qube_by_property_df)
    # qube_by_property_df.drop(['BOS GR', 'Discrepancy GR'], axis=1, inplace=True)
    # qube_by_property_df.to_excel(excel_writer, sheet_name='Qube BOS By Property {}'.format(qube_date), index=False, float_format = '%.2f')

    # Run Qube BOS report for given run date
    logging.info(f"Running Qube BOS report for {qube_date}")
    sql = union_sql_queries(qube_by_property_sql, qube_by_block_sql)
    logging.debug(sql)
    df = run_sql_query(
        db_conn,
        sql,
        (qube_date, qube_date, bos_date) + (qube_date, qube_date, bos_date),
    )
    df = add_extra_rows(df)
    df = df.sort_values(by="Property / Block")
    df = add_column_totals(df)
    df.drop(["BOS GR", "Discrepancy GR"], axis=1, inplace=True)
    df.to_excel(
        excel_writer,
        sheet_name="Qube BOS {}".format(qube_date),
        index=False,
        float_format="%.2f",
    )

    # Run SC total transactions by tenant report for given run date
    logging.info(f"Running Total SC Paid By Tenant on {bos_date} report")
    logging.debug(SELECT_TOTAL_PAID_SC_BY_TENANT_SQL)
    df = run_sql_query(db_conn, SELECT_TOTAL_PAID_SC_BY_TENANT_SQL, (bos_date,) * 2)
    df = add_column_totals(df)
    df.to_excel(
        excel_writer,
        sheet_name="Total SC By Tenant {}".format(bos_date),
        index=False,
        float_format="%.2f",
    )

    excel_writer.close()


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-b", "--bos_date", type=str, help="Bank Of Scotland Transactions date"
    )
    parser.add_argument("-q", "--qube_date", type=str, help="Qube Balances date")
    parser.add_argument("-v", "--verbose", type=str, help="Generate verbose log file.")
    args = parser.parse_args()

    if args.bos_date and not args.qube_date:
        print("ERROR: --bos_date can only be provided with --qube_date")
        sys.exit(1)

    # if len(sys.argv) == 1:
    #    print('''RunReports.py [--bos_date YYYY-MM-DD] [--qube_date YYYY-MM-DD] [--verbose]''')
    #    sys.exit(0)
    return args


def main() -> None:
    import time

    start_time = time.time()

    # Get command line arguments
    args = get_args()

    os.makedirs(WPP_REPORT_DIR, exist_ok=True)

    logging.info("Running Reports")
    try:
        db_conn = sqlite3.connect(WPP_DB_FILE)
        runReports(db_conn, args)
    except Exception as ex:
        logging.error(str(ex))

    elapsed_time = time.time() - start_time
    time.strftime("%S", time.gmtime(elapsed_time))

    logging.info("Done in {} seconds.".format(round(elapsed_time, 1)))
    logging.info(
        "----------------------------------------------------------------------------------------"
    )
    # input("Press enter to end.")


if __name__ == "__main__":
    main()
