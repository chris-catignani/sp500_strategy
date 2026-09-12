"""Core data models and type schemas for S&P 500 Top N Strategy backtesting engine."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class ConstituentSnapshot:
    """Point-in-time constituent information at year-end or quarter-end."""
    ticker: str
    name: str
    market_cap_weight: float
    trailing_1y_return: float
    year: int
    quarter: Optional[int] = None


@dataclass
class HoldingTarget:
    """Target portfolio allocation for a single constituent."""
    ticker: str
    target_weight: float
    target_dollar: float = 0.0
    target_shares: float = 0.0


@dataclass
class TaxLot:
    """Individual tax lot purchased at a specific price and period for FIFO accounting."""
    lot_id: str
    ticker: str
    shares: float
    purchase_price: float
    purchase_year: int
    purchase_quarter: Optional[int] = None

    @property
    def quarter(self) -> Optional[int]:
        """Alias for purchase_quarter."""
        return self.purchase_quarter

    def cost_basis(self) -> float:
        """Calculate the total dollar cost basis for this lot."""
        return self.shares * self.purchase_price


@dataclass
class TradeOrder:
    """Rebalancing execution order for buy or sell transactions."""
    ticker: str
    action: str  # 'BUY' or 'SELL'
    shares: float
    price: float
    year: int
    quarter: Optional[int] = None
    realized_gain: float = 0.0


@dataclass
class AnnualLedgerEntry:
    """Annual or quarterly performance, cash flow, and tax ledger entry."""
    year: int
    start_value: float
    gross_return: float
    ending_value_pretax: float
    realized_capital_gain: float
    net_taxable_gain: float
    tax_paid: float
    loss_carryforward: float
    ending_value_aftertax: float
    spx_return: float
    turnover: float
    holdings: Dict[str, Any] = field(default_factory=dict)
    cash: float = 0.0
    dividend_income: float = 0.0
    dividend_tax_paid: float = 0.0
    capital_gains_tax_paid: float = 0.0
    universe: str = "sp500"
    quarter: Optional[int] = None


@dataclass
class StrategyResult:
    """Comprehensive multi-year performance and risk statistics for a strategy run."""
    strategy_name: str
    n: int
    start_year: int
    end_year: int
    is_after_tax: bool
    tax_rate: float
    initial_capital: float
    final_equity: float
    cagr: float
    cumulative_return: float
    max_drawdown: float
    total_taxes_paid: float
    pre_liquidation_wealth: float
    post_liquidation_wealth: float
    post_liquidation_cagr: float
    annual_history: List[AnnualLedgerEntry] = field(default_factory=list)
    quarterly_history: List[AnnualLedgerEntry] = field(default_factory=list)
    total_dividends_received: float = 0.0
    total_dividend_taxes_paid: float = 0.0
    universe: str = "sp500"
    rebalance_frequency: str = "annual"
