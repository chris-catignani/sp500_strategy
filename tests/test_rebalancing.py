"""Unit tests for Two-Phase Portfolio Simulation Engine (PortfolioSimulator)."""

import unittest
from engine.data_loader import DataLoader
from engine.models import StrategyResult, TradeOrder
from engine.selector import MarketCapSelector, PerformanceSelector
from engine.backtest import PortfolioSimulator


class TestPortfolioSimulator(unittest.TestCase):
    """Test suite for PortfolioSimulator and two-phase rebalancing mechanics."""

    def setUp(self):
        self.data_loader = DataLoader()
        self.simulator = PortfolioSimulator(data_loader=self.data_loader)

    def test_simulator_initialization(self):
        """Test default and custom initialization of PortfolioSimulator."""
        sim_default = PortfolioSimulator()
        self.assertIsNotNone(sim_default.data_loader)
        self.assertEqual(len(sim_default.trade_history), 0)
        self.assertEqual(sim_default.cash, 0.0)

        sim_custom = PortfolioSimulator(data_loader=self.data_loader)
        self.assertIs(sim_custom.data_loader, self.data_loader)

    def test_validation_errors(self):
        """Test invalid parameters raise appropriate ValueErrors."""
        with self.assertRaises(ValueError):
            self.simulator.run_simulation(start_year=2020, end_year=2020, n=5)

        with self.assertRaises(ValueError):
            self.simulator.run_simulation(start_year=2020, end_year=2015, n=5)

        with self.assertRaises(ValueError):
            self.simulator.run_simulation(start_year=2014, end_year=2024, n=0)

        with self.assertRaises(ValueError):
            self.simulator.run_simulation(start_year=2014, end_year=2024, n=5, initial_capital=-1000)

        with self.assertRaises(ValueError):
            self.simulator.run_simulation(start_year=2014, end_year=2024, n=5, tax_rate=-0.1)

        with self.assertRaises(ValueError):
            self.simulator.run_simulation(start_year=2014, end_year=2024, n=5, tax_rate=1.5)

    def test_target_weights_and_normalization(self):
        """Test Phase 1 & Phase 2 matching target weights (100% normalization)."""
        result = self.simulator.run_simulation(
            start_year=2014,
            end_year=2015,
            n=5,
            is_after_tax=False,
            initial_capital=10000.0,
        )

        self.assertEqual(len(result.annual_history), 1)
        entry_2015 = result.annual_history[0]
        self.assertEqual(entry_2015.year, 2015)

        # Universe at 2015 Top 5 targets
        u2015 = self.data_loader.load_universe(2015)
        selector = MarketCapSelector(n=5)
        expected_targets = selector.select(u2015)
        expected_weights = {t.ticker: t.target_weight for t in expected_targets}

        # Verify all expected tickers are in holdings
        self.assertEqual(set(entry_2015.holdings.keys()), set(expected_weights.keys()))

        # Verify holding weights match expected normalized target weights
        total_val = entry_2015.ending_value_pretax
        computed_weights = {}
        for ticker, shares in entry_2015.holdings.items():
            price = self.data_loader.get_price(ticker, 2015)
            val = shares * price
            computed_weights[ticker] = val / total_val
            self.assertAlmostEqual(computed_weights[ticker], expected_weights[ticker], places=5)

        # Weights sum to 100%
        self.assertAlmostEqual(sum(computed_weights.values()), 1.0, places=5)

    def test_cash_neutrality_pretax(self):
        """Test cash neutrality: total portfolio value equals sum of holding values (zero cash drag)."""
        result = self.simulator.run_simulation(
            start_year=2014,
            end_year=2024,
            n=5,
            is_after_tax=False,
            initial_capital=10000.0,
        )

        for entry in result.annual_history:
            sum_holdings = sum(
                shares * self.data_loader.get_price(ticker, entry.year)
                for ticker, shares in entry.holdings.items()
            )
            # In pre-tax, cash is 0 and sum of holdings equals pretax ending value
            self.assertAlmostEqual(entry.ending_value_pretax, sum_holdings, places=4)
            self.assertAlmostEqual(entry.ending_value_aftertax, entry.ending_value_pretax, places=4)

        self.assertAlmostEqual(self.simulator.cash, 0.0, places=4)

    def test_cash_neutrality_aftertax(self):
        """Test cash neutrality in after-tax: ending_value_aftertax equals sum of holding values + cash."""
        result = self.simulator.run_simulation(
            start_year=2014,
            end_year=2024,
            n=5,
            is_after_tax=True,
            tax_rate=0.30,
            initial_capital=10000.0,
        )

        for entry, cash in zip(result.annual_history, self.simulator.cash_history):
            sum_holdings = sum(
                shares * self.data_loader.get_price(ticker, entry.year)
                for ticker, shares in entry.holdings.items()
            )
            # Total equity matches sum of holding values + cash balance for that year
            self.assertAlmostEqual(
                entry.ending_value_aftertax,
                sum_holdings + cash,
                places=4,
            )

    def test_pretax_vs_aftertax(self):
        """Test Pre-Tax vs After-Tax: after-tax wealth <= pre-tax wealth when capital gains occur."""
        res_pretax = self.simulator.run_simulation(
            start_year=2014,
            end_year=2024,
            n=5,
            is_after_tax=False,
            initial_capital=10000.0,
        )

        res_aftertax = self.simulator.run_simulation(
            start_year=2014,
            end_year=2024,
            n=5,
            is_after_tax=True,
            tax_rate=0.30,
            initial_capital=10000.0,
        )

        # Positive taxes were incurred
        self.assertGreater(res_aftertax.total_taxes_paid, 0.0)

        # After-tax final equity and CAGR are strictly lower than pre-tax
        self.assertLess(res_aftertax.final_equity, res_pretax.final_equity)
        self.assertLess(res_aftertax.cagr, res_pretax.cagr)
        self.assertLess(res_aftertax.post_liquidation_wealth, res_pretax.post_liquidation_wealth)

        # Year-by-year comparison
        for e_pre, e_post in zip(res_pretax.annual_history, res_aftertax.annual_history):
            self.assertEqual(e_pre.year, e_post.year)
            # After tax value <= pre-tax value
            self.assertLessEqual(e_post.ending_value_aftertax, e_pre.ending_value_pretax + 1e-4)
            if e_post.tax_paid > 0:
                self.assertLess(e_post.ending_value_aftertax, e_post.ending_value_pretax)

    def test_full_exit_of_dropping_constituents(self):
        """Test exit of constituents liquidated 100% when dropping out of Top N."""
        # In 2014 Top 5: AAPL, XOM, MSFT, BRK.B, JNJ
        # In 2015 Top 5: AAPL, MSFT, XOM, AMZN, META
        # BRK.B and JNJ drop out in 2015
        result = self.simulator.run_simulation(
            start_year=2014,
            end_year=2015,
            n=5,
            is_after_tax=False,
        )

        entry_2015 = result.annual_history[0]
        # BRK.B and JNJ should not be in 2015 holdings
        self.assertNotIn("BRK.B", entry_2015.holdings)
        self.assertNotIn("JNJ", entry_2015.holdings)
        self.assertEqual(self.simulator.tax_manager.get_position_shares("BRK.B"), 0.0)
        self.assertEqual(self.simulator.tax_manager.get_position_shares("JNJ"), 0.0)

        # Check SELL orders for BRK.B and JNJ in trade history
        sell_orders = [o for o in self.simulator.trade_history if o.year == 2015 and o.action == "SELL"]
        sold_tickers = {o.ticker for o in sell_orders}
        self.assertIn("BRK.B", sold_tickers)
        self.assertIn("JNJ", sold_tickers)

        # Check that BRK.B sold shares equal 2014 purchase shares
        init_brk_order = [o for o in self.simulator.trade_history if o.year == 2014 and o.ticker == "BRK.B"][0]
        sell_brk_order = [o for o in sell_orders if o.ticker == "BRK.B"][0]
        self.assertAlmostEqual(init_brk_order.shares, sell_brk_order.shares, places=5)

    def test_overweight_trimming(self):
        """Test overweight trimming down to provisional target."""
        result = self.simulator.run_simulation(
            start_year=2014,
            end_year=2015,
            n=5,
            is_after_tax=False,
        )

        # MSFT and XOM were held from 2014 and trimmed in 2015
        sell_orders = [o for o in self.simulator.trade_history if o.year == 2015 and o.action == "SELL"]
        sell_dict = {o.ticker: o for o in sell_orders}

        # Verify XOM and MSFT were trimmed
        self.assertIn("XOM", sell_dict)
        self.assertIn("MSFT", sell_dict)
        self.assertGreater(sell_dict["XOM"].shares, 0.0)
        self.assertGreater(sell_dict["MSFT"].shares, 0.0)

        # Verify realized gains were recorded
        self.assertNotEqual(sell_dict["MSFT"].realized_gain, 0.0)

    def test_multi_year_backtest_run_n3_n5_n10(self):
        """Test multi-year backtest run across N in (3, 5, 10) for 2014-2024."""
        for n in [3, 5, 10]:
            for is_after_tax in [False, True]:
                res = self.simulator.run_simulation(
                    start_year=2014,
                    end_year=2024,
                    n=n,
                    is_after_tax=is_after_tax,
                    tax_rate=0.30,
                    initial_capital=10000.0,
                )

                self.assertIsInstance(res, StrategyResult)
                self.assertEqual(res.strategy_name, f"Top_{n}_MarketCap")
                self.assertEqual(res.n, n)
                self.assertEqual(res.start_year, 2014)
                self.assertEqual(res.end_year, 2024)
                self.assertEqual(len(res.annual_history), 10)
                self.assertEqual(res.initial_capital, 10000.0)
                self.assertGreater(res.final_equity, 0.0)
                self.assertGreater(res.cagr, 0.0)
                self.assertGreater(res.cumulative_return, 0.0)
                self.assertLessEqual(res.max_drawdown, 0.0)
                self.assertGreater(res.pre_liquidation_wealth, 0.0)
                self.assertGreater(res.post_liquidation_wealth, 0.0)

                if is_after_tax:
                    self.assertLessEqual(res.post_liquidation_wealth, res.pre_liquidation_wealth)
                    self.assertLessEqual(res.post_liquidation_cagr, res.cagr)
                else:
                    self.assertAlmostEqual(res.post_liquidation_wealth, res.pre_liquidation_wealth, places=5)
                    self.assertAlmostEqual(res.post_liquidation_cagr, res.cagr, places=5)

    def test_selector_override(self):
        """Test passing a custom PerformanceSelector."""
        selector = PerformanceSelector(n=5)
        res = self.simulator.run_simulation(
            start_year=2014,
            end_year=2024,
            n=5,
            selector=selector,
            is_after_tax=False,
        )
        self.assertEqual(res.strategy_name, "Top_5_Performance")
        self.assertEqual(len(res.annual_history), 10)

    def test_trade_history_access(self):
        """Test trade history recording and get_trades accessor."""
        self.simulator.run_simulation(
            start_year=2014,
            end_year=2015,
            n=3,
        )
        trades = self.simulator.get_trades()
        self.assertEqual(trades, self.simulator.trade_history)
        self.assertGreater(len(trades), 0)

        # Check initial buys at 2014
        buys_2014 = [t for t in trades if t.year == 2014 and t.action == "BUY"]
        self.assertEqual(len(buys_2014), 3)


if __name__ == "__main__":
    unittest.main()
