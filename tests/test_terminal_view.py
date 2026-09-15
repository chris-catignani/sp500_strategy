"""Unit tests for terminal view and row builders in engine/terminal_view.py."""

import unittest
from engine.benchmarks import BenchmarkMetrics
from engine.models import StrategyResult
from engine.terminal_view import (
    build_benchmark_row,
    build_strategy_row,
    format_terminal_table,
)


def _make_strategy_result(
    strategy_name: str = "Top 5",
    n: int = 5,
    start_year: int = 2014,
    end_year: int = 2024,
    is_after_tax: bool = False,
    tax_rate: float = 0.0,
    initial_capital: float = 10000.0,
    final_equity: float = 30000.0,
    cagr: float = 0.15,
    cumulative_return: float = 2.0,
    max_drawdown: float = -0.15,
    total_taxes_paid: float = 0.0,
    pre_liquidation_wealth: float = 30000.0,
    post_liquidation_wealth: float = 30000.0,
    post_liquidation_cagr: float = 0.15,
    universe: str = "sp500",
) -> StrategyResult:
    """Helper to construct a valid StrategyResult with all required attributes."""
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
        max_drawdown=max_drawdown,
        total_taxes_paid=total_taxes_paid,
        pre_liquidation_wealth=pre_liquidation_wealth,
        post_liquidation_wealth=post_liquidation_wealth,
        post_liquidation_cagr=post_liquidation_cagr,
        universe=universe,
    )


class TestTerminalViewRowBuilders(unittest.TestCase):
    """Test suite for build_strategy_row and build_benchmark_row helpers."""

    def test_build_strategy_row_basic(self):
        """Test build_strategy_row with standard inputs and default labels."""
        res_pre = _make_strategy_result(
            strategy_name="top_5",
            cagr=0.15,
            is_after_tax=False,
        )
        res_post = _make_strategy_result(
            strategy_name="top_5",
            cagr=0.12,
            post_liquidation_cagr=0.11,
            cumulative_return=2.0,
            max_drawdown=-0.15,
            is_after_tax=True,
        )
        row = build_strategy_row(
            res_pre=res_pre,
            res_post=res_post,
            horizon_label="10y",
            spx_after_cagr=0.10,
        )

        self.assertEqual(row["horizon"], "10y")
        self.assertEqual(row["strategy"], "top_5")
        self.assertNotIn("universe", row)
        self.assertAlmostEqual(row["pre_cagr"], 0.15)
        self.assertAlmostEqual(row["post_cagr"], 0.12)
        self.assertAlmostEqual(row["post_liq_cagr"], 0.11)
        self.assertAlmostEqual(row["cum_return"], 2.0)
        self.assertAlmostEqual(row["max_dd"], -0.15)
        self.assertAlmostEqual(row["tax_drag"], 0.03)
        self.assertAlmostEqual(row["alpha"], 0.02)

    def test_build_strategy_row_with_overrides(self):
        """Test build_strategy_row with strategy_label and universe_label overrides."""
        res_pre = _make_strategy_result(
            strategy_name="top_5",
            cagr=0.16,
            is_after_tax=False,
        )
        res_post = _make_strategy_result(
            strategy_name="top_5",
            cagr=0.13,
            post_liquidation_cagr=0.12,
            cumulative_return=2.5,
            max_drawdown=-0.18,
            is_after_tax=True,
        )
        row = build_strategy_row(
            res_pre=res_pre,
            res_post=res_post,
            horizon_label="20y",
            spx_after_cagr=0.10,
            strategy_label="Top 5 (Equal Weight)",
            universe_label="S&P 500",
        )

        self.assertEqual(row["horizon"], "20y")
        self.assertEqual(row["strategy"], "Top 5 (Equal Weight)")
        self.assertEqual(row["universe"], "S&P 500")
        self.assertAlmostEqual(row["pre_cagr"], 0.16)
        self.assertAlmostEqual(row["post_cagr"], 0.13)
        self.assertAlmostEqual(row["post_liq_cagr"], 0.12)
        self.assertAlmostEqual(row["cum_return"], 2.5)
        self.assertAlmostEqual(row["max_dd"], -0.18)
        self.assertAlmostEqual(row["tax_drag"], 0.03)
        self.assertAlmostEqual(row["alpha"], 0.03)

    def test_build_benchmark_row_sp500(self):
        """Test build_benchmark_row for S&P 500 variants sets alpha to 0.0."""
        metrics = BenchmarkMetrics(
            tr_cagr=0.12,
            tr_cum=2.0,
            tr_max_dd=-0.20,
            after_cagr=0.10,
            post_liq_cagr=0.09,
            cum_return=1.5,
            final_equity=25000.0,
            max_dd=-0.22,
            tax_drag=0.02,
            total_dividends=2000.0,
            total_taxes=1000.0,
        )

        # Baseline S&P 500
        row_spx = build_benchmark_row(
            name="S&P 500",
            metrics=metrics,
            horizon_label="10y",
            spx_after_cagr=0.10,
            universe_label="S&P 500",
        )
        self.assertEqual(row_spx["strategy"], "S&P 500")
        self.assertEqual(row_spx["universe"], "S&P 500")
        self.assertEqual(row_spx["horizon"], "10y")
        self.assertAlmostEqual(row_spx["pre_cagr"], 0.12)
        self.assertAlmostEqual(row_spx["post_cagr"], 0.10)
        self.assertAlmostEqual(row_spx["post_liq_cagr"], 0.09)
        self.assertAlmostEqual(row_spx["cum_return"], 1.5)
        self.assertAlmostEqual(row_spx["max_dd"], -0.22)
        self.assertAlmostEqual(row_spx["tax_drag"], 0.02)
        self.assertAlmostEqual(row_spx["alpha"], 0.0)

        # Frequency annotated S&P 500 variants
        for variant in ["S&P 500 (Annual)", "S&P 500 (Quarterly)"]:
            row_variant = build_benchmark_row(
                name=variant,
                metrics=metrics,
                horizon_label="10y",
                spx_after_cagr=0.10,
            )
            self.assertEqual(row_variant["strategy"], variant)
            self.assertNotIn("universe", row_variant)
            self.assertAlmostEqual(row_variant["alpha"], 0.0)

    def test_build_benchmark_row_non_spx(self):
        """Test build_benchmark_row for non-SPX indices calculates relative alpha."""
        metrics_nasdaq = BenchmarkMetrics(
            tr_cagr=0.18,
            tr_cum=4.0,
            tr_max_dd=-0.25,
            after_cagr=0.15,
            post_liq_cagr=0.14,
            cum_return=3.2,
            final_equity=42000.0,
            max_dd=-0.28,
            tax_drag=0.03,
            total_dividends=500.0,
            total_taxes=800.0,
        )

        row_nasdaq = build_benchmark_row(
            name="Nasdaq 100",
            metrics=metrics_nasdaq,
            horizon_label="10y",
            spx_after_cagr=0.10,
            universe_label="Nasdaq 100",
        )
        self.assertEqual(row_nasdaq["strategy"], "Nasdaq 100")
        self.assertEqual(row_nasdaq["universe"], "Nasdaq 100")
        self.assertAlmostEqual(row_nasdaq["pre_cagr"], 0.18)
        self.assertAlmostEqual(row_nasdaq["post_cagr"], 0.15)
        self.assertAlmostEqual(row_nasdaq["alpha"], 0.05)

        # MSCI World
        metrics_msci = BenchmarkMetrics(
            tr_cagr=0.09,
            tr_cum=1.3,
            tr_max_dd=-0.22,
            after_cagr=0.07,
            post_liq_cagr=0.065,
            cum_return=1.0,
            final_equity=20000.0,
            max_dd=-0.24,
            tax_drag=0.02,
            total_dividends=1500.0,
            total_taxes=600.0,
        )
        row_msci = build_benchmark_row(
            name="MSCI World",
            metrics=metrics_msci,
            horizon_label="10y",
            spx_after_cagr=0.10,
            universe_label="All World",
        )
        self.assertEqual(row_msci["strategy"], "MSCI World")
        self.assertAlmostEqual(row_msci["alpha"], -0.03)

        # FBGRX
        metrics_fbgrx = BenchmarkMetrics(
            tr_cagr=0.16,
            tr_cum=3.5,
            tr_max_dd=-0.30,
            after_cagr=0.13,
            post_liq_cagr=0.12,
            cum_return=2.8,
            final_equity=38000.0,
            max_dd=-0.32,
            tax_drag=0.03,
            total_dividends=800.0,
            total_taxes=900.0,
        )
        row_fbgrx = build_benchmark_row(
            name="FBGRX",
            metrics=metrics_fbgrx,
            horizon_label="10y",
            spx_after_cagr=0.10,
            universe_label="Mutual Fund",
        )
        self.assertEqual(row_fbgrx["strategy"], "FBGRX")
        self.assertAlmostEqual(row_fbgrx["alpha"], 0.03)

    def test_format_terminal_table_integration(self):
        """Test that rows produced by the builders can be passed directly to format_terminal_table."""
        res_pre = _make_strategy_result(strategy_name="top_5", cagr=0.15, is_after_tax=False)
        res_post = _make_strategy_result(
            strategy_name="top_5",
            cagr=0.12,
            post_liquidation_cagr=0.11,
            cumulative_return=2.0,
            max_drawdown=-0.15,
            is_after_tax=True,
        )
        strat_row = build_strategy_row(res_pre, res_post, "10y", 0.10, universe_label="S&P 500")

        metrics_spx = BenchmarkMetrics(
            tr_cagr=0.12, tr_cum=2.0, tr_max_dd=-0.20,
            after_cagr=0.10, post_liq_cagr=0.09, cum_return=1.5,
            final_equity=25000.0, max_dd=-0.22, tax_drag=0.02,
            total_dividends=2000.0, total_taxes=1000.0,
        )
        bm_row = build_benchmark_row("S&P 500", metrics_spx, "10y", 0.10, universe_label="S&P 500")

        output = format_terminal_table([strat_row, bm_row])
        self.assertIn("S&P 500", output)
        self.assertIn("top_5", output)
        self.assertIn("Universe", output)
        self.assertIn("Pre-Tax CAGR", output)


if __name__ == "__main__":
    unittest.main()
