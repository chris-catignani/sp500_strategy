"""Two-Phase Portfolio Simulation Engine for S&P 500 Top N Strategies."""

from typing import Dict, List, Optional

from engine.data_loader import DataLoader
from engine.models import AnnualLedgerEntry, StrategyResult, TradeOrder
from engine.selector import BaseSelector, MarketCapSelector
from engine.tax_lots import FIFOTaxLotManager
from engine.metrics import (
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

        # Reset simulator state for this simulation run
        self.trade_history = []
        self.cash_history = []
        self.tax_manager = FIFOTaxLotManager()
        self.cash = 0.0

        if selector is None:
            selector = MarketCapSelector(n=n)

        strategy_name = f"Top_{n}_{selector.__class__.__name__.replace('Selector', '')}"

        # Initial Allocation at start_year
        u_start = self.data_loader.load_universe(start_year)
        initial_targets = selector.select(u_start, n=n)

        for target in initial_targets:
            price = self.data_loader.get_price(target.ticker, start_year)
            target_dollar = initial_capital * target.target_weight
            target_shares = target_dollar / price
            self.tax_manager.add_lot(target.ticker, target_shares, price, start_year)
            self.trade_history.append(
                TradeOrder(
                    ticker=target.ticker,
                    action="BUY",
                    shares=target_shares,
                    price=price,
                    year=start_year,
                    realized_gain=0.0,
                )
            )

        start_value = initial_capital
        annual_history: List[AnnualLedgerEntry] = []

        # Annual Rebalancing Loop for subsequent years
        for current_year in range(start_year + 1, end_year + 1):
            # Step 1: Pre-Tax Valuation
            positions = self.tax_manager.get_all_positions()
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

            # Step 2: Provisional Target Weights
            u_curr = self.data_loader.load_universe(current_year)
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

            # Step 3: Phase 1 (Sells: Full Exits & Overweight Trims)
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

            # Step 4: Phase 2 (Tax Settlement, Secondary Trims & Buys)
            if is_after_tax:
                total_tax_paid = 0.0
                last_loss_cf = 0.0
                last_net_taxable = 0.0
                # Rebalance secondary trims and tax settlements until convergence
                for _ in range(20):
                    tax_paid_step, net_taxable, loss_cf = (
                        self.tax_manager.settle_annual_taxes(tax_rate, current_year)
                    )
                    total_tax_paid += tax_paid_step
                    self.cash -= tax_paid_step
                    last_loss_cf = loss_cf
                    last_net_taxable += net_taxable

                    if tax_paid_step <= 1e-7:
                        break

                    net_investable_equity = total_pretax_value - total_tax_paid
                    final_target_shares = {
                        ticker: (net_investable_equity * weight) / prices_curr[ticker]
                        for ticker, weight in target_weights.items()
                    }

                    trimmed_any = False
                    for ticker in final_target_shares:
                        curr_sh = self.tax_manager.get_position_shares(ticker)
                        if curr_sh > final_target_shares[ticker] + 1e-7:
                            sec_delta = curr_sh - final_target_shares[ticker]
                            p = prices_curr[ticker]
                            gain, _ = self.tax_manager.sell_shares(
                                ticker, sec_delta, p, current_year
                            )
                            proceeds = sec_delta * p
                            gross_sell_proceeds += proceeds
                            self.cash += proceeds
                            annual_realized_gain += gain
                            self.trade_history.append(
                                TradeOrder(
                                    ticker=ticker,
                                    action="SELL",
                                    shares=sec_delta,
                                    price=p,
                                    year=current_year,
                                    realized_gain=gain,
                                )
                            )
                            trimmed_any = True

                    if not trimmed_any:
                        break

                tax_paid = total_tax_paid
                net_taxable_gain = last_net_taxable
                loss_carryforward = last_loss_cf
                net_investable_equity = total_pretax_value - tax_paid
            else:
                self.tax_manager.settle_annual_taxes(0.0, current_year)
                tax_paid = 0.0
                net_taxable_gain = annual_realized_gain
                loss_carryforward = 0.0
                net_investable_equity = total_pretax_value

            turnover = (
                gross_sell_proceeds / total_pretax_value
                if total_pretax_value > 0.0
                else 0.0
            )

            final_target_shares = {
                ticker: (net_investable_equity * weight) / prices_curr[ticker]
                for ticker, weight in target_weights.items()
            }

            # Buys: for each stock in Top N where current shares < final target shares
            for ticker, final_sh in final_target_shares.items():
                curr_sh = self.tax_manager.get_position_shares(ticker)
                if curr_sh < final_sh - 1e-7:
                    shares_to_buy = final_sh - curr_sh
                    price = prices_curr[ticker]
                    cost = shares_to_buy * price
                    # Clamp Phase 2 buys to available cash so self.cash can NEVER become negative
                    cost = min(cost, max(0.0, self.cash))
                    shares_to_buy = cost / price
                    self.cash -= cost
                    self.tax_manager.add_lot(
                        ticker, shares_to_buy, price, current_year
                    )
                    self.trade_history.append(
                        TradeOrder(
                            ticker=ticker,
                            action="BUY",
                            shares=shares_to_buy,
                            price=price,
                            year=current_year,
                            realized_gain=0.0,
                        )
                    )

            # Snap floating-point dust in cash to 0.0 and guard against negative cash
            if abs(self.cash) < 1e-5:
                self.cash = 0.0
            self.cash = max(0.0, self.cash)

            self.cash_history.append(self.cash)
            ending_value_aftertax = net_investable_equity

            # Benchmark S&P 500 return
            spx_curr = self.data_loader.get_spx_level(current_year)
            spx_prev = self.data_loader.get_spx_level(current_year - 1)
            spx_return = (spx_curr - spx_prev) / spx_prev

            # Step 5: Annual Ledger Entry
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
        )
