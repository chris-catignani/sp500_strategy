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
    def year(self) -> int:
        """Alias for purchase_year."""
        return self.purchase_year

    @property
    def quarter(self) -> Optional[int]:
        """Alias for purchase_quarter."""
        return self.purchase_quarter

    @property
    def cost_basis_per_share(self) -> float:
        """Cost basis per share (purchase_price)."""
        return self.purchase_price

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
    """Annual or quarterly performance, cash flow, and tax ledger entry.

    Note on net_taxable_gain:
        Represents the signed net taxable capital position (G - C_open) for the period,
        where negative values signify unabsorbed capital losses for that period rather
        than negative taxable income.
    """
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
    spinoff_proceeds: float = 0.0
    universe: str = "sp500"
    quarter: Optional[int] = None


@dataclass
class StrategyResult:
    """Comprehensive multi-year performance and risk statistics for a strategy run.

    Wealth & Return Semantics:
        final_equity: Terminal portfolio valuation before terminal liquidation tax (identical to pre_liquidation_wealth).
        cagr: Compound annual growth rate based on pre_liquidation_wealth.
        pre_liquidation_wealth: Valuation of holdings + cash at terminal year before liquidating remaining tax lots.
        post_liquidation_wealth: Net cash realized after full terminal liquidation of all holdings and terminal tax.
        post_liquidation_cagr: Annualized return based on post_liquidation_wealth factoring terminal liquidation tax.
    """
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
    tax_drag: float = 0.0
    alpha: float = 0.0
