"""FIFO Tax-Lot Manager with Capital Loss Carryforward tracking."""

from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from engine.models import TaxLot

EPSILON = 1e-7


class FIFOTaxLotManager:
    """Manages purchase tax lots per ticker using FIFO accounting,

    tracking realized capital gains/losses and capital loss carryforwards.
    """

    def __init__(self) -> None:
        # Queues of TaxLot per ticker: Dict[str, List[TaxLot]]
        self.lots: Dict[str, List[TaxLot]] = defaultdict(list)
        # Accumulated capital loss carryforward
        self.capital_loss_carryforward: float = 0.0
        # Current annual realized capital gains accumulator
        self.current_annual_realized_gain: float = 0.0
        self._lot_counter: int = 0

    @property
    def loss_carryforward(self) -> float:
        """Alias for capital_loss_carryforward."""
        return self.capital_loss_carryforward

    def add_lot(
        self,
        ticker: str,
        shares: float,
        price: float,
        year: int,
        quarter: Optional[int] = None,
    ) -> TaxLot:
        """Adds a new purchase tax lot to the FIFO queue.

        Args:
            ticker: Stock ticker symbol.
            shares: Number of shares purchased.
            price: Purchase price per share.
            year: Calendar year of purchase.
            quarter: Optional calendar quarter of purchase (1..4).

        Returns:
            The created TaxLot instance.
        """
        if shares <= 0:
            raise ValueError(f"Shares added must be positive, got {shares}")
        if price < 0:
            raise ValueError(f"Price must be non-negative, got {price}")

        self._lot_counter += 1
        q_tag = f"Q{quarter}_" if quarter is not None else ""
        lot_id = f"{ticker}_{year}_{q_tag}{self._lot_counter}"
        lot = TaxLot(
            lot_id=lot_id,
            ticker=ticker,
            shares=shares,
            purchase_price=price,
            purchase_year=year,
            purchase_quarter=quarter,
        )
        self.lots[ticker].append(lot)
        return lot

    def get_position_shares(self, ticker: str) -> float:
        """Returns total shares currently held across active lots for ticker."""
        return sum(lot.shares for lot in self.lots.get(ticker, []) if lot.shares > EPSILON)

    def get_all_positions(self) -> Dict[str, float]:
        """Returns map of ticker -> total active shares held."""
        positions: Dict[str, float] = {}
        for ticker, lots in self.lots.items():
            total = sum(lot.shares for lot in lots if lot.shares > EPSILON)
            if total > EPSILON:
                positions[ticker] = total
        return positions

    def sell_shares(
        self,
        ticker: str,
        shares_to_sell: float,
        current_price: float,
        current_year: int,
        current_quarter: Optional[int] = None,
    ) -> Tuple[float, List[TaxLot]]:
        """Depletes lots FIFO. Partial lots are split (remaining shares stay in queue).

        Calculates realized capital gain/loss = (shares_sold * current_price) - cost_basis_of_sold_shares.
        Accumulates realized gain/loss into current annual pool.

        Args:
            ticker: Stock ticker symbol.
            shares_to_sell: Number of shares to sell.
            current_price: Execution price per share.
            current_year: Calendar year of sale.

        Returns:
            Tuple of (realized_gain_on_this_sale, list_of_depleted_or_partial_lots).

        Raises:
            ValueError: If shares_to_sell > available shares (allowing for floating point epsilon 1e-7)
                        or shares_to_sell < 0.
        """
        if shares_to_sell < -EPSILON:
            raise ValueError(f"Cannot sell negative shares: {shares_to_sell}")

        if shares_to_sell <= EPSILON:
            return 0.0, []

        available_shares = self.get_position_shares(ticker)
        if shares_to_sell > available_shares + EPSILON:
            raise ValueError(
                f"Cannot sell {shares_to_sell} shares of {ticker}; only {available_shares} available."
            )

        # Cap within epsilon tolerance
        if shares_to_sell > available_shares:
            shares_to_sell = available_shares

        remaining_to_sell = shares_to_sell
        depleted_lots: List[TaxLot] = []
        total_cost_basis_sold = 0.0

        ticker_lots = self.lots.get(ticker, [])
        while remaining_to_sell > EPSILON and ticker_lots:
            lot = ticker_lots[0]
            if lot.shares <= remaining_to_sell + EPSILON:
                # Lot is completely consumed
                shares_sold = lot.shares
                total_cost_basis_sold += shares_sold * lot.purchase_price
                remaining_to_sell -= shares_sold
                depleted_lots.append(ticker_lots.pop(0))
            else:
                # Lot is partially consumed; split and keep remaining
                shares_sold = remaining_to_sell
                total_cost_basis_sold += shares_sold * lot.purchase_price
                lot.shares -= shares_sold
                sold_lot_record = TaxLot(
                    lot_id=f"{lot.lot_id}_split_{len(depleted_lots) + 1}",
                    ticker=lot.ticker,
                    shares=shares_sold,
                    purchase_price=lot.purchase_price,
                    purchase_year=lot.purchase_year,
                    purchase_quarter=lot.purchase_quarter,
                )
                depleted_lots.append(sold_lot_record)
                remaining_to_sell = 0.0

        # Clean up empty list
        if not ticker_lots and ticker in self.lots:
            del self.lots[ticker]

        gross_proceeds = shares_to_sell * current_price
        realized_gain = gross_proceeds - total_cost_basis_sold
        self.current_annual_realized_gain += realized_gain

        return realized_gain, depleted_lots

    def settle_annual_taxes(
        self, tax_rate: float, current_year: int
    ) -> Tuple[float, float, float]:
        """Nets annual realized gain/loss against accumulated loss carryforward:

        net_taxable_gain = current_annual_realized_gain - capital_loss_carryforward
        If net_taxable_gain > 0:
            tax_paid = net_taxable_gain * tax_rate
            new_loss_carryforward = 0.0
        Else:
            tax_paid = 0.0
            new_loss_carryforward = abs(net_taxable_gain)

        Resets current annual realized gains accumulator to 0.0.
        Updates internal capital_loss_carryforward to new_loss_carryforward.

        Args:
            tax_rate: Tax rate on net capital gains (e.g. 0.30).
            current_year: Calendar year being settled.

        Returns:
            Tuple of (tax_paid, net_taxable_gain, new_loss_carryforward).
        """
        net_taxable_gain = self.current_annual_realized_gain - self.capital_loss_carryforward
        if net_taxable_gain > 0:
            tax_paid = net_taxable_gain * tax_rate
            new_loss_carryforward = 0.0
        else:
            tax_paid = 0.0
            new_loss_carryforward = abs(net_taxable_gain)

        if new_loss_carryforward < 1e-9:
            new_loss_carryforward = 0.0

        self.current_annual_realized_gain = 0.0
        self.capital_loss_carryforward = new_loss_carryforward
        return tax_paid, net_taxable_gain, new_loss_carryforward

    def calculate_taxes_and_net(
        self, tax_rate: float, current_year: int
    ) -> Tuple[float, float, float]:
        """Alias for settle_annual_taxes."""
        return self.settle_annual_taxes(tax_rate, current_year)

    def get_unrealized_gain(self, current_prices: Dict[str, float]) -> float:
        """Calculates total embedded unrealized capital gain across all active lots:

        Sum for all lots: (shares * current_prices[ticker]) - (shares * purchase_price).

        Args:
            current_prices: Map of ticker -> current share price.

        Returns:
            Total unrealized capital gain/loss across all holdings.
        """
        total_unrealized = 0.0
        for ticker, lots in self.lots.items():
            for lot in lots:
                if lot.shares > EPSILON:
                    if ticker not in current_prices:
                        raise KeyError(f"Missing current price for ticker '{ticker}'")
                    total_unrealized += lot.shares * (current_prices[ticker] - lot.purchase_price)
        return total_unrealized

    def unrealized_gains(self, current_prices: Dict[str, float]) -> float:
        """Alias for get_unrealized_gain."""
        return self.get_unrealized_gain(current_prices)

    def total_cost_basis(self) -> float:
        """Returns sum of cost bases across all active lots."""
        return sum(
            lot.shares * lot.purchase_price
            for lots in self.lots.values()
            for lot in lots
            if lot.shares > EPSILON
        )
