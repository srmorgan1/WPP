"""Data classes for parameter grouping to reduce long parameter lists."""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class TransactionReferences:
    """Groups property/block/tenant reference data."""
    property_ref: Optional[str] = None
    block_ref: Optional[str] = None
    tenant_ref: Optional[str] = None
    
    def all_present(self) -> bool:
        """Check if all references are present."""
        return all((self.property_ref, self.block_ref, self.tenant_ref))


@dataclass
class RunConfiguration:
    """Configuration for report runs."""
    qube_date: Optional[date] = None
    bos_date: Optional[date] = None
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
    property_ref: Optional[str]
    block_ref: Optional[str] 
    tenant_ref: Optional[str]
    strategy_name: str