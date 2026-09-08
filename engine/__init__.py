"""S&P 500 Top N Strategy Backtesting Engine."""

from engine.models import (
    AnnualLedgerEntry,
    ConstituentSnapshot,
    HoldingTarget,
    StrategyResult,
    TaxLot,
    TradeOrder,
)
from engine.tax_lots import FIFOTaxLotManager
from engine.selector import (
    BaseSelector,
    MarketCapSelector,
    PerformanceSelector,
)

__all__ = [
    "AnnualLedgerEntry",
    "ConstituentSnapshot",
    "HoldingTarget",
    "StrategyResult",
    "TaxLot",
    "TradeOrder",
    "FIFOTaxLotManager",
    "BaseSelector",
    "MarketCapSelector",
    "PerformanceSelector",
]
