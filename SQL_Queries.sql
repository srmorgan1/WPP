-- Total of paid service charges by tenant
SELECT block_ref, tenant_ref, tenant_name, amount FROM Transactions, Tenants, Blocks WHERE Transactions.tenant_id = Tenants.ID AND Blocks.ID = Tenants.block_id ORDER BY block_ref;

SELECT tenant_ref as 'Tenant Reference', tenant_name as 'Tenant Name', sum(amount) AS 'Total Paid SC' FROM Transactions, Tenants
WHERE Transactions.tenant_id = Tenants.ID AND pay_date BETWEEN '2018-11-29' AND '2018-11-29'
GROUP BY tenant_ref
ORDER BY tenant_ref;

-- Service charges paid by tenant
SELECT tenant_ref, tenant_name, amount FROM Transactions, Tenants WHERE Transactions.tenant_id = Tenants.ID;
SELECT block_ref, tenant_ref, tenant_name, amount FROM Transactions, Tenants, Blocks WHERE Transactions.tenant_id = Tenants.ID and Blocks.ID = Tenants.block_id order by block_ref;


-- Total of paid service charges by block
SELECT block_ref as 'Block', sum(amount) as 'Total Paid SC' FROM Transactions, Tenants, Blocks
WHERE Transactions.tenant_id = Tenants.ID AND Tenants.block_id = Blocks.ID
GROUP BY block_ref;

-- SC Fund from Qube EOD Balances by block
select block_ref as 'Block', amount as 'SC Fund' from Charges, Blocks, Key_Category, Key_fund, Key_type
where
    Blocks.ID = Charges.block_id and Key_category.ID = Charges.category_id and Key_fund.ID = Charges.fund_id and Key_type.ID = Charges.type_id
    and Key_fund.value = 'Service Charge' and Key_category.value like '%Service Charge%' and Key_type.value = 'SC Fund'

-- Misc queries
select distinct fund_id, category_id from Charges

select distinct strftime('%m', at_date) as month from Charges

-- Reconcile Qube and Transactions service charges by block
select a.block_ref as 'Block', a.'SC Fund', b.'SC Paid' from
(select block_id, block_ref, amount as 'SC Fund', account_number as 'Account Number' from Charges, Blocks, Key_Category, Key_fund, Key_type
where
    Blocks.ID = Charges.block_id and Key_fund.ID = Charges.fund_id AND Key_category.ID = Charges.category_id and Key_type.ID = Charges.type_id
    and Key_fund.value = 'Service Charge' and Key_category.value like '%Service Charge%' and Key_type.value = 'SC Fund') a
LEFT OUTER JOIN
(SELECT block_id, sum(amount) as 'SC Paid' FROM Transactions, Tenants, Blocks
WHERE Transactions.tenant_id = Tenants.ID AND Tenants.block_id = Blocks.ID
GROUP BY block_ref) b
ON a.block_id = b.block_id;

SELECT a.block_ref as 'Block', a.'SC Fund', b.'SC Paid', a.account_number as 'Account Number' FROM
(SELECT block_id, block_ref, amount AS 'SC Fund', account_number FROM Charges, Blocks, Key_Category, Key_fund, Key_type
WHERE
    Blocks.ID = Charges.block_id AND Key_fund.ID = Charges.fund_id AND Key_category.ID = Charges.category_id AND Key_type.ID = Charges.type_id
    AND Key_fund.value = 'Service Charge' AND Key_category.value like '%Service Charge%' AND Key_type.value = 'SC Fund'
    AND at_date BETWEEN '2018-11-01' AND '2018-11-30') a
LEFT OUTER JOIN
(SELECT block_id, sum(amount) AS 'SC Paid' FROM Transactions, Tenants, Blocks
WHERE pay_date BETWEEN '2018-11-01' AND '2018-11-30' AND Transactions.tenant_id = Tenants.ID AND Tenants.block_id = Blocks.ID
GROUP BY block_ref) b
ON a.block_id = b.block_id;

SELECT a.block_ref as 'Block', a.'SC Fund', b.'SC Paid', a.account_number as 'Account Number' FROM
(SELECT block_id, block_ref, amount AS 'SC Fund', account_number FROM Charges, Blocks, Key_Category, Key_fund, Key_type
WHERE
    Blocks.ID = Charges.block_id AND Key_fund.ID = Charges.fund_id AND Key_category.ID = Charges.category_id AND Key_type.ID = Charges.type_id
    AND Key_fund.value = 'Service Charge' AND Key_category.value like '%Service Charge%' AND Key_type.value = 'SC Fund'
    AND at_date BETWEEN ? AND ?) a
LEFT OUTER JOIN
(SELECT block_id, sum(amount) AS 'SC Paid' FROM Transactions, Tenants, Blocks
WHERE Transactions.tenant_id = Tenants.ID AND Tenants.block_id = Blocks.ID AND pay_date BETWEEN ? AND ?
GROUP BY block_ref) b
ON a.block_id = b.block_id;

-- Test Queries

SELECT block_ref, Key_fund.value as 'Fund', Key_category.value as 'Category', Key_type.value as 'Type', amount AS 'Amount', account_number
FROM Charges, Blocks, Key_Category, Key_fund, Key_type
WHERE
    Blocks.ID = Charges.block_id AND Key_category.ID = Charges.category_id AND Key_fund.ID = Charges.fund_id AND Key_type.ID = Charges.type_id
    AND block_id=55


-- For QubeBOS Report
SELECT
    block_ref as 'Block', block_name as 'Block Name', Key_fund.value as 'Fund', amount AS 'Amount'
FROM Charges, Blocks, Key_Category, Key_fund, Key_type
WHERE
    Blocks.ID = Charges.block_id AND Key_category.ID = Charges.category_id AND Key_fund.ID = Charges.fund_id AND Key_type.ID = Charges.type_id
    AND
    (
    (Key_fund.value = 'Service Charge' AND Key_category.value like '%Service Charge%' AND Key_type.value = 'SC Fund') OR
    (Key_fund.value = 'Reserve') OR
    (Key_fund.value = 'Admin Fund') OR
    (Key_fund.value = 'Rent' AND Key_category.value = 'Ground Rent' AND Key_type.value = 'Available Funds')
    )
    AND at_date BETWEEN '2018-11-01' AND '2018-11-30'
ORDER BY block_id;


SELECT
    block_ref as 'Block', block_name as 'Block Name', Key_fund.value as 'Fund', Key_Category.value as 'Category', Key_type.value as 'Type', amount AS 'Amount'
FROM Charges, Blocks, Key_Category, Key_fund, Key_type
WHERE
    Blocks.ID = Charges.block_id AND Key_category.ID = Charges.category_id AND Key_fund.ID = Charges.fund_id AND Key_type.ID = Charges.type_id
    AND
    (
    (Key_fund.value = 'Service Charge' AND Key_category.value like '%Service Charge%' AND Key_type.value = 'SC Fund') OR
    (Key_fund.value = 'Reserve' AND Key_type.value = 'Available Funds') OR
    (Key_fund.value = 'Tenant Recharge' AND Key_type.value = 'SC Fund') OR
    (Key_fund.value = 'Admin Fund' AND Key_type.value = 'Available Funds') OR
    (Key_fund.value = 'Rent' AND Key_category.value = 'Ground Rent' AND Key_type.value = 'Available Funds')
    )
    AND at_date BETWEEN '2018-11-01' AND '2018-11-30'
ORDER BY block_id;


-- For QubeBOS Report by Block
-- Should 'Admin' be taken from 'Tenant Recharge', 'Admin' or the sum of the two?
SELECT
    block_ref as 'Block',
    block_name as 'Block Name',
    sum(case when Key_fund.value = 'Service Charge' then amount end) as 'SC Fund',
    sum(case when Key_fund.value = 'Reserve' then amount end) as Reserve,
    sum(case when Key_fund.value = 'Tenant Recharge' then amount end) as Admin,
    sum(case when Key_fund.value = 'Rent' then amount end) as 'GR',
    sum(amount) as 'Qube Total'
FROM Charges, Blocks, Key_Category, Key_fund, Key_type
WHERE
    Blocks.ID = Charges.block_id AND Key_category.ID = Charges.category_id AND Key_fund.ID = Charges.fund_id AND Key_type.ID = Charges.type_id
    AND
    (
    (Key_fund.value = 'Service Charge' AND Key_category.value like '%Service Charge%' AND Key_type.value = 'SC Fund') OR
    (Key_fund.value = 'Reserve') OR
    (Key_fund.value = 'Tenant Recharge' AND Key_category.value like '%Tenant Recharge%' AND Key_type.value = 'SC Fund') OR
    (Key_fund.value = 'Rent' AND Key_category.value = 'Ground Rent' AND Key_type.value = 'Available Funds')
    )
    AND at_date BETWEEN '2018-11-01' AND '2018-11-30'
GROUP BY block_id
ORDER BY block_ref;


-- For QubeBOS Report by Property
-- Should 'Admin' be taken from 'Tenant Recharge', 'Admin' or the sum of the two?
SELECT
    property_ref as 'Property',
    property_name as 'Property Name',
    sum(case when Key_fund.value = 'Service Charge' then amount end) as 'SC Fund',
    sum(case when Key_fund.value = 'Reserve' then amount end) as Reserve,
    sum(case when Key_fund.value = 'Tenant Recharge' then amount end) as Admin,
    sum(case when Key_fund.value = 'Rent' then amount end) as 'GR',
    sum(amount) as 'Qube Total'
FROM Charges, Properties, Blocks, Key_Category, Key_fund, Key_type
WHERE
    Properties.ID = Blocks.property_id AND Blocks.ID = Charges.block_id AND Key_category.ID = Charges.category_id AND Key_fund.ID = Charges.fund_id AND Key_type.ID = Charges.type_id
    AND
    (
    (Key_fund.value = 'Service Charge' AND Key_category.value like '%Service Charge%' AND Key_type.value = 'SC Fund') OR
    (Key_fund.value = 'Reserve') OR
    (Key_fund.value = 'Tenant Recharge') OR
    (Key_fund.value = 'Rent' AND Key_category.value = 'Ground Rent' AND Key_type.value = 'Available Funds')
    )
    AND at_date BETWEEN '2018-11-01' AND '2018-11-30'
GROUP BY property_id
ORDER BY property_ref;


-- To test the import of charges
SELECT
    block_id, block_ref as 'Block', block_name as 'Block Name', Key_fund.value as 'Fund', Key_category.value, Key_type.value, amount AS 'Amount'
FROM Charges, Blocks, Key_Category, Key_fund, Key_type
WHERE
    Blocks.ID = Charges.block_id AND Key_category.ID = Charges.category_id AND Key_fund.ID = Charges.fund_id AND Key_type.ID = Charges.type_id
    AND at_date BETWEEN '2018-11-01' AND '2018-11-30'
    AND block_id = 194
ORDER BY block_id;

select Properties.property_name, Blocks.block_name, Key_fund.value as 'Fund', Key_category.value as 'Category', Key_type.value as 'Type', amount
from Charges, Properties, Blocks, Key_fund, Key_category, Key_type
where Properties.ID = Blocks.property_id and Blocks.ID = Charges.block_id and Key_fund.ID = fund_id and Key_category.ID = category_id and Key_type.ID = type_id and block_id in (122, 123, 197) and fund_id in (1,2)



SELECT
    Blocks.block_ref,
    --case when account_type in ('CL', 'RE') then current_balance end as 'BOS Non-GR',
    --case when account_type = 'GR' then current_balance end as 'BOS GR',
    current_balance as BOS
FROM
    Accounts, AccountBalances, Blocks
WHERE
    AccountBalances.account_id = Accounts.ID
    AND Accounts.block_id = Blocks.ID
    AND AccountBalances.at_date = '2018-11-29'
    AND Blocks.block_ref = '071-01'
    AND Blocks.type = 'B'

select
    pay_date, block_ref, block_name, tenant_name, description, amount
    from Transactions, Tenants, Blocks
where
    Transactions.tenant_id = Tenants.ID
    and Tenants.block_id = Blocks.ID
    --and Blocks.block_ref = '020-03'
    and pay_date = '2018-11-29'
    order by Blocks.block_ref
