"""Database command pattern implementation for consistent database operations."""

import logging
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .data_classes import ChargeData
from .db import get_last_insert_id


@dataclass
class DatabaseCommand(ABC):
    """Abstract base for database operations."""

    @abstractmethod
    def execute(self, cursor: sqlite3.Cursor, logger: logging.Logger) -> Any:
        """Execute the database operation with preserved logging."""
        pass


@dataclass
class InsertTenantCommand(DatabaseCommand):
    """Command to insert a new tenant."""

    tenant_ref: str
    tenant_name: str
    block_id: int
    insert_sql: str  # Pass SQL to preserve exact behavior

    def execute(self, cursor: sqlite3.Cursor, logger: logging.Logger) -> int:
        cursor.execute(self.insert_sql, (self.tenant_ref, self.tenant_name, self.block_id))
        logger.debug(f"\tAdding tenant {self.tenant_ref} to the database")
        return get_last_insert_id(cursor, "Tenants")


@dataclass
class UpdateTenantNameCommand(DatabaseCommand):
    """Command to update tenant name."""

    tenant_name: str
    tenant_id: int
    tenant_ref: str  # For logging
    update_sql: str

    def execute(self, cursor: sqlite3.Cursor, logger: logging.Logger) -> None:
        cursor.execute(self.update_sql, (self.tenant_name, self.tenant_id))
        logger.info(f"Updated tenant name to {self.tenant_name} for tenant reference {self.tenant_ref}")


@dataclass
class InsertPropertyCommand(DatabaseCommand):
    """Command to insert a new property."""

    property_ref: str
    insert_sql: str

    def execute(self, cursor: sqlite3.Cursor, logger: logging.Logger) -> int:
        cursor.execute(self.insert_sql, (self.property_ref,))
        logger.debug(f"\tAdding property {self.property_ref} to the database")
        return get_last_insert_id(cursor, "Properties")


@dataclass
class InsertBlockCommand(DatabaseCommand):
    """Command to insert a new block."""

    block_ref: str
    block_type: str | None
    property_id: int
    insert_sql: str

    def execute(self, cursor: sqlite3.Cursor, logger: logging.Logger) -> int:
        cursor.execute(self.insert_sql, (self.block_ref, self.block_type, self.property_id))
        logger.debug(f"\tAdding block {self.block_ref} to the database")
        return get_last_insert_id(cursor, "Blocks")


@dataclass
class UpdateBlockNameCommand(DatabaseCommand):
    """Command to update block name."""

    block_name: str
    block_ref: str
    update_sql: str

    def execute(self, cursor: sqlite3.Cursor, logger: logging.Logger) -> None:
        cursor.execute(self.update_sql, (self.block_name, self.block_ref))
        logger.debug(f"\tAdding block name {self.block_name} for block reference {self.block_ref}")


@dataclass
class InsertChargeCommand(DatabaseCommand):
    """Command to insert a charge."""

    charge_data: ChargeData
    insert_sql: str

    def execute(self, cursor: sqlite3.Cursor, logger: logging.Logger) -> None:
        cursor.execute(
            self.insert_sql, (self.charge_data.fund_id, self.charge_data.category_id, self.charge_data.type_id, self.charge_data.at_date, self.charge_data.amount, self.charge_data.block_id)
        )


@dataclass
class InsertTransactionCommand(DatabaseCommand):
    """Command to insert a transaction."""

    transaction_type: str
    amount: float
    description: str
    pay_date: str
    tenant_id: int
    account_id: int
    sort_code: str  # For logging
    account_number: str  # For logging
    tenant_ref: str  # For logging
    insert_sql: str

    def execute(self, cursor: sqlite3.Cursor, logger: logging.Logger) -> None:
        cursor.execute(
            self.insert_sql,
            (
                self.transaction_type,
                self.amount,
                self.description,
                self.pay_date,
                self.tenant_id,
                self.account_id,
            ),
        )
        logger.debug(f"\tAdding transaction {(self.sort_code, self.account_number, self.transaction_type, self.amount, self.description, self.pay_date, self.tenant_ref)}")


class DatabaseCommandExecutor:
    """Executor for database commands with consistent error handling."""

    def __init__(self, cursor: sqlite3.Cursor, logger: logging.Logger):
        self.cursor = cursor
        self.logger = logger

    def execute(self, command: DatabaseCommand) -> Any:
        """Execute a database command with preserved logging."""
        return command.execute(self.cursor, self.logger)
