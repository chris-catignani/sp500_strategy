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
        # Accumulated capital loss carryforward (closing carryforward of last settled period)
        self.capital_loss_carryforward: float = 0.0
        # Current annual realized capital gains accumulator
        self.current_annual_realized_gain: float = 0.0
        # Active calendar tax year
        self.current_tax_year: Optional[int] = None
        # Opening capital loss carryforward at start of active calendar year
        self.opening_loss_carryforward: float = 0.0
        # Cumulative capital gains tax paid within active calendar year
        self.annual_capital_gains_tax_paid: float = 0.0
        self._lot_counter: int = 0

    def start_tax_year(self, year: int) -> None:
        """Explicitly starts a new calendar tax year, rolling over loss carryforwards.

        Under US individual tax rules, capital loss carryforwards from prior years offset
        current year capital gains, but current year losses never carry back to prior years.
        Within a calendar year, intra-year gains and losses net symmetrically.

        Args:
            year: Calendar year being started.
        """
        if self.current_tax_year != year:
            if self.current_tax_year is not None:
                self.current_annual_realized_gain = 0.0
            self.current_tax_year = year
            self.opening_loss_carryforward = self.capital_loss_carryforward
            self.annual_capital_gains_tax_paid = 0.0

    def _check_calendar_year_rollover(self, current_year: int) -> None:
        """Ensures the tax lot manager is synced to current_year."""
        if self.current_tax_year != current_year:
            self.start_tax_year(current_year)

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

    def get_lots(self, ticker: str) -> List[TaxLot]:
        """Return a copy of active lots for a given ticker."""
        return list(self.lots.get(ticker, []))

    def adjust_basis_ratio(
        self,
        ticker: str,
        ratio: float,
        gross_proceeds: Optional[float] = None,
        current_year: Optional[int] = None,
    ) -> float:
        """Adjust cost basis per share (purchase_price) of all open lots following a corporate spinoff,
        and optionally realize capital gain/loss on the liquidated child shares.

        Under IRC Section 358, the cost basis of the parent shares is apportioned between
        the parent and the spun-off child shares based on relative fair market value:
            Parent Basis = Prior Basis * ratio
            Child Basis = Prior Basis * (1.0 - ratio)

        When the child shares are immediately liquidated for gross_proceeds (IRC Section 1001):
            Realized Gain = gross_proceeds - Child Basis

        Args:
            ticker: Stock ticker symbol of the parent company.
            ratio: Basis retention ratio for the parent stock in (0.0, 1.0].
            gross_proceeds: Total cash proceeds received from selling the spun-off child shares.
                            If provided, computes and records the realized capital gain/loss.
            current_year: Optional calendar year of the spinoff corporate action.

        Returns:
            Realized capital gain/loss on the liquidated child shares (0.0 if gross_proceeds is None).
        """
        if current_year is not None:
            self._check_calendar_year_rollover(current_year)

        if not (0.0 < ratio <= 1.0):
            raise ValueError(f"Invalid basis retention ratio: {ratio}. Must be in (0.0, 1.0].")
        if ratio == 1.0:
            if gross_proceeds is not None and gross_proceeds > 0.0:
                self.current_annual_realized_gain += gross_proceeds
                return gross_proceeds
            return 0.0

        child_basis = 0.0
        if ticker in self.lots:
            for lot in self.lots[ticker]:
                old_price = lot.purchase_price
                new_price = round(old_price * ratio, 4)
                child_basis += lot.shares * (old_price - new_price)
                lot.purchase_price = new_price

        if gross_proceeds is not None:
            child_realized_gain = gross_proceeds - child_basis
            self.current_annual_realized_gain += child_realized_gain
            return child_realized_gain

        return 0.0

    def exchange_lots(
        self,
        ticker: str,
        new_ticker: str,
        share_multiplier: float,
    ) -> float:
        """Move every open lot of ticker into new_ticker under IRC Section 368.

        A statutory reorganisation is not a disposal: the holder's basis carries forward
        into the shares received and no gain or loss is realised. Each lot keeps its total
        cost basis and its purchase date, and only the share count changes, so a lot bought
        before the reorganisation still depletes before one bought after it.

            new_shares = old_shares * share_multiplier
            new_basis_per_share = old_basis_per_share / share_multiplier

        Args:
            ticker: Symbol being converted away.
            new_ticker: Symbol received in the reorganisation.
            share_multiplier: Shares received per share surrendered, expressed in the
                share terms of each series (so not necessarily the filing's exchange
                ratio, which is in as-traded terms on both sides).

        Returns:
            Total shares of new_ticker created.

        Raises:
            ValueError: If share_multiplier is not positive.
        """
        if share_multiplier <= 0.0:
            raise ValueError(f"share_multiplier must be positive, got {share_multiplier}")
        if ticker == new_ticker:
            raise ValueError(f"Cannot exchange '{ticker}' into itself")

        shares_created = 0.0
        for lot in self.lots.get(ticker, []):
            if lot.shares <= EPSILON:
                continue
            lot.ticker = new_ticker
            lot.shares *= share_multiplier
            lot.purchase_price /= share_multiplier
            shares_created += lot.shares
            self.lots[new_ticker].append(lot)

        if ticker in self.lots:
            del self.lots[ticker]

        # Where the portfolio already held the acquirer, the arriving lots are older than
        # some of the lots already queued and appending them would put them behind. FIFO
        # is an ordering by purchase date, not by arrival, and a reorganisation does not
        # give the surrendered shares a new one. Python's sort is stable, so lots bought
        # in the same period keep the order they were bought in.
        self.lots[new_ticker].sort(key=lambda l: (l.purchase_year, l.purchase_quarter or 0))

        return shares_created

    def recognize_boot(
        self,
        ticker: str,
        cash_per_share: float,
        stock_value_per_share: float,
        current_year: int,
        current_quarter: Optional[int] = None,
    ) -> float:
        """Recognise gain on the cash leg of a reorganisation under IRC Section 356.

        Where a reorganisation pays cash alongside shares, the cash is "boot": gain is
        recognised up to the cash received, but never more than the gain actually realised,
        and a loss is not recognised at all. Basis in the shares received is reduced by the
        cash and increased by the gain recognised:

            realized   = shares * (cash_per_share + stock_value_per_share) - basis
            recognized = min(max(realized, 0), shares * cash_per_share)
            new_basis  = basis - shares * cash_per_share + recognized

        Applied per lot, so a lot standing at a loss recognises nothing while a lot
        standing at a gain recognises its own, rather than the two netting first.

        Args:
            ticker: Symbol being converted away.
            cash_per_share: Cash consideration per share surrendered.
            stock_value_per_share: Value per share surrendered of the stock leg.
            current_year: Calendar year of the reorganisation.
            current_quarter: Optional calendar quarter.

        Returns:
            Total gain recognised, already accumulated into the annual realised pool.
        """
        self._check_calendar_year_rollover(current_year)

        if cash_per_share < 0.0:
            raise ValueError(f"cash_per_share must be non-negative, got {cash_per_share}")

        total_recognized = 0.0
        for lot in self.lots.get(ticker, []):
            if lot.shares <= EPSILON:
                continue
            basis = lot.shares * lot.purchase_price
            cash = lot.shares * cash_per_share
            realized = lot.shares * (cash_per_share + stock_value_per_share) - basis
            recognized = min(max(realized, 0.0), cash)
            total_recognized += recognized
            lot.purchase_price = (basis - cash + recognized) / lot.shares

        self.current_annual_realized_gain += total_recognized
        return total_recognized

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
        self._check_calendar_year_rollover(current_year)

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
        """Nets cumulative annual realized gain/loss against opening loss carryforward:

        net_taxable_gain = current_annual_realized_gain - opening_loss_carryforward
        If net_taxable_gain > 0:
            cum_tax_liability = net_taxable_gain * tax_rate
            new_loss_carryforward = 0.0
        Else:
            cum_tax_liability = 0.0
            new_loss_carryforward = abs(net_taxable_gain)

        tax_delta = cum_tax_liability - annual_capital_gains_tax_paid

        If tax_delta > 0, additional capital gains tax is paid.
        If tax_delta < 0, earlier intra-year estimated tax overpayment is refunded/credited.
        Capital loss refunds can never exceed annual_capital_gains_tax_paid (cum_tax_liability >= 0),
        ensuring capital losses never offset or refund dividend taxes.

        Args:
            tax_rate: Tax rate on net capital gains (e.g. 0.30).
            current_year: Calendar year being settled.

        Returns:
            Tuple of (tax_delta, net_taxable_gain, new_loss_carryforward).
        """
        self._check_calendar_year_rollover(current_year)

        net_taxable_gain = self.current_annual_realized_gain - self.opening_loss_carryforward
        if net_taxable_gain > 0:
            cum_tax_liability = net_taxable_gain * tax_rate
            new_loss_carryforward = 0.0
        else:
            cum_tax_liability = 0.0
            new_loss_carryforward = abs(net_taxable_gain)

        if new_loss_carryforward < 1e-9:
            new_loss_carryforward = 0.0

        tax_delta = cum_tax_liability - self.annual_capital_gains_tax_paid
        if abs(tax_delta) < 1e-9:
            tax_delta = 0.0

        self.annual_capital_gains_tax_paid = cum_tax_liability
        self.capital_loss_carryforward = new_loss_carryforward
        return tax_delta, net_taxable_gain, new_loss_carryforward

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
