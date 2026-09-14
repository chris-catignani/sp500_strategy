"""Unit tests for quantitative performance and tax drag calculators."""

import unittest
from engine.models import AnnualLedgerEntry
from engine.metrics import (
    calculate_cagr,
    calculate_cumulative_return,
    calculate_max_drawdown,
    calculate_turnover,
    calculate_tax_drag,
    calculate_terminal_metrics,
    calculate_alpha,
    calculate_benchmark_annual_series,
)
import engine


class TestMetrics(unittest.TestCase):
    """Test suite for engine/metrics.py quantitative calculators."""

    def test_engine_reexports(self):
        self.assertIs(engine.calculate_cagr, calculate_cagr)
        self.assertIs(engine.calculate_cumulative_return, calculate_cumulative_return)
        self.assertIs(engine.calculate_max_drawdown, calculate_max_drawdown)
        self.assertIs(engine.calculate_turnover, calculate_turnover)
        self.assertIs(engine.calculate_tax_drag, calculate_tax_drag)
        self.assertIs(engine.calculate_terminal_metrics, calculate_terminal_metrics)
        self.assertIs(engine.calculate_alpha, calculate_alpha)
        self.assertIs(engine.calculate_benchmark_annual_series, calculate_benchmark_annual_series)


    # 1. CAGR Tests
    def test_cagr_10_years(self):
        # 10000 -> 20000 over 10 years: (2)**(0.1) - 1 ~ 7.177346%
        cagr = calculate_cagr(10000.0, 20000.0, 10)
        expected = (20000.0 / 10000.0) ** (1.0 / 10) - 1.0
        self.assertAlmostEqual(cagr, expected, places=7)
        self.assertAlmostEqual(cagr, 0.07177346, places=6)

    def test_cagr_20_years(self):
        # 10000 -> 40000 over 20 years: (4)**(0.05) - 1 ~ 7.177346%
        cagr = calculate_cagr(10000.0, 40000.0, 20)
        expected = (40000.0 / 10000.0) ** (1.0 / 20) - 1.0
        self.assertAlmostEqual(cagr, expected, places=7)
        self.assertAlmostEqual(cagr, 0.07177346, places=6)

    def test_cagr_30_years(self):
        # 10000 -> 80000 over 30 years: (8)**(1/30) - 1 ~ 7.177346%
        cagr = calculate_cagr(10000.0, 80000.0, 30)
        expected = (80000.0 / 10000.0) ** (1.0 / 30) - 1.0
        self.assertAlmostEqual(cagr, expected, places=7)
        self.assertAlmostEqual(cagr, 0.07177346, places=6)

    def test_cagr_flat_return(self):
        cagr = calculate_cagr(10000.0, 10000.0, 5)
        self.assertAlmostEqual(cagr, 0.0)

    def test_cagr_loss(self):
        cagr = calculate_cagr(10000.0, 5000.0, 1)
        self.assertAlmostEqual(cagr, -0.5)

    def test_cagr_total_loss(self):
        cagr = calculate_cagr(10000.0, 0.0, 5)
        self.assertEqual(cagr, -1.0)

    def test_cagr_negative_end_value(self):
        cagr = calculate_cagr(10000.0, -100.0, 5)
        self.assertEqual(cagr, -1.0)

    def test_cagr_zero_or_negative_years(self):
        self.assertEqual(calculate_cagr(10000.0, 20000.0, 0), 0.0)
        self.assertEqual(calculate_cagr(10000.0, 20000.0, -5), 0.0)

    def test_cagr_zero_or_negative_start_value(self):
        self.assertEqual(calculate_cagr(0.0, 20000.0, 10), 0.0)
        self.assertEqual(calculate_cagr(-500.0, 20000.0, 10), 0.0)

    # 2. Cumulative Return Tests
    def test_cumulative_return_positive(self):
        ret = calculate_cumulative_return(100.0, 250.0)
        self.assertAlmostEqual(ret, 1.50)

    def test_cumulative_return_negative(self):
        ret = calculate_cumulative_return(100.0, 60.0)
        self.assertAlmostEqual(ret, -0.40)

    def test_cumulative_return_zero(self):
        ret = calculate_cumulative_return(100.0, 100.0)
        self.assertAlmostEqual(ret, 0.0)

    def test_cumulative_return_zero_or_negative_start(self):
        self.assertEqual(calculate_cumulative_return(0.0, 100.0), 0.0)
        self.assertEqual(calculate_cumulative_return(-50.0, 50.0), 0.0)

    # 3. Max Drawdown Tests
    def test_max_drawdown_empty_series(self):
        self.assertEqual(calculate_max_drawdown([]), 0.0)

    def test_max_drawdown_single_value(self):
        self.assertEqual(calculate_max_drawdown([100.0]), 0.0)

    def test_max_drawdown_monotonic_gain(self):
        series = [100.0, 110.0, 125.0, 140.0, 160.0]
        self.assertEqual(calculate_max_drawdown(series), 0.0)

    def test_max_drawdown_monotonic_drop(self):
        # 100 -> 80 (-20%) -> 50 (-50%)
        series = [100.0, 80.0, 50.0]
        self.assertAlmostEqual(calculate_max_drawdown(series), -0.50)

    def test_max_drawdown_volatile_series(self):
        # 100 -> 80 (-20%) -> 120 -> 90 (-25% from 120 peak) -> 150
        series = [100.0, 80.0, 120.0, 90.0, 150.0]
        self.assertAlmostEqual(calculate_max_drawdown(series), -0.25)

    def test_max_drawdown_flat_series(self):
        series = [100.0, 100.0, 100.0]
        self.assertEqual(calculate_max_drawdown(series), 0.0)

    def test_max_drawdown_zero_or_negative_peak(self):
        series = [0.0, -10.0, -20.0]
        self.assertEqual(calculate_max_drawdown(series), 0.0)

    # 4. Turnover Tests
    def test_turnover_empty_ledger(self):
        self.assertEqual(calculate_turnover([]), 0.0)

    def test_turnover_single_entry(self):
        entry = AnnualLedgerEntry(
            year=2020,
            start_value=10000.0,
            gross_return=0.10,
            ending_value_pretax=11000.0,
            realized_capital_gain=1000.0,
            net_taxable_gain=1000.0,
            tax_paid=300.0,
            loss_carryforward=0.0,
            ending_value_aftertax=10700.0,
            spx_return=0.15,
            turnover=0.35,
        )
        self.assertAlmostEqual(calculate_turnover([entry]), 0.35)

    def test_turnover_multiple_entries(self):
        entries = [
            AnnualLedgerEntry(
                year=2020,
                start_value=10000.0,
                gross_return=0.10,
                ending_value_pretax=11000.0,
                realized_capital_gain=0.0,
                net_taxable_gain=0.0,
                tax_paid=0.0,
                loss_carryforward=0.0,
                ending_value_aftertax=11000.0,
                spx_return=0.10,
                turnover=t,
            )
            for t in [0.10, 0.20, 0.30]
        ]
        self.assertAlmostEqual(calculate_turnover(entries), 0.20)

    # 5. Tax Drag Tests
    def test_tax_drag_standard(self):
        drag = calculate_tax_drag(0.15, 0.12)
        self.assertAlmostEqual(drag, 0.03)

    def test_tax_drag_zero(self):
        drag = calculate_tax_drag(0.10, 0.10)
        self.assertAlmostEqual(drag, 0.0)

    def test_tax_drag_negative(self):
        drag = calculate_tax_drag(0.10, 0.12)
        self.assertAlmostEqual(drag, -0.02)

    # 6. Terminal Liquidation Metrics Tests
    def test_terminal_metrics_after_tax(self):
        # 10 years, $100k -> $350k pre-liquidation, $100k unrealized gain, $20k loss carryforward, 30% tax
        res = calculate_terminal_metrics(
            pre_liquidation_wealth=350000.0,
            unrealized_gain=100000.0,
            loss_carryforward=20000.0,
            tax_rate=0.30,
            initial_capital=100000.0,
            years=10,
            is_after_tax=True,
        )
        self.assertEqual(res["pre_liquidation_wealth"], 350000.0)
        self.assertEqual(res["embedded_unrealized_gain"], 100000.0)
        self.assertEqual(res["net_taxable_terminal_gain"], 80000.0)
        self.assertEqual(res["terminal_tax"], 24000.0)
        self.assertEqual(res["post_liquidation_wealth"], 326000.0)

        pre_cagr = calculate_cagr(100000.0, 350000.0, 10)
        post_cagr = calculate_cagr(100000.0, 326000.0, 10)
        self.assertAlmostEqual(res["post_liquidation_cagr"], post_cagr)
        self.assertAlmostEqual(res["terminal_tax_drag"], pre_cagr - post_cagr)

    def test_terminal_metrics_pre_tax_mode(self):
        res = calculate_terminal_metrics(
            pre_liquidation_wealth=350000.0,
            unrealized_gain=100000.0,
            loss_carryforward=20000.0,
            tax_rate=0.30,
            initial_capital=100000.0,
            years=10,
            is_after_tax=False,
        )
        self.assertEqual(res["pre_liquidation_wealth"], 350000.0)
        self.assertEqual(res["embedded_unrealized_gain"], 100000.0)
        self.assertEqual(res["net_taxable_terminal_gain"], 0.0)
        self.assertEqual(res["terminal_tax"], 0.0)
        self.assertEqual(res["post_liquidation_wealth"], 350000.0)

        pre_cagr = calculate_cagr(100000.0, 350000.0, 10)
        self.assertAlmostEqual(res["post_liquidation_cagr"], pre_cagr)
        self.assertAlmostEqual(res["terminal_tax_drag"], 0.0)

    def test_terminal_metrics_loss_carryforward_exceeds_gain(self):
        res = calculate_terminal_metrics(
            pre_liquidation_wealth=200000.0,
            unrealized_gain=30000.0,
            loss_carryforward=50000.0,
            tax_rate=0.30,
            initial_capital=100000.0,
            years=10,
            is_after_tax=True,
        )
        self.assertEqual(res["net_taxable_terminal_gain"], 0.0)
        self.assertEqual(res["terminal_tax"], 0.0)
        self.assertEqual(res["post_liquidation_wealth"], 200000.0)
        self.assertAlmostEqual(res["terminal_tax_drag"], 0.0)

    def test_terminal_metrics_unrealized_loss(self):
        res = calculate_terminal_metrics(
            pre_liquidation_wealth=80000.0,
            unrealized_gain=-20000.0,
            loss_carryforward=5000.0,
            tax_rate=0.30,
            initial_capital=100000.0,
            years=5,
            is_after_tax=True,
        )
        self.assertEqual(res["net_taxable_terminal_gain"], 0.0)
        self.assertEqual(res["terminal_tax"], 0.0)
        self.assertEqual(res["post_liquidation_wealth"], 80000.0)
        self.assertAlmostEqual(res["terminal_tax_drag"], 0.0)

    def test_terminal_metrics_zero_years(self):
        res = calculate_terminal_metrics(
            pre_liquidation_wealth=100000.0,
            unrealized_gain=10000.0,
            loss_carryforward=0.0,
            tax_rate=0.30,
            initial_capital=100000.0,
            years=0,
            is_after_tax=True,
        )
        self.assertEqual(res["post_liquidation_cagr"], 0.0)
        self.assertEqual(res["terminal_tax_drag"], 0.0)

    # 7. Alpha Test
    def test_alpha(self):
        self.assertAlmostEqual(calculate_alpha(0.15, 0.10), 0.05)
        self.assertAlmostEqual(calculate_alpha(0.08, 0.10), -0.02)

    # 8. Benchmark Annual Series Tests
    def test_calculate_benchmark_annual_series_pretax(self):
        pr_levels = [100.0, 110.0]   # 10% price return
        tr_levels = [100.0, 112.0]   # 12% total return (2% dividend yield)
        res = calculate_benchmark_annual_series(
            pr_levels=pr_levels,
            tr_levels=tr_levels,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_after_tax=False,
        )
        self.assertAlmostEqual(res["annual_returns"][0], 0.12, places=6)
        self.assertAlmostEqual(res["final_equity"], 11200.0, places=2)
        self.assertAlmostEqual(res["pre_liquidation_wealth"], 11200.0, places=2)
        self.assertAlmostEqual(res["total_taxes_paid"], 0.0, places=2)
        self.assertAlmostEqual(res["post_liquidation_wealth"], 11200.0, places=2)

    def test_calculate_benchmark_annual_series_aftertax(self):
        pr_levels = [100.0, 110.0]   # 10% price return
        tr_levels = [100.0, 112.0]   # 12% total return (2% dividend yield)
        res = calculate_benchmark_annual_series(
            pr_levels=pr_levels,
            tr_levels=tr_levels,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_after_tax=True,
        )
        self.assertAlmostEqual(res["annual_returns"][0], 0.114, places=6)
        self.assertAlmostEqual(res["pre_liquidation_wealth"], 11140.0, places=2)
        self.assertAlmostEqual(res["final_equity"], 11140.0, places=2)
        self.assertAlmostEqual(res["post_liquidation_wealth"], 10840.0, places=2)
        self.assertAlmostEqual(res["total_taxes_paid"], 60.0, places=2)
        self.assertAlmostEqual(res["terminal_liq_tax"], 300.0, places=2)
        self.assertAlmostEqual(res["total_dividends_received"], 200.0, places=2)

    def test_calculate_benchmark_annual_series_multi_year(self):
        # 2 years:
        # Year 1: PR 100 -> 110 (10%), TR 100 -> 112 (12%), yield = 2%
        # Year 2: PR 110 -> 121 (10%), TR 112 -> 126.56, r_tr = (126.56 - 112) / 112 = 0.13, yield = 3%
        pr_levels = [100.0, 110.0, 121.0]
        tr_levels = [100.0, 112.0, 126.56]
        res = calculate_benchmark_annual_series(
            pr_levels=pr_levels,
            tr_levels=tr_levels,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_after_tax=True,
        )
        self.assertEqual(len(res["annual_returns"]), 2)
        # Year 1 return: 0.10 + 0.02 * 0.7 = 0.114
        self.assertAlmostEqual(res["annual_returns"][0], 0.114, places=6)
        # Year 2 return: 0.10 + 0.03 * 0.7 = 0.121
        self.assertAlmostEqual(res["annual_returns"][1], 0.121, places=6)
        v1 = 10000.0 * 1.114  # 11140.0
        v2 = v1 * 1.121       # 12487.94
        self.assertAlmostEqual(res["pre_liquidation_wealth"], v2, places=2)
        # Div 1: 10000 * 0.02 = 200. Div 2: 11140 * 0.03 = 334.20. Total div = 534.20
        self.assertAlmostEqual(res["total_dividends_received"], 534.20, places=2)

    def test_calculate_benchmark_annual_series_edge_cases(self):
        # Mismatched lengths
        with self.assertRaises(ValueError):
            calculate_benchmark_annual_series([100.0], [100.0, 110.0])

        # Empty or single level (< 2)
        res_empty = calculate_benchmark_annual_series([], [], initial_capital=5000.0)
        self.assertEqual(res_empty["annual_returns"], [])
        self.assertEqual(res_empty["final_equity"], 5000.0)
        self.assertEqual(res_empty["total_taxes_paid"], 0.0)
        self.assertEqual(res_empty["total_dividends_received"], 0.0)
        self.assertEqual(res_empty["cost_basis"], 5000.0)

        # Zero tax rate matches pretax
        pr_levels = [100.0, 110.0]
        tr_levels = [100.0, 112.0]
        res_zero_tax = calculate_benchmark_annual_series(
            pr_levels, tr_levels, tax_rate=0.0, initial_capital=10000.0, is_after_tax=True
        )
        res_pretax = calculate_benchmark_annual_series(
            pr_levels, tr_levels, tax_rate=0.30, initial_capital=10000.0, is_after_tax=False
        )
        self.assertEqual(res_zero_tax["annual_returns"], res_pretax["annual_returns"])
        self.assertEqual(res_zero_tax["final_equity"], res_pretax["final_equity"])
        self.assertEqual(res_zero_tax["total_taxes_paid"], 0.0)


if __name__ == "__main__":
    unittest.main()
