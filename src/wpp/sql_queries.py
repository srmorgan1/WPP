"""Centralized SQL queries for WPP reports and data processing.

This module contains all complex SQL queries used across the application,
separated from business logic for better maintainability and readability.
"""

# Service Charge Payment Queries
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

# Transaction Queries
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

# Qube Report Queries
QUBE_BOS_REPORT_BY_BLOCK_SQL = """
SELECT
    Blocks.ID as block_id,
    block_ref as 'Block',
    block_name as 'Name',
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

# Bank of Scotland Balance Queries
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

# Combined Report Queries
QUBE_BOS_SHEET_BY_BLOCK_SQL = """
SELECT
    a.'Block' as 'Property / Block',
    a.'Name',
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

# Exception Report Queries
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
        SELECT DISTINCT block_ref FROM Accounts, Blocks WHERE Blocks.type = 'B' AND Accounts.block_id = Blocks.ID ORDER BY block_ref
    )
    AND property_ref NOT IN
    (
        -- And also doesn't have an estate (-00) account
        SELECT DISTINCT property_ref FROM Accounts, Blocks, Properties WHERE Blocks.block_ref LIKE '%-00' AND Accounts.block_id = Blocks.ID AND Blocks.property_id = Properties.ID ORDER BY property_ref
    )
ORDER BY block_ref
"""
