"""Two-Phase Portfolio Simulation Engine for S&P 500 Top N Strategies."""

from typing import Dict, List, Optional

from engine.data_loader import DataLoader
from engine.models import AnnualLedgerEntry, StrategyResult, TradeOrder
from engine.selector import BaseSelector, MarketCapSelector
from engine.tax_lots import FIFOTaxLotManager
from engine.metrics import (
    calculate_benchmark_annual_series,
    calculate_cagr,
    calculate_cumulative_return,
    calculate_max_drawdown,
    calculate_terminal_metrics,
)


class PortfolioSimulator:
    """Simulates annual Top N rebalancing strategies with FIFO tax lot tracking."""

    def __init__(self, data_loader: Optional[DataLoader] = None) -> None:
        """Initialize the simulator with data loader and empty tracking structures.

        Args:
            data_loader: Optional DataLoader instance. If None, instantiate a default DataLoader.
        """
        self.data_loader: DataLoader = data_loader if data_loader is not None else DataLoader()
        self.trade_history: List[TradeOrder] = []
        self.cash_history: List[float] = []
        self.tax_manager: FIFOTaxLotManager = FIFOTaxLotManager()
        self.cash: float = 0.0

    def get_trades(self) -> List[TradeOrder]:
        """Return a copy of the executed trade order history.

        Returns:
            List of TradeOrder objects.
        """
        return list(self.trade_history)

    def run_simulation(
        self,
        start_year: int,
        end_year: int,
        n: int = 5,
        selector: Optional[BaseSelector] = None,
        is_after_tax: bool = False,
        tax_rate: float = 0.30,
        initial_capital: float = 10000.0,
        universe: str = "sp500",
        rebalance_frequency: str = "annual",
    ) -> StrategyResult:
        """Execute a multi-year backtest simulation.

        Args:
            start_year: Calendar year for initial allocation (e.g. 2014).
            end_year: Terminal calendar year (e.g. 2024).
            n: Number of top constituents to select (e.g. 3, 5, 10).
            selector: Optional constituent selector. Defaults to MarketCapSelector(n=n).
            is_after_tax: Whether to deduct annual capital gains taxes and terminal tax.
            tax_rate: Flat capital gains tax rate applied to net taxable gains.
            initial_capital: Starting dollar capital basis (default 10,000.0).
            universe: Identifier of target universe ('sp500' or 'world').
            rebalance_frequency: 'annual' (default) or 'quarterly'.

        Returns:
            StrategyResult with full metrics and annual ledger history.

        Raises:
            ValueError: If parameters are invalid.
        """
        if end_year <= start_year:
            raise ValueError(
                f"end_year ({end_year}) must be strictly greater than start_year ({start_year})"
            )
        if n <= 0:
            raise ValueError(f"n must be positive, got {n}")
        if initial_capital <= 0.0:
            raise ValueError(f"initial_capital must be positive, got {initial_capital}")
        if not (0.0 <= tax_rate <= 1.0):
            raise ValueError(f"tax_rate must be between 0.0 and 1.0, got {tax_rate}")
        if rebalance_frequency not in ("annual", "quarterly"):
            raise ValueError(
                f"rebalance_frequency must be 'annual' or 'quarterly', got '{rebalance_frequency}'"
            )

        # Reset simulator state for this simulation run
        self.trade_history = []
        self.cash_history = []
        self.tax_manager = FIFOTaxLotManager()
        self.cash = 0.0

        if selector is None:
            selector = MarketCapSelector(n=n)

        prefix = "World_" if universe in ("world", "all_world") else ""
        freq_tag = "_Quarterly" if rebalance_frequency == "quarterly" else ""
        strategy_name = f"{prefix}Top_{n}_{selector.__class__.__name__.replace('Selector', '')}{freq_tag}"

        # Initial Allocation at start_year (Q4 if quarterly, annual start if annual)
        if rebalance_frequency == "quarterly":
            u_start = self.data_loader.load_quarterly_universe(start_year, 4, universe=universe)
        else:
            u_start = self.data_loader.load_universe(start_year, universe=universe)
        initial_targets = selector.select(u_start, n=n)

        for target in initial_targets:
            if rebalance_frequency == "quarterly":
                price = self.data_loader.get_quarterly_price(target.ticker, start_year, 4)
            else:
                price = self.data_loader.get_price(target.ticker, start_year)
            target_dollar = initial_capital * target.target_weight
            target_shares = target_dollar / price
            self.tax_manager.add_lot(
                target.ticker,
                target_shares,
                price,
                start_year,
                quarter=4 if rebalance_frequency == "quarterly" else None,
            )
            self.trade_history.append(
                TradeOrder(
                    ticker=target.ticker,
                    action="BUY",
                    shares=target_shares,
                    price=price,
                    year=start_year,
                    quarter=4 if rebalance_frequency == "quarterly" else None,
                    realized_gain=0.0,
                )
            )

        start_value = initial_capital
        annual_history: List[AnnualLedgerEntry] = []
        quarterly_history: List[AnnualLedgerEntry] = []

        # Rebalancing Loop for subsequent years
        if rebalance_frequency == "quarterly":
            for current_year in range(start_year + 1, end_year + 1):
                year_start_value = start_value
                year_dividends = 0.0
                year_div_tax = 0.0
                year_realized_gain = 0.0
                year_net_taxable_gain = 0.0
                year_tax_paid = 0.0
                year_cap_tax = 0.0
                year_turnover_sum = 0.0

                for q in (1, 2, 3, 4):
                    q_start_value = start_value
                    positions = self.tax_manager.get_all_positions()
                    q_dividends = sum(
                        shares * self.data_loader.get_quarterly_dividend(ticker, current_year, q)
                        for ticker, shares in positions.items()
                    )
                    self.cash += q_dividends

                    holdings_value_pretax = sum(
                        shares * self.data_loader.get_quarterly_price(ticker, current_year, q)
                        for ticker, shares in positions.items()
                    )
                    total_pretax_value = holdings_value_pretax + self.cash
                    gross_return = (
                        (total_pretax_value - q_start_value) / q_start_value
                        if q_start_value > 0.0
                        else 0.0
                    )

                    u_curr = self.data_loader.load_quarterly_universe(current_year, q, universe=universe)
                    targets_curr = selector.select(u_curr, n=n)
                    target_weights: Dict[str, float] = {
                        t.ticker: t.target_weight for t in targets_curr
                    }
                    prices_curr: Dict[str, float] = {
                        t.ticker: self.data_loader.get_quarterly_price(t.ticker, current_year, q)
                        for t in targets_curr
                    }
                    prov_target_shares: Dict[str, float] = {
                        ticker: (total_pretax_value * weight) / prices_curr[ticker]
                        for ticker, weight in target_weights.items()
                    }

                    gross_sell_proceeds = 0.0
                    q_realized_gain = 0.0

                    for ticker, held_shares in list(positions.items()):
                        price = self.data_loader.get_quarterly_price(ticker, current_year, q)
                        if ticker not in target_weights:
                            gain, _ = self.tax_manager.sell_shares(
                                ticker, held_shares, price, current_year, q
                            )
                            proceeds = held_shares * price
                            gross_sell_proceeds += proceeds
                            self.cash += proceeds
                            q_realized_gain += gain
                            self.trade_history.append(
                                TradeOrder(
                                    ticker=ticker,
                                    action="SELL",
                                    shares=held_shares,
                                    price=price,
                                    year=current_year,
                                    quarter=q,
                                    realized_gain=gain,
                                )
                            )
                        elif held_shares > prov_target_shares[ticker] + 1e-7:
                            delta_shares = held_shares - prov_target_shares[ticker]
                            gain, _ = self.tax_manager.sell_shares(
                                ticker, delta_shares, price, current_year, q
                            )
                            proceeds = delta_shares * price
                            gross_sell_proceeds += proceeds
                            self.cash += proceeds
                            q_realized_gain += gain
                            self.trade_history.append(
                                TradeOrder(
                                    ticker=ticker,
                                    action="SELL",
                                    shares=delta_shares,
                                    price=price,
                                    year=current_year,
                                    quarter=q,
                                    realized_gain=gain,
                                )
                            )

                    if is_after_tax:
                        tax_div = q_dividends * tax_rate
                        self.cash -= tax_div
                        total_tax_paid = tax_div
                        last_loss_cf = 0.0
                        last_net_taxable = 0.0

                        for iteration in range(20):
                            tax_cap_step, net_taxable, loss_cf = (
                                self.tax_manager.settle_annual_taxes(tax_rate, current_year)
                            )
                            total_tax_paid += tax_cap_step
                            self.cash -= tax_cap_step
                            last_loss_cf = loss_cf
                            last_net_taxable += net_taxable

                            net_investable_equity = total_pretax_value - total_tax_paid
                            final_target_shares = {
                                ticker: (net_investable_equity * weight) / prices_curr[ticker]
                                for ticker, weight in target_weights.items()
                            }

                            additional_trims = 0
                            for ticker, held_shares in list(self.tax_manager.get_all_positions().items()):
                                if ticker in final_target_shares:
                                    target_sh = final_target_shares[ticker]
                                    if held_shares > target_sh + 1e-7:
                                        trim_sh = held_shares - target_sh
                                        trim_price = prices_curr[ticker]
                                        gain, _ = self.tax_manager.sell_shares(
                                            ticker, trim_sh, trim_price, current_year, q
                                        )
                                        proceeds = trim_sh * trim_price
                                        gross_sell_proceeds += proceeds
                                        self.cash += proceeds
                                        q_realized_gain += gain
                                        additional_trims += 1
                                        self.trade_history.append(
                                            TradeOrder(
                                                ticker=ticker,
                                                action="SELL",
                                                shares=trim_sh,
                                                price=trim_price,
                                                year=current_year,
                                                quarter=q,
                                                realized_gain=gain,
                                            )
                                        )
                            if additional_trims == 0:
                                break
                        capital_gains_tax_paid = total_tax_paid - tax_div
                    else:
                        total_tax_paid = 0.0
                        tax_div = 0.0
                        capital_gains_tax_paid = 0.0
                        last_net_taxable = 0.0
                        last_loss_cf = self.tax_manager.loss_carryforward
                        net_investable_equity = total_pretax_value
                        final_target_shares = prov_target_shares

                    gross_buy_expenditure = 0.0
                    current_positions_before_buys = self.tax_manager.get_all_positions()

                    for target in targets_curr:
                        t_ticker = target.ticker
                        price = prices_curr[t_ticker]
                        target_sh = final_target_shares[t_ticker]
                        held_sh = current_positions_before_buys.get(t_ticker, 0.0)
                        needed_sh = target_sh - held_sh

                        if needed_sh > 1e-7:
                            cost = needed_sh * price
                            if cost > self.cash:
                                needed_sh = max(0.0, self.cash / price)
                                cost = needed_sh * price
                            if needed_sh > 1e-7:
                                self.tax_manager.add_lot(t_ticker, needed_sh, price, current_year, q)
                                gross_buy_expenditure += cost
                                self.cash -= cost
                                self.trade_history.append(
                                    TradeOrder(
                                        ticker=t_ticker,
                                        action="BUY",
                                        shares=needed_sh,
                                        price=price,
                                        year=current_year,
                                        quarter=q,
                                        realized_gain=0.0,
                                    )
                                )

                    if self.cash < 0.0 and abs(self.cash) < 1e-7:
                        self.cash = 0.0

                    final_positions = self.tax_manager.get_all_positions()
                    final_holdings_val = sum(
                        shares * self.data_loader.get_quarterly_price(ticker, current_year, q)
                        for ticker, shares in final_positions.items()
                    )
                    ending_value_aftertax = final_holdings_val + self.cash

                    turnover = (
                        (gross_sell_proceeds + gross_buy_expenditure) / (2.0 * total_pretax_value)
                        if total_pretax_value > 0.0
                        else 0.0
                    )

                    spx_prev_q = self.data_loader.get_spx_tr_quarterly_level(
                        current_year if q > 1 else current_year - 1,
                        q - 1 if q > 1 else 4,
                    )
                    spx_curr_q = self.data_loader.get_spx_tr_quarterly_level(current_year, q)
                    spx_ret = (spx_curr_q - spx_prev_q) / spx_prev_q if spx_prev_q > 0 else 0.0

                    q_entry = AnnualLedgerEntry(
                        year=current_year,
                        quarter=q,
                        start_value=q_start_value,
                        gross_return=gross_return,
                        ending_value_pretax=total_pretax_value,
                        realized_capital_gain=q_realized_gain,
                        net_taxable_gain=last_net_taxable,
                        tax_paid=total_tax_paid,
                        loss_carryforward=last_loss_cf,
                        ending_value_aftertax=ending_value_aftertax,
                        spx_return=spx_ret,
                        turnover=turnover,
                        holdings=dict(final_positions),
                        cash=self.cash,
                        dividend_income=q_dividends,
                        dividend_tax_paid=tax_div,
                        capital_gains_tax_paid=capital_gains_tax_paid,
                        universe=universe,
                    )
                    quarterly_history.append(q_entry)

                    year_dividends += q_dividends
                    year_div_tax += tax_div
                    year_realized_gain += q_realized_gain
                    year_net_taxable_gain += last_net_taxable
                    year_tax_paid += total_tax_paid
                    year_cap_tax += capital_gains_tax_paid
                    year_turnover_sum += turnover

                    start_value = ending_value_aftertax if is_after_tax else total_pretax_value

                # Synthesize annual ledger entry for annual_history
                spx_ann_prev = self.data_loader.get_spx_tr_level(current_year - 1)
                spx_ann_curr = self.data_loader.get_spx_tr_level(current_year)
                spx_ann_ret = (spx_ann_curr - spx_ann_prev) / spx_ann_prev if spx_ann_prev > 0 else 0.0
                year_gross_return = (
                    (quarterly_history[-1].ending_value_pretax - year_start_value) / year_start_value
                    if year_start_value > 0.0
                    else 0.0
                )

                ann_entry = AnnualLedgerEntry(
                    year=current_year,
                    quarter=None,
                    start_value=year_start_value,
                    gross_return=year_gross_return,
                    ending_value_pretax=quarterly_history[-1].ending_value_pretax,
                    realized_capital_gain=year_realized_gain,
                    net_taxable_gain=year_net_taxable_gain,
                    tax_paid=year_tax_paid,
                    loss_carryforward=self.tax_manager.loss_carryforward,
                    ending_value_aftertax=quarterly_history[-1].ending_value_aftertax,
                    spx_return=spx_ann_ret,
                    turnover=year_turnover_sum,
                    holdings=dict(self.tax_manager.get_all_positions()),
                    cash=self.cash,
                    dividend_income=year_dividends,
                    dividend_tax_paid=year_div_tax,
                    capital_gains_tax_paid=year_cap_tax,
                    universe=universe,
                )
                annual_history.append(ann_entry)
        else:
            # Annual Rebalancing Loop for subsequent years
            for current_year in range(start_year + 1, end_year + 1):
                # Step 1: Pre-Rebalance Dividend Receipt & Cash Pooling
                positions = self.tax_manager.get_all_positions()
                annual_dividends = sum(
                    shares * self.data_loader.get_dividend(ticker, current_year)
                    for ticker, shares in positions.items()
                )
                self.cash += annual_dividends

                # Step 2: Pre-Tax Valuation
                holdings_value_pretax = sum(
                    shares * self.data_loader.get_price(ticker, current_year)
                    for ticker, shares in positions.items()
                )
                total_pretax_value = holdings_value_pretax + self.cash
                gross_return = (
                    (total_pretax_value - start_value) / start_value
                    if start_value > 0.0
                    else 0.0
                )

                # Step 3: Provisional Target Weights
                u_curr = self.data_loader.load_universe(current_year, universe=universe)
                targets_curr = selector.select(u_curr, n=n)
                target_weights: Dict[str, float] = {
                    t.ticker: t.target_weight for t in targets_curr
                }
                prices_curr: Dict[str, float] = {
                    t.ticker: self.data_loader.get_price(t.ticker, current_year)
                    for t in targets_curr
                }

                prov_target_shares: Dict[str, float] = {
                    ticker: (total_pretax_value * weight) / prices_curr[ticker]
                    for ticker, weight in target_weights.items()
                }

                # Step 4: Phase 1 (Sells: Full Exits & Overweight Trims)
                gross_sell_proceeds = 0.0
                annual_realized_gain = 0.0

                for ticker, held_shares in list(positions.items()):
                    price = self.data_loader.get_price(ticker, current_year)
                    if ticker not in target_weights:
                        # Full exit: constituent dropped out of Top N
                        gain, _ = self.tax_manager.sell_shares(
                            ticker, held_shares, price, current_year
                        )
                        proceeds = held_shares * price
                        gross_sell_proceeds += proceeds
                        self.cash += proceeds
                        annual_realized_gain += gain
                        self.trade_history.append(
                            TradeOrder(
                                ticker=ticker,
                                action="SELL",
                                shares=held_shares,
                                price=price,
                                year=current_year,
                                realized_gain=gain,
                            )
                        )
                    elif held_shares > prov_target_shares[ticker] + 1e-7:
                        # Overweight trim down to provisional target
                        delta_shares = held_shares - prov_target_shares[ticker]
                        gain, _ = self.tax_manager.sell_shares(
                            ticker, delta_shares, price, current_year
                        )
                        proceeds = delta_shares * price
                        gross_sell_proceeds += proceeds
                        self.cash += proceeds
                        annual_realized_gain += gain
                        self.trade_history.append(
                            TradeOrder(
                                ticker=ticker,
                                action="SELL",
                                shares=delta_shares,
                                price=price,
                                year=current_year,
                                realized_gain=gain,
                            )
                        )

                # Step 5: Phase 2 (Tax Settlement, Secondary Trims & Buys)
                if is_after_tax:
                    tax_div = annual_dividends * tax_rate
                    self.cash -= tax_div
                    total_tax_paid = tax_div
                    last_loss_cf = 0.0
                    last_net_taxable = 0.0

                    for iteration in range(20):
                        tax_cap_step, net_taxable, loss_cf = (
                            self.tax_manager.settle_annual_taxes(tax_rate, current_year)
                        )
                        total_tax_paid += tax_cap_step
                        self.cash -= tax_cap_step
                        last_loss_cf = loss_cf
                        last_net_taxable += net_taxable

                        net_investable_equity = total_pretax_value - total_tax_paid
                        final_target_shares = {
                            ticker: (net_investable_equity * weight) / prices_curr[ticker]
                            for ticker, weight in target_weights.items()
                        }

                        additional_trims = 0
                        for ticker, held_shares in list(self.tax_manager.get_all_positions().items()):
                            if ticker in final_target_shares:
                                target_sh = final_target_shares[ticker]
                                if held_shares > target_sh + 1e-7:
                                    trim_sh = held_shares - target_sh
                                    trim_price = prices_curr[ticker]
                                    gain, _ = self.tax_manager.sell_shares(
                                        ticker, trim_sh, trim_price, current_year
                                    )
                                    proceeds = trim_sh * trim_price
                                    gross_sell_proceeds += proceeds
                                    self.cash += proceeds
                                    annual_realized_gain += gain
                                    additional_trims += 1
                                    self.trade_history.append(
                                        TradeOrder(
                                            ticker=ticker,
                                            action="SELL",
                                            shares=trim_sh,
                                            price=trim_price,
                                            year=current_year,
                                            realized_gain=gain,
                                        )
                                    )
                        if additional_trims == 0:
                            break

                    capital_gains_tax_paid = total_tax_paid - tax_div
                    net_taxable_gain = last_net_taxable
                    loss_carryforward = last_loss_cf
                    tax_paid = total_tax_paid
                    dividend_tax_paid = tax_div
                else:
                    tax_paid = 0.0
                    dividend_tax_paid = 0.0
                    capital_gains_tax_paid = 0.0
                    net_taxable_gain = 0.0
                    loss_carryforward = self.tax_manager.loss_carryforward
                    net_investable_equity = total_pretax_value
                    final_target_shares = prov_target_shares

                # Step 6: Buys with Cash Clamping
                gross_buy_expenditure = 0.0
                current_positions_before_buys = self.tax_manager.get_all_positions()

                for target in targets_curr:
                    t_ticker = target.ticker
                    price = prices_curr[t_ticker]
                    target_sh = final_target_shares[t_ticker]
                    held_sh = current_positions_before_buys.get(t_ticker, 0.0)
                    needed_sh = target_sh - held_sh

                    if needed_sh > 1e-7:
                        cost = needed_sh * price
                        if cost > self.cash:
                            needed_sh = max(0.0, self.cash / price)
                            cost = needed_sh * price
                        if needed_sh > 1e-7:
                            self.tax_manager.add_lot(t_ticker, needed_sh, price, current_year)
                            gross_buy_expenditure += cost
                            self.cash -= cost
                            self.trade_history.append(
                                TradeOrder(
                                    ticker=t_ticker,
                                    action="BUY",
                                    shares=needed_sh,
                                    price=price,
                                    year=current_year,
                                    realized_gain=0.0,
                                )
                            )

                if self.cash < 0.0 and abs(self.cash) < 1e-7:
                    self.cash = 0.0

                # Step 7: Ledger Recording
                final_positions = self.tax_manager.get_all_positions()
                final_holdings_val = sum(
                    shares * self.data_loader.get_price(ticker, current_year)
                    for ticker, shares in final_positions.items()
                )
                ending_value_aftertax = final_holdings_val + self.cash

                turnover = (
                    (gross_sell_proceeds + gross_buy_expenditure) / (2.0 * total_pretax_value)
                    if total_pretax_value > 0.0
                    else 0.0
                )

                spx_prev = self.data_loader.get_spx_tr_level(current_year - 1)
                spx_curr = self.data_loader.get_spx_tr_level(current_year)
                spx_return = (spx_curr - spx_prev) / spx_prev if spx_prev > 0.0 else 0.0

                final_holdings = self.tax_manager.get_all_positions()
                entry = AnnualLedgerEntry(
                    year=current_year,
                    start_value=start_value,
                    gross_return=gross_return,
                    ending_value_pretax=total_pretax_value,
                    realized_capital_gain=annual_realized_gain,
                    net_taxable_gain=net_taxable_gain,
                    tax_paid=tax_paid,
                    loss_carryforward=loss_carryforward,
                    ending_value_aftertax=ending_value_aftertax,
                    spx_return=spx_return,
                    turnover=turnover,
                    holdings=dict(final_holdings),
                    cash=self.cash,
                    dividend_income=annual_dividends,
                    dividend_tax_paid=dividend_tax_paid,
                    capital_gains_tax_paid=capital_gains_tax_paid,
                    universe=universe,
                )
                annual_history.append(entry)

                # Next period's start value
                start_value = ending_value_aftertax if is_after_tax else total_pretax_value

        # Terminal Liquidation & Metrics
        pre_liquidation_wealth = (
            annual_history[-1].ending_value_aftertax
            if is_after_tax
            else annual_history[-1].ending_value_pretax
        )
        final_equity = pre_liquidation_wealth
        total_years = end_year - start_year

        cumulative_return = calculate_cumulative_return(initial_capital, pre_liquidation_wealth)
        cagr = calculate_cagr(initial_capital, pre_liquidation_wealth, total_years)
        total_taxes_paid = sum(e.tax_paid for e in annual_history)

        # Maximum Drawdown
        valuation_series = [initial_capital] + [
            e.ending_value_aftertax if is_after_tax else e.ending_value_pretax
            for e in annual_history
        ]
        max_dd = calculate_max_drawdown(valuation_series)

        # Embedded unrealized capital gains at terminal year
        terminal_positions = self.tax_manager.get_all_positions()
        terminal_prices = {
            ticker: self.data_loader.get_price(ticker, end_year)
            for ticker in terminal_positions
        }
        unrealized_gain = self.tax_manager.get_unrealized_gain(terminal_prices)

        term_metrics = calculate_terminal_metrics(
            pre_liquidation_wealth=pre_liquidation_wealth,
            unrealized_gain=unrealized_gain,
            loss_carryforward=self.tax_manager.loss_carryforward,
            tax_rate=tax_rate,
            initial_capital=initial_capital,
            years=total_years,
            is_after_tax=is_after_tax,
        )
        post_liquidation_wealth = term_metrics["post_liquidation_wealth"]
        post_liquidation_cagr = term_metrics["post_liquidation_cagr"]

        total_dividends_received = sum(e.dividend_income for e in annual_history)
        total_dividend_taxes_paid = sum(e.dividend_tax_paid for e in annual_history)

        return StrategyResult(
            strategy_name=strategy_name,
            n=n,
            start_year=start_year,
            end_year=end_year,
            is_after_tax=is_after_tax,
            tax_rate=tax_rate,
            initial_capital=initial_capital,
            final_equity=final_equity,
            cagr=cagr,
            cumulative_return=cumulative_return,
            max_drawdown=max_dd,
            total_taxes_paid=total_taxes_paid,
            pre_liquidation_wealth=pre_liquidation_wealth,
            post_liquidation_wealth=post_liquidation_wealth,
            post_liquidation_cagr=post_liquidation_cagr,
            annual_history=annual_history,
            quarterly_history=quarterly_history,
            total_dividends_received=total_dividends_received,
            total_dividend_taxes_paid=total_dividend_taxes_paid,
            universe=universe,
            rebalance_frequency=rebalance_frequency,
        )
