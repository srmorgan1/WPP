import argparse
import copy
import datetime as dt
import logging
import os
import sqlite3
import sys
from typing import cast

import pandas as pd
from dateutil import parser

from wpp.calendars import get_business_day_offset
from wpp.config import get_wpp_db_file, get_wpp_report_dir, get_wpp_report_file, get_wpp_run_reports_log_file
from wpp.data_classes import RunConfiguration
from wpp.db import get_db_connection, get_single_value, join_sql_queries, run_sql_query, union_sql_queries
from wpp.excel import format_all_excel_sheets_comprehensive
from wpp.exceptions import safe_pandas_operation
from wpp.logger import setup_logger
from wpp.sql_queries import (
    BLOCKS_NOT_IN_COMREC_REPORT,
    BOS_ACCOUNT_BALANCES_BY_BLOCK_SQL,
    BOS_ACCOUNT_BALANCES_BY_PROPERTY_SQL,
    QUBE_BOS_REPORT_BY_BLOCK_SQL,
    QUBE_BOS_REPORT_BY_PROPERTY_SQL,
    QUBE_BOS_SHEET_BY_BLOCK_SQL,
    QUBE_BOS_SHEET_BY_PROPERTY_SQL,
    SELECT_NON_PAY_TYPE_TRANSACTIONS,
    SELECT_PAY_TYPE_TRANSACTIONS,
    SELECT_TOTAL_PAID_SC_BY_BLOCK_SQL,
    SELECT_TOTAL_PAID_SC_BY_PROPERTY_SQL,
    SELECT_TOTAL_PAID_SC_BY_TENANT_SQL,
)
from wpp.utils import is_running_via_pytest

# Set up logger
logger = logging.getLogger(__name__)

# SQL queries are now imported from sql_queries module


def add_column_totals(df):
    if len(df) > 0:
        total_row = df.sum(numeric_only=True).rename("Total")
        # Convert to object dtype to allow string assignment without warning
        total_row = total_row.astype(object)
        total_row[df.columns[0]] = "TOTAL"
        df = pd.concat([df, pd.DataFrame([total_row])])
    return df


def add_extra_rows(df: pd.DataFrame) -> pd.DataFrame:
    PROPERTY_BLOCK_COL = "Property / Block"
    pd.options.mode.chained_assignment = None
    select = df[PROPERTY_BLOCK_COL] == "050-01"
    row = copy.copy(df[select])
    row["Name"] = row["Name"] + " GR"
    row[["Qube Total", "BOS", "Discrepancy"]] = row[["GR", "BOS GR", "Discrepancy GR"]]
    row[[PROPERTY_BLOCK_COL, "SC Fund", "Reserve", "Admin"]] = [
        "050-01A",
        0.0,
        0.0,
        0.0,
    ]
    row.reset_index()

    qube_total, qube_gr = None, None
    with safe_pandas_operation():
        qube_total = df.loc[select, "Qube Total"].iloc[0]
        qube_gr = df.loc[select, "GR"].iloc[0]
    if qube_total is not None and qube_gr is not None:
        df.loc[select, ["Qube Total"]] = qube_total - qube_gr

    bos_gr, bos = None, None
    with safe_pandas_operation():
        bos = df.loc[select, "BOS"].iloc[0]
        bos_gr = df.loc[select, "BOS GR"].iloc[0]
    if bos is not None and bos_gr is not None:
        df.loc[select, ["BOS"]] = bos - bos_gr

    df.loc[select, "GR"] = 0.0
    df = pd.concat([df, row])
    return df


def checkDataIsPresent(db_conn: sqlite3.Connection, qube_date: str, bos_date: str) -> bool:
    is_data_present = True

    csr = db_conn.cursor()
    sql = "select count(ID) from Transactions where pay_date = ?"
    count: int = cast(int, get_single_value(csr, sql, (bos_date,)))
    logger.info(f"{count} Bank Of Scotland transactions found for date {bos_date}")
    is_data_present = is_data_present and (count > 0)

    sql = "select count(ID) from AccountBalances where at_date = ?"
    count = cast(int, get_single_value(csr, sql, (bos_date,)))
    logger.info(f"{count} Bank Of Scotland account balance records found for date {bos_date}")
    is_data_present = is_data_present and (count > 0)

    sql = "select count(ID) from Charges where at_date = ?"
    count = cast(int, get_single_value(csr, sql, (qube_date,)))
    logger.info(f"{count} Qube charge records found for date {qube_date}")
    is_data_present = is_data_present and (count > 0)
    return is_data_present


def _generate_comrec_report(db_conn: sqlite3.Connection, bos_date: dt.date, excel_writer: pd.ExcelWriter) -> None:
    """Generate COMREC report showing total paid SC by property and block."""
    logger.info(f"Running COMREC report for {bos_date}")
    sql = union_sql_queries(
        SELECT_TOTAL_PAID_SC_BY_PROPERTY_SQL,
        SELECT_TOTAL_PAID_SC_BY_BLOCK_SQL,
        "ORDER BY Reference",
    )
    logger.debug(sql)
    df = run_sql_query(db_conn, sql, (bos_date.isoformat(),) * 4, logger)
    df = add_column_totals(df)
    df.to_excel(
        excel_writer,
        sheet_name=f"COMREC {bos_date}",
        index=False,
        float_format="%.2f",
    )

    # Check for blocks missing from COMREC report
    df = run_sql_query(db_conn, BLOCKS_NOT_IN_COMREC_REPORT, (bos_date.isoformat(),) * 2, logger)
    blocks = df["Block"].tolist()
    if len(blocks) > 0:
        logger.info("Blocks which have transactions but are missing from the COMREC report because there is no bank account for that block: {}".format(", ".join(blocks)))


def _generate_transactions_reports(db_conn: sqlite3.Connection, bos_date: dt.date, excel_writer: pd.ExcelWriter) -> None:
    """Generate both non-PAY and PAY transaction reports."""
    # Non-DC/PAY type transactions
    logger.info(f"Running Transactions report for {bos_date}")
    logger.debug(SELECT_NON_PAY_TYPE_TRANSACTIONS)
    df = run_sql_query(db_conn, SELECT_NON_PAY_TYPE_TRANSACTIONS, (bos_date.isoformat(),) * 2, logger)
    df = add_column_totals(df)
    df.to_excel(excel_writer, sheet_name="Transactions", index=False, float_format="%.2f")

    # DC/PAY type transactions
    logger.info(f"Running DC & PAY Transactions report for {bos_date}")
    logger.debug(SELECT_PAY_TYPE_TRANSACTIONS)
    df = run_sql_query(db_conn, SELECT_PAY_TYPE_TRANSACTIONS, (bos_date.isoformat(),) * 2, logger)
    df = add_column_totals(df)
    df.to_excel(
        excel_writer,
        sheet_name="DC & PAY Transactions",
        index=False,
        float_format="%.2f",
    )


def _generate_qube_bos_report(db_conn: sqlite3.Connection, qube_date: dt.date, bos_date: dt.date, excel_writer: pd.ExcelWriter) -> None:
    """Generate Qube BOS reconciliation report."""
    logger.info(f"Running Qube BOS report for {qube_date}")

    qube_by_block_sql = join_sql_queries(
        QUBE_BOS_SHEET_BY_BLOCK_SQL,
        QUBE_BOS_REPORT_BY_BLOCK_SQL,
        BOS_ACCOUNT_BALANCES_BY_BLOCK_SQL,
    )

    qube_by_property_sql = join_sql_queries(
        QUBE_BOS_SHEET_BY_PROPERTY_SQL,
        QUBE_BOS_REPORT_BY_PROPERTY_SQL,
        BOS_ACCOUNT_BALANCES_BY_PROPERTY_SQL,
    )

    sql = union_sql_queries(qube_by_property_sql, qube_by_block_sql)
    logger.debug(sql)
    df = run_sql_query(
        db_conn,
        sql,
        (qube_date.isoformat(), qube_date.isoformat(), bos_date.isoformat()) + (qube_date.isoformat(), qube_date.isoformat(), bos_date.isoformat()),
        logger,
    )
    df = add_extra_rows(df)
    df = df.sort_values(by="Property / Block")
    df = add_column_totals(df)
    df.drop(["BOS GR", "Discrepancy GR"], axis=1, inplace=True)
    df.to_excel(
        excel_writer,
        sheet_name=f"Qube BOS {qube_date}",
        index=False,
        float_format="%.2f",
    )


def _generate_tenant_report(db_conn: sqlite3.Connection, bos_date: dt.date, excel_writer: pd.ExcelWriter) -> None:
    """Generate total SC paid by tenant report."""
    logger.info(f"Running Total SC Paid By Tenant on {bos_date} report")
    logger.debug(SELECT_TOTAL_PAID_SC_BY_TENANT_SQL)
    df = run_sql_query(db_conn, SELECT_TOTAL_PAID_SC_BY_TENANT_SQL, (bos_date.isoformat(),) * 2, logger)
    df = add_column_totals(df)
    df.to_excel(
        excel_writer,
        sheet_name=f"Total SC By Tenant {bos_date}",
        index=False,
        float_format="%.2f",
    )


def runReports(db_conn: sqlite3.Connection, qube_date: dt.date, bos_date: dt.date) -> None:
    """Generate all WPP reports for the given dates."""
    logger.info(f"Qube Date: {qube_date}")
    logger.info(f"Bank Of Scotland Transactions and Account Balances Date: {bos_date}")

    if not checkDataIsPresent(db_conn, qube_date.isoformat(), bos_date.isoformat()):
        raise RuntimeError(f"The required data is not in the database. Unable to run the reports for Qube date {qube_date} and BoS transactions date {bos_date}")

    # Create a Pandas Excel writer using openpyxl as the engine.
    excel_report_file = get_wpp_report_file(qube_date)
    logger.info(f"Creating Excel spreadsheet report file {excel_report_file}")
    excel_writer = pd.ExcelWriter(excel_report_file, engine="openpyxl")

    try:
        _generate_comrec_report(db_conn, bos_date, excel_writer)
        _generate_transactions_reports(db_conn, bos_date, excel_writer)
        _generate_qube_bos_report(db_conn, qube_date, bos_date, excel_writer)
        _generate_tenant_report(db_conn, bos_date, excel_writer)

        # Apply consistent formatting to all sheets
        format_all_excel_sheets_comprehensive(excel_writer)
    finally:
        excel_writer.close()


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--bos_date", type=str, help="Bank Of Scotland Transactions date")
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


def get_run_date_args(args: argparse.Namespace, config: RunConfiguration) -> tuple[dt.date, dt.date]:
    qube_date = config.qube_date or (parser.parse(args.qube_date, dayfirst=False).date() if args.qube_date else (dt.date.today() - BUSINESS_DAY))
    bos_date = config.bos_date or (parser.parse(args.bos_date, dayfirst=False).date() if args.bos_date else qube_date)
    return qube_date, bos_date


def main(qube_date: dt.date | None = None, bos_date: dt.date | None = None) -> None:
    import time

    start_time = time.time()

    global logger
    log_file = get_wpp_run_reports_log_file(dt.datetime.today())
    logger = setup_logger(__name__, log_file)

    global BUSINESS_DAY
    BUSINESS_DAY = get_business_day_offset(logger)

    # Get command line arguments
    args = get_args() if not is_running_via_pytest() else argparse.Namespace()

    os.makedirs(get_wpp_report_dir(), exist_ok=True)

    logger.info("Running Reports")
    try:
        db_conn = get_db_connection(get_wpp_db_file())
        config = RunConfiguration(qube_date, bos_date, business_day_offset=BUSINESS_DAY)
        qube_date, bos_date = get_run_date_args(args, config)
        runReports(db_conn, qube_date, bos_date)
    except Exception as ex:
        logger.exception(f"running reports: {ex}")

    elapsed_time = time.time() - start_time
    time.strftime("%S", time.gmtime(elapsed_time))

    logger.info(f"Done in {round(elapsed_time, 1)} seconds.")
    logger.info("----------------------------------------------------------------------------------------")
    # input("Press enter to end.")


if __name__ == "__main__":
    main()
