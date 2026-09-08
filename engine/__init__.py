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
from engine.data_loader import DataLoader
from engine.backtest import PortfolioSimulator
from engine.metrics import (
    calculate_cagr,
    calculate_cumulative_return,
    calculate_max_drawdown,
    calculate_turnover,
    calculate_tax_drag,
    calculate_terminal_metrics,
    calculate_alpha,
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
    "DataLoader",
    "PortfolioSimulator",
    "calculate_cagr",
    "calculate_cumulative_return",
    "calculate_max_drawdown",
    "calculate_turnover",
    "calculate_tax_drag",
    "calculate_terminal_metrics",
    "calculate_alpha",
]

