"""Business logic constants and enumerations for WPP application.

This module contains magic numbers, business rules, and enumerated constants
that are used throughout the application for data processing and validation.
"""

from enum import Enum

# ============================================================================
# Business Logic Constants (Magic Numbers)
# ============================================================================

# Tenant Reference Matching
MINIMUM_TENANT_NAME_MATCH_LENGTH = 4  # Minimum substring length for reliable tenant name matching
MIN_TENANT_REF_LENGTH_FOR_ERROR_CORRECTION = 3  # Minimum length for applying error corrections

# Property Reference Validation
MINIMUM_VALID_PROPERTY_REF = 900  # Property refs >= this value are excluded from processing

# File Processing
MAX_ZIP_FILE_ENTRIES = 1  # ZIP files must contain exactly one entry

# DataFrame Operations
PANDAS_DROP_COLUMNS_AXIS = 1  # Axis parameter for dropping DataFrame columns

# ============================================================================
# String Constants for Business Rules
# ============================================================================

# Special Characters and Suffixes
DEBIT_CARD_SUFFIX = "DC"  # Suffix indicating debit card transactions
PROPERTY_094_ERROR_CHAR = "O"  # Character to correct to "0" in property 094 references
PROPERTY_094_CORRECTION_POSITION = -3  # Position of error character from end of reference

# Excluded Characters
EXCLUDED_TENANT_REF_CHARACTERS = ["Z", "Y"]  # Characters that invalidate tenant references

# Estate Block Identifier
ESTATE_BLOCK_SUFFIX = "00"  # Suffix identifying estate service charge blocks (e.g., "020-00")

# ============================================================================
# Enumerations for Related Constants
# ============================================================================


class FundType(Enum):
    """Types of funds used in financial processing."""

    SERVICE_CHARGE = "Service Charge"
    TENANT_RECHARGE = "Tenant Recharge"
    ADMIN_FUND = "Admin Fund"
    RESERVE = "Reserve"
    RENT = "Rent"


class AccountType(Enum):
    """Bank account types."""

    CLIENT = "CL"  # Client account
    GROUND_RENT = "GR"  # Ground rent account
    RESERVE = "RE"  # Reserve account


class BlockType(Enum):
    """Types of property blocks."""

    PROPERTY = "P"  # Property-level block (estate)
    BLOCK = "B"  # Individual block


class TransactionType(Enum):
    """Transaction types for filtering."""

    PAYMENT = "PAY"  # Payment transactions


class PropertyOrBlock(Enum):
    """Property or block indicator for accounts."""

    PROPERTY = "P"  # Property-level account
    BLOCK = "B"  # Block-level account


class ChargeType(Enum):
    """Charge type categories."""

    SC_FUND = "SC Fund"  # Service charge fund
    AVAILABLE_FUNDS = "Available Funds"  # Available funds
    AUTH_CREDITORS = "Auth Creditors"  # Authorized creditors


# ============================================================================
# Simple String Constants Classes
# ============================================================================


class ReportColumns:
    """Standard column names used in reports."""

    PROPERTY_BLOCK = "Property / Block"
    QUBE_TOTAL = "Qube Total"
    BOS_GR = "BOS GR"
    DISCREPANCY_GR = "Discrepancy GR"
    SC_FUND = "SC Fund"
    RESERVE = "Reserve"
    ADMIN = "Admin"
    QUBE_GR = "Qube GR"
    BOS = "BOS"
    DISCREPANCY = "Discrepancy"


class TableNames:
    """Database table names."""

    TENANTS = "Tenants"
    PROPERTIES = "Properties"
    BLOCKS = "Blocks"
    ACCOUNTS = "Accounts"
    CHARGES = "Charges"
    TRANSACTIONS = "Transactions"


# ============================================================================
# Special Case Mappings
# ============================================================================


# Property recoding rules: (original_property, original_block) -> new_property
SPECIAL_PROPERTY_RECODING = {
    ("020", "020-03"): "020A",  # Block 020-03 belongs to different property group
    ("064", "064-01"): "064A",  # Block 064-01 belongs to different property group
}

# Block recoding rules: (property, original_block) -> new_block
SPECIAL_BLOCK_RECODING = {
    ("101", "101-02"): "101-01",  # Block 101-02 should be 101-01
}
