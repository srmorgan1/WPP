from dateutil import parser
import argparse
import datetime as dt
import sqlite3
import pandas as pd
import calendar
import copy
import sys

# NB: This must be set to the correct location
WPP_ROOT_DIR = r'/Users/steve/Work/WPP'

WPP_DB_DIR = WPP_ROOT_DIR + '/Database'
WPP_REPORT_DIR = WPP_ROOT_DIR + '/Reports'
WPP_DB_FILE = WPP_DB_DIR + r'/WPP_DB.db'
WPP_REPORT_FILE = WPP_REPORT_DIR + r'/WPP_Report_{}.xlsx'

#
# SQL
#
SELECT_TOTAL_PAID_SC_BY_TENANT_SQL = '''
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
GROUP BY tenant_ref
ORDER BY tenant_ref;
'''

SELECT_TOTAL_PAID_SC_BY_BLOCK_SQL = '''
SELECT
    block_ref AS 'Block',
    block_name as 'Block Name',
    sum(amount) AS 'Total Paid SC',
    Accounts.account_number as 'Account Number'
FROM
    Transactions, Tenants, Blocks, Accounts
WHERE
    Transactions.tenant_id = Tenants.ID
    AND Tenants.block_id = Blocks.ID
    AND Accounts.block_id = Blocks.ID
    AND pay_date BETWEEN ? AND ?
GROUP BY block_ref
ORDER BY block_ref;
'''

QUBE_BOS_REPORT_BY_BLOCK_SQL = '''
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
    (Key_fund.value = 'Service Charge' AND Key_category.value like '%Service Charge%' AND Key_type.value = 'SC Fund') OR
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
'''

QUBE_BOS_REPORT_BY_PROPERTY_SQL = '''
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
'''

BOS_ACCOUNT_BALANCES_BY_BLOCK_SQL = '''
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
'''

BOS_ACCOUNT_BALANCES_BY_PROPERTY_SQL = '''
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
'''

QUBE_BOS_SHEET_BY_BLOCK_SQL = '''
SELECT
    a.'Block' as 'Property / Block',
    a.'Block Name' as 'Name',
    a.'SC Fund',
    a.Reserve,
    a.Admin,
    a.'Qube GR',
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
'''


QUBE_BOS_SHEET_BY_PROPERTY_SQL = '''
SELECT
    a.'Property' as 'Property / Block',
    a.'Property Name' as 'Name',
    a.'SC Fund',
    a.Reserve,
    a.Admin,
    a.'Qube GR',
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
'''


def join_sql_queries(query_sql, sql1, sql2):
    sql1 = sql1.replace(';', '')
    sql2 = sql2.replace(';', '')

    sql = query_sql.format(sql1, sql2)
    return sql


def union_sql_queries(sql1, sql2):
    sql1 = sql1.replace(';', '')
    sql2 = sql2.replace(';', '')

    sql = '''
    {}
    UNION ALL
    {};
    '''.format(sql1, sql2)
    return sql


def run_sql_query(db_conn, sql, args_tuple):
    try:
        df = pd.read_sql_query(sql, db_conn, params=args_tuple)
        return df
    except db_conn.Error as err:
        print('ERROR: ' + str(err))
        print(sql)
        return None
    except Exception as ex:
        print('ERROR: ' + str(ex))
        print(sql)
        return None

def add_column_totals(df):
    if len(df > 0):
        df = df.append(df.sum(numeric_only=True).rename('Total'))
        df.iloc[-1:, 0] = 'TOTAL'
    return df

def add_extra_rows(df):
    pd.options.mode.chained_assignment = None
    select = df['Property / Block'] == '050-01'
    row = copy.copy(df[select])
    row['Name'] = row['Name'] + ' GR'
    row[['Qube Total', 'BOS', 'Discrepancy']] = row[['Qube GR', 'BOS GR', 'Discrepancy GR']]
    row[['SC Fund', 'Reserve', 'Admin']] = [0.0, 0.0, 0.0]
    row.reset_index()
    df.loc[select, ['Qube Total']] = df.loc[select, 'Qube Total'].iloc[0] - df.loc[select, 'Qube GR'].iloc[0]
    df.loc[select, ['BOS']] = df.loc[select, 'BOS'].iloc[0] - df.loc[select, 'BOS GR'].iloc[0]
    df = df.append(row)
    return df


def runReports(db_conn, args):
    # Get start and end dates for this calendar month
    today = dt.date.today()
    year = int(today.strftime('%Y'))
    month = int(today.strftime('%m'))
    month = 11
    month_name = today.strftime('%b')
    last_day_of_month = calendar.monthrange(year, month)[-1]
    start_date = '{}-{}-{}'.format(year, month, '1')
    end_date = '{}-{}-{}'.format(year, month, last_day_of_month)

    bos_date = parser.parse(args.bos_date) if args.bos_date else dt.date.today() - dt.timedelta(1)
    qube_date = parser.parse(args.qube_date) if args.qube_date else dt.date.today()

    # Create a Pandas Excel writer using XlsxWriter as the engine.
    excel_report_file = WPP_REPORT_FILE.format(qube_date)
    excel_writer = pd.ExcelWriter(excel_report_file, engine='xlsxwriter')

    # Run SC total transactions by block (COMREC) report for given run date
    print('Running Total Services Charges Paid By Block on {} report'.format(bos_date))
    df = run_sql_query(db_conn, SELECT_TOTAL_PAID_SC_BY_BLOCK_SQL, (bos_date,) * 2)
    df = add_column_totals(df)
    df.to_excel(excel_writer, sheet_name='Total SC By Block {}'.format(bos_date), index=False, float_format = '%.2f')

    # Run Qube BOS By Block report for given run date
    print('Running Qube BOS By Block report for {}'.format(qube_date))
    qube_by_block_sql = join_sql_queries(QUBE_BOS_SHEET_BY_BLOCK_SQL, QUBE_BOS_REPORT_BY_BLOCK_SQL, BOS_ACCOUNT_BALANCES_BY_BLOCK_SQL)
    qube_by_block_df = run_sql_query(db_conn, qube_by_block_sql, (qube_date, qube_date, bos_date))
    qube_by_block_df = add_extra_rows(qube_by_block_df)
    qube_by_block_df = qube_by_block_df.sort_values(by='Property / Block')
    qube_by_block_df = add_column_totals(qube_by_block_df)
    qube_by_block_df.drop(['Qube GR', 'BOS GR', 'Discrepancy GR'], axis=1, inplace=True)
    qube_by_block_df.to_excel(excel_writer, sheet_name='Qube BOS By Block {}'.format(qube_date), index=False, float_format = '%.2f')

    # Run Qube BOS By Property report for given run date
    print('Running Qube BOS By Property report for {}'.format(qube_date))
    qube_by_property_sql = join_sql_queries(QUBE_BOS_SHEET_BY_PROPERTY_SQL, QUBE_BOS_REPORT_BY_PROPERTY_SQL, BOS_ACCOUNT_BALANCES_BY_PROPERTY_SQL)
    qube_by_property_df = run_sql_query(db_conn, qube_by_property_sql, (qube_date, qube_date, bos_date))
    qube_by_property_df = qube_by_property_df.sort_values(by='Property / Block')
    qube_by_property_df = add_column_totals(qube_by_property_df)
    qube_by_property_df.drop(['Qube GR', 'BOS GR', 'Discrepancy GR'], axis=1, inplace=True)
    qube_by_property_df.to_excel(excel_writer, sheet_name='Qube BOS By Property {}'.format(qube_date), index=False, float_format = '%.2f')

    # Run Qube BOS report for given run date
    print('Running Qube BOS report for {}'.format(qube_date))
    sql = union_sql_queries(qube_by_property_sql, qube_by_block_sql)
    df = run_sql_query(db_conn, sql, (qube_date, qube_date, bos_date) + (qube_date, qube_date, bos_date))
    df = add_extra_rows(df)
    df = df.sort_values(by='Property / Block')
    df = add_column_totals(df)
    df.drop(['Qube GR', 'BOS GR', 'Discrepancy GR'], axis=1, inplace=True)
    df.to_excel(excel_writer, sheet_name='Qube BOS {}'.format(qube_date), index=False, float_format='%.2f')

    # Run SC total transactions by tenant report for given run date
    print('Running Total SC Paid By Tenant in {} report'.format(bos_date))
    df = run_sql_query(db_conn, SELECT_TOTAL_PAID_SC_BY_TENANT_SQL, (bos_date,) * 2)
    df = add_column_totals(df)
    df.to_excel(excel_writer, sheet_name='Total SC By Tenant {}'.format(bos_date), index=False, float_format = '%.2f')

    excel_writer.close()

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-q', '--bos_date', type=str, help='Bank Of Scotland Transactions date')
    parser.add_argument('-b', '--qube_date', type=str, help='Qube Balances date')
    parser.add_argument('-v', '--verbose', type=str, help='Generate verbose log file.')
    args = parser.parse_args()

    if len(sys.argv) == 1:
        print('''RunReports.py [--bos_date YYYY-MM-DD] [--qube_date YYYY-MM-DD] [--verbose]''')
        sys.exit(0)

    return args

def main():
    import time
    start_time = time.time()

    # Get command line arguments
    args = get_args()

    os.makedirs(WPP_INPUT_DIR, exist_ok=True)
    os.makedirs(WPP_LOG_DIR, exist_ok=True)

    print('Running Reports')
    try:
        db_conn = conn = sqlite3.connect(WPP_DB_FILE)
        reports = runReports(db_conn, args)
    except Exception as ex:
        print("ERROR: " + str(ex))

    elapsed_time = time.time() - start_time
    # time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
    time.strftime("%S", time.gmtime(elapsed_time))

    print('Done in {} seconds.'.format(round(elapsed_time, 1)))
    # input("Press enter to end.")


if __name__ == "__main__":
    main()