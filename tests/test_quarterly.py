"""Unit tests for Quarterly Rebalancing, Dynamic Weight Drift, and Tax Lot Accounting.

Zero external dependencies - Python 3 standard library only.
"""

import unittest
from engine.backtest import PortfolioSimulator
from engine.data_loader import DataLoader
from engine.models import StrategyResult, TaxLot, TradeOrder
from engine.selector import MarketCapSelector, PerformanceSelector
from engine.tax_lots import FIFOTaxLotManager


class TestQuarterlyDataLoading(unittest.TestCase):
    """Test data loader retrieval of quarterly prices, dividends, and universes."""

    def setUp(self) -> None:
        self.loader = DataLoader()

    def test_get_quarterly_price_valid(self) -> None:
        """Verify split-adjusted quarterly price retrieval."""
        price_q1 = self.loader.get_quarterly_price("AAPL", 2024, 1)
        price_q4 = self.loader.get_quarterly_price("AAPL", 2024, 4)
        self.assertGreater(price_q1, 0.0)
        self.assertGreater(price_q4, 0.0)
        # Verify Q4 price matches year-end annual price
        annual_price = self.loader.get_price("AAPL", 2024)
        self.assertAlmostEqual(price_q4, annual_price, places=2)

    def test_get_quarterly_price_missing_raises(self) -> None:
        """Verify KeyError raised for unknown ticker or missing quarter."""
        with self.assertRaises(KeyError):
            self.loader.get_quarterly_price("NONEXISTENT_TICKER", 2024, 1)

    def test_get_quarterly_dividend(self) -> None:
        """Verify quarterly dividend collection."""
        div = self.loader.get_quarterly_dividend("AAPL", 2024, 1)
        self.assertGreaterEqual(div, 0.0)
        # Sum of 4 quarters should approximate annual dividend
        q_sum = sum(self.loader.get_quarterly_dividend("AAPL", 2024, q) for q in (1, 2, 3, 4))
        ann_div = self.loader.get_dividend("AAPL", 2024)
        self.assertAlmostEqual(q_sum, ann_div, delta=0.05)

    def test_load_quarterly_universe_and_anchoring(self) -> None:
        """Verify quarterly constituent snapshots exist for all 4 quarters."""
        for q in (1, 2, 3, 4):
            univ_q = self.loader.load_quarterly_universe(2024, q, universe="sp500")
            self.assertGreater(len(univ_q), 0)
            tickers = [s.ticker for s in univ_q]
            self.assertIn("AAPL", tickers)
            self.assertIn("MSFT", tickers)
            self.assertIn("NVDA", tickers)
            for s in univ_q:
                self.assertEqual(s.quarter, q)
                self.assertGreater(s.market_cap_weight, 0.0)

    def test_tesla_inclusion_date_enforced(self) -> None:
        """Verify TSLA is not in quarterly candidates prior to its Dec 21, 2020 addition."""
        for universe in ("sp500", "world"):
            for q in (1, 2, 3):
                univ = self.loader.load_quarterly_universe(2020, q, universe=universe)
                tickers = [s.ticker for s in univ]
                self.assertNotIn("TSLA", tickers, f"TSLA found prematurely in {universe} 2020-Q{q}")
            # TSLA should be present at 2020-Q4 factsheet re-anchoring
            univ_q4 = self.loader.load_quarterly_universe(2020, 4, universe=universe)
            self.assertIn("TSLA", [s.ticker for s in univ_q4])

    def test_quarterly_candidate_zero_lookahead_invariant(self) -> None:
        """Verify Q1-Q3 candidate rosters across all years derive strictly from prior-year membership."""
        for universe in ("sp500", "world"):
            for year in range(1995, 2025):
                prior_univ = self.loader.load_universe(year - 1, universe=universe)
                prior_tickers = {s.ticker for s in prior_univ}
                for q in (1, 2, 3):
                    q_univ = self.loader.load_quarterly_universe(year, q, universe=universe)
                    for s in q_univ:
                        self.assertIn(
                            s.ticker,
                            prior_tickers,
                            f"Lookahead leak: {s.ticker} in {universe} {year}-Q{q} was not in {year-1} factsheet",
                        )

    def test_msci_world_quarterly_levels_observed(self) -> None:
        """Verify MSCI World quarterly levels reflect observed market movements rather than linear interpolation."""
        # In Q1 2020 (COVID shock), MSCI World Price Return and Total Return dropped significantly
        pr_2019_q4 = self.loader.get_msci_world_quarterly_level(2019, 4)
        pr_2020_q1 = self.loader.get_msci_world_quarterly_level(2020, 1)
        tr_2019_q4 = self.loader.get_msci_world_tr_quarterly_level(2019, 4)
        tr_2020_q1 = self.loader.get_msci_world_tr_quarterly_level(2020, 1)

        self.assertLess(pr_2020_q1, pr_2019_q4, "Q1 2020 PR did not reflect market crash")
        self.assertLess(tr_2020_q1, tr_2019_q4, "Q1 2020 TR did not reflect market crash")



class TestQuarterlyTaxLotsAndTrades(unittest.TestCase):
    """Test tax lot manager with quarter metadata."""

    def setUp(self) -> None:
        self.tax_mgr = FIFOTaxLotManager()

    def test_add_and_sell_with_quarter(self) -> None:
        """Verify FIFO lot depletion preserves quarter metadata."""
        lot = self.tax_mgr.add_lot("AAPL", shares=10.0, price=150.0, year=2024, quarter=1)
        self.assertEqual(lot.quarter, 1)
        self.assertEqual(lot.purchase_year, 2024)

        gain, depleted = self.tax_mgr.sell_shares("AAPL", shares_to_sell=5.0, current_price=170.0, current_year=2024, current_quarter=2)
        self.assertAlmostEqual(gain, 100.0)  # 5 * (170 - 150)
        self.assertEqual(len(depleted), 1)
        self.assertEqual(depleted[0].purchase_quarter, 1)
        self.assertEqual(self.tax_mgr.get_position_shares("AAPL"), 5.0)


class TestQuarterlyPortfolioSimulator(unittest.TestCase):
    """Test quarterly rebalancing execution and invariants."""

    def setUp(self) -> None:
        self.loader = DataLoader()
        self.simulator = PortfolioSimulator(self.loader)

    def test_unleveraged_cash_invariant(self) -> None:
        """Verify cash is strictly non-negative at every step of quarterly simulation."""
        result = self.simulator.run_simulation(
            start_year=2014,
            end_year=2024,
            n=5,
            selector=MarketCapSelector(5),
            is_after_tax=True,
            tax_rate=0.30,
            initial_capital=10000.0,
            universe="sp500",
            rebalance_frequency="quarterly",
        )
        self.assertGreater(result.final_equity, 10000.0)
        self.assertEqual(result.rebalance_frequency, "quarterly")

        # Invariant check across cash history
        for c in self.simulator.cash_history:
            self.assertGreaterEqual(c, 0.0)

        # Quarterly history checks: 10 years * 4 quarters = 40 entries
        self.assertEqual(len(result.quarterly_history), 40)
        for entry in result.quarterly_history:
            self.assertIn(entry.quarter, (1, 2, 3, 4))
            self.assertGreaterEqual(entry.cash, 0.0)
            self.assertGreaterEqual(entry.ending_value_aftertax, 0.0)

        # Annual history checks: exactly 10 calendar year-end entries
        self.assertEqual(len(result.annual_history), 10)
        for entry in result.annual_history:
            self.assertGreaterEqual(entry.cash, 0.0)
            self.assertGreaterEqual(entry.ending_value_aftertax, 0.0)

    def test_quarterly_performance_selector(self) -> None:
        """Verify performance selector functions properly with quarterly rebalancing."""
        result = self.simulator.run_simulation(
            start_year=2020,
            end_year=2024,
            n=3,
            selector=PerformanceSelector(3),
            is_after_tax=False,
            initial_capital=10000.0,
            universe="sp500",
            rebalance_frequency="quarterly",
        )
        self.assertEqual(result.rebalance_frequency, "quarterly")
        self.assertEqual(len(result.annual_history), 4)
        self.assertEqual(len(result.quarterly_history), 16)
        self.assertGreater(result.final_equity, 0.0)

    def test_quarterly_vs_annual_divergence(self) -> None:
        """Verify quarterly and annual strategies yield valid, distinct results."""
        sim_ann = PortfolioSimulator(self.loader)
        res_ann = sim_ann.run_simulation(
            start_year=2014,
            end_year=2024,
            n=5,
            selector=MarketCapSelector(5),
            is_after_tax=True,
            tax_rate=0.30,
            initial_capital=10000.0,
            universe="sp500",
            rebalance_frequency="annual",
        )

        sim_qtr = PortfolioSimulator(self.loader)
        res_qtr = sim_qtr.run_simulation(
            start_year=2014,
            end_year=2024,
            n=5,
            selector=MarketCapSelector(5),
            is_after_tax=True,
            tax_rate=0.30,
            initial_capital=10000.0,
            universe="sp500",
            rebalance_frequency="quarterly",
        )

        self.assertNotEqual(res_ann.final_equity, res_qtr.final_equity)
        self.assertGreater(res_ann.cagr, 0.10)
        self.assertGreater(res_qtr.cagr, 0.10)

    def test_quarterly_max_drawdown_intra_year(self) -> None:
        """Verify quarterly max drawdown evaluates intra-year quarterly peaks and troughs."""
        res_qtr = self.simulator.run_simulation(
            start_year=2004,
            end_year=2024,
            n=5,
            selector=MarketCapSelector(5),
            is_after_tax=False,
            initial_capital=10000.0,
            universe="sp500",
            rebalance_frequency="quarterly",
        )
        # Quarterly peak-to-trough during 2008 GFC reaches ~ -45.38%, strictly worse than annual -37.75%
        self.assertLess(res_qtr.max_drawdown, -0.40)
        self.assertAlmostEqual(res_qtr.max_drawdown, -0.4538, places=2)

    def test_quarterly_annual_synthesis_net_taxable_gain(self) -> None:
        """Verify synthesized annual net_taxable_gain correctly nets year's realized gains against entering carryforward."""
        res = self.simulator.run_simulation(
            start_year=2014,
            end_year=2024,
            n=5,
            selector=MarketCapSelector(5),
            is_after_tax=True,
            tax_rate=0.30,
            initial_capital=10000.0,
            universe="sp500",
            rebalance_frequency="quarterly",
        )
        prev_loss_cf = 0.0
        for entry in res.annual_history:
            expected_net_taxable = entry.realized_capital_gain - prev_loss_cf
            self.assertAlmostEqual(entry.net_taxable_gain, expected_net_taxable, places=2)
            prev_loss_cf = entry.loss_carryforward

    def test_quarterly_index_dividend_reinvestment(self) -> None:
        """Verify quarterly index dividend reinvestment produces exact compounding metrics."""
        from engine.metrics import calculate_benchmark_annual_series, calculate_cagr

        # S&P 500 10-Year (2014-2024)
        spx_q_pr = [self.loader.get_spx_quarterly_level(2014, 4)]
        spx_q_tr = [self.loader.get_spx_tr_quarterly_level(2014, 4)]
        for y in range(2015, 2025):
            for q in (1, 2, 3, 4):
                spx_q_pr.append(self.loader.get_spx_quarterly_level(y, q))
                spx_q_tr.append(self.loader.get_spx_tr_quarterly_level(y, q))

        self.assertEqual(len(spx_q_pr), 41)
        self.assertEqual(len(spx_q_tr), 41)

        spx_post = calculate_benchmark_annual_series(
            pr_levels=spx_q_pr,
            tr_levels=spx_q_tr,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_after_tax=True,
        )

        cagr = calculate_cagr(10000.0, spx_post["post_liquidation_wealth"], 10)
        self.assertAlmostEqual(cagr, 0.1017, places=3)
        self.assertAlmostEqual(spx_post["post_liquidation_wealth"], 26352.07, places=1)
        self.assertAlmostEqual(spx_post["total_taxes_paid"], 919.06, places=1)
        self.assertAlmostEqual(spx_post["total_dividends_received"], 3063.55, places=1)

        # MSCI World 10-Year (2014-2024)
        msci_q_pr = [self.loader.get_msci_world_quarterly_level(2014, 4)]
        msci_q_tr = [self.loader.get_msci_world_tr_quarterly_level(2014, 4)]
        for y in range(2015, 2025):
            for q in (1, 2, 3, 4):
                msci_q_pr.append(self.loader.get_msci_world_quarterly_level(y, q))
                msci_q_tr.append(self.loader.get_msci_world_tr_quarterly_level(y, q))

        self.assertEqual(len(msci_q_pr), 41)
        msci_post = calculate_benchmark_annual_series(
            pr_levels=msci_q_pr,
            tr_levels=msci_q_tr,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_after_tax=True,
        )
        m_cagr = calculate_cagr(10000.0, msci_post["post_liquidation_wealth"], 10)
        self.assertAlmostEqual(m_cagr, 0.0795, places=3)
        self.assertAlmostEqual(msci_post["post_liquidation_wealth"], 21497.28, places=1)

    def test_quarterly_spinoff_distribution_and_basis_adjustment(self) -> None:
        """Verify quarterly spinoff proceeds credit to cash and adjust basis in quarterly simulation."""
        self.loader.spinoffs["MSFT"] = [
            {
                "ex_date": "2015-03-15",
                "year": 2015,
                "quarter": 1,
                "distribution_per_share": 5.0,
                "basis_retention_ratio": 0.85,
                "spinco_ticker": "SPINQ",
                "description": "Quarterly Test Spinoff",
            }
        ]
        sim = PortfolioSimulator(data_loader=self.loader)
        res = sim.run_simulation(
            start_year=2014,
            end_year=2015,
            n=5,
            is_after_tax=True,
            tax_rate=0.30,
            initial_capital=100000.0,
            rebalance_frequency="quarterly",
        )
        q1_entry = res.quarterly_history[0]  # 2015 Q1
        ann_entry = res.annual_history[0]    # 2015 synthesized annual
        self.assertGreater(q1_entry.spinoff_proceeds, 0.0)
        self.assertGreater(ann_entry.spinoff_proceeds, 0.0)
        self.assertAlmostEqual(q1_entry.spinoff_proceeds, ann_entry.spinoff_proceeds, places=2)
        self.assertAlmostEqual(
            q1_entry.dividend_tax_paid,
            q1_entry.dividend_income * 0.30,
            places=2,
        )


if __name__ == "__main__":
    unittest.main()
