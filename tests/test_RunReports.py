import logging
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# FILE: tests/test_RunReports.py
from wpp.calendars import EnglandAndWalesHolidayCalendar
from wpp.db import get_db_connection
from wpp.logger import StdErrFilter, StdOutFilter
from wpp.RunReports import add_column_totals, add_extra_rows, checkDataIsPresent, get_args, get_single_value, join_sql_queries, run_sql_query, runReports, union_sql_queries

# Define the database file for testing
TEST_DB_FILE = "/Users/steve/Development/PycharmProjects/WPP/tests/test_WPP_DB.db"


@pytest.fixture
def db_conn():
    # Setup: create a new database connection for testing
    conn = get_db_connection(TEST_DB_FILE)
    yield conn
    # Teardown: close the database connection and remove the test database file
    conn.close()
    os.remove(TEST_DB_FILE)


def test_EnglandAndWalesHolidayCalendar():
    calendar = EnglandAndWalesHolidayCalendar()
    holidays = calendar.holidays(datetime(2023, 1, 1), datetime(2023, 12, 31))
    assert len(holidays) > 0


def test_STDOutFilter():
    filter_ = StdOutFilter()
    record = MagicMock(levelno=logging.INFO)
    assert filter_.filter(record)


def test_STDErrFilter():
    filter_ = StdErrFilter()
    record = MagicMock(levelno=logging.ERROR)
    assert filter_.filter(record)


def test_join_sql_queries():
    sql1 = "SELECT * FROM table1"
    sql2 = "SELECT * FROM table2"
    query_sql = "({}) UNION ALL ({})"
    result = join_sql_queries(query_sql, sql1, sql2)
    assert "UNION ALL" in result


def test_union_sql_queries():
    sql1 = "SELECT * FROM table1"
    sql2 = "SELECT * FROM table2"
    result = union_sql_queries(sql1, sql2)
    assert "UNION ALL" in result


@patch("RunReports.pd.read_sql_query")
def test_run_sql_query(mock_read_sql_query):
    mock_read_sql_query.return_value = pd.DataFrame()
    conn = MagicMock()
    sql = "SELECT * FROM table"
    result = run_sql_query(conn, sql, ())
    assert isinstance(result, pd.DataFrame)


def test_get_single_value():
    cursor = MagicMock()
    cursor.fetchone.return_value = [1]
    sql = "SELECT 1"
    result = get_single_value(cursor, sql)
    assert result == 1


def test_add_column_totals():
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    result = add_column_totals(df)
    assert "TOTAL" in result.iloc[-1, 0]


def test_add_extra_rows():
    df = pd.DataFrame(
        {
            "Property / Block": ["050-01"],
            "Name": ["Test Block"],
            "Qube Total": [100],
            "BOS": [90],
            "Discrepancy": [10],
            "GR": [5],
            "BOS GR": [4],
            "Discrepancy GR": [1],
        }
    )
    result = add_extra_rows(df)
    assert len(result) > 1


@patch("RunReports.get_single_value")
def test_checkDataIsPresent(mock_get_single_value):
    mock_get_single_value.return_value = 1
    conn = MagicMock()
    result = checkDataIsPresent(conn, "2023-01-01", "2023-01-01")
    assert result


@patch("RunReports.run_sql_query")
@patch("RunReports.pd.ExcelWriter")
def test_runReports(mock_ExcelWriter, mock_run_sql_query):
    mock_run_sql_query.return_value = pd.DataFrame()
    conn = MagicMock()
    args = MagicMock()
    args.qube_date = "2023-01-01"
    args.bos_date = "2023-01-01"
    runReports(conn, args)
    assert mock_ExcelWriter.called


@patch("argparse.ArgumentParser.parse_args")
def test_get_args(mock_parse_args):
    mock_parse_args.return_value = MagicMock(bos_date="2023-01-01", qube_date="2023-01-01")
    args = get_args()
    assert args.bos_date == "2023-01-01"
    assert args.qube_date == "2023-01-01"
