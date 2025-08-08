"""Data classes for parameter grouping to reduce long parameter lists."""

from dataclasses import dataclass
from datetime import date


@dataclass
class TransactionReferences:
    """Groups property/block/tenant reference data."""

    property_ref: str | None = None
    block_ref: str | None = None
    tenant_ref: str | None = None

    def all_present(self) -> bool:
        """Check if all references are present."""
        return all((self.property_ref, self.block_ref, self.tenant_ref))


@dataclass
class RunConfiguration:
    """Configuration for report runs."""

    qube_date: date | None = None
    bos_date: date | None = None
    verbose: bool = False

    def get_dates(self) -> tuple[date, date]:
        """Get both dates, with fallbacks."""
        from datetime import date as dt_date

        from wpp.calendars import BUSINESS_DAY

        qube = self.qube_date or (dt_date.today() - BUSINESS_DAY)
        bos = self.bos_date or qube
        return qube, bos


@dataclass
class ChargeData:
    """Data for adding charges to database."""

    fund_id: int
    category_id: int
    type_id: int
    at_date: str
    amount: float
    block_id: int


@dataclass
class MatchLogData:
    """Data for logging matches."""

    description: str
    property_ref: str | None
    block_ref: str | None
    tenant_ref: str | None
    strategy_name: str
