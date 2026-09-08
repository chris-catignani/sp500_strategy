"""Unit tests for constituent selectors (MarketCapSelector, PerformanceSelector)."""

import unittest
from engine.models import ConstituentSnapshot, HoldingTarget
from engine.selector import BaseSelector, MarketCapSelector, PerformanceSelector
import engine


class TestSelector(unittest.TestCase):
    """Test suite for pluggable selector implementations."""

    def setUp(self):
        self.universe = [
            ConstituentSnapshot(
                ticker="AAPL",
                name="Apple Inc.",
                market_cap_weight=0.07,
                trailing_1y_return=0.15,
                year=2024,
            ),
            ConstituentSnapshot(
                ticker="MSFT",
                name="Microsoft Corp.",
                market_cap_weight=0.06,
                trailing_1y_return=0.10,
                year=2024,
            ),
            ConstituentSnapshot(
                ticker="NVDA",
                name="NVIDIA Corp.",
                market_cap_weight=0.05,
                trailing_1y_return=1.20,
                year=2024,
            ),
            ConstituentSnapshot(
                ticker="AMZN",
                name="Amazon.com Inc.",
                market_cap_weight=0.04,
                trailing_1y_return=0.25,
                year=2024,
            ),
            ConstituentSnapshot(
                ticker="GOOGL",
                name="Alphabet Inc.",
                market_cap_weight=0.03,
                trailing_1y_return=0.05,
                year=2024,
            ),
        ]

    def test_base_selector_abstract(self):
        """BaseSelector cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            BaseSelector(n=5)  # type: ignore

    def test_market_cap_selector_selection_and_weighting(self):
        """MarketCapSelector selects top N by market_cap_weight and normalizes weights."""
        selector = MarketCapSelector(n=3)
        targets = selector.select(self.universe)

        self.assertEqual(len(targets), 3)
        # Expected tickers in order of market_cap_weight descending: AAPL (0.07), MSFT (0.06), NVDA (0.05)
        self.assertEqual([t.ticker for t in targets], ["AAPL", "MSFT", "NVDA"])

        # Expected normalized weights: W_i / sum(W) where sum = 0.07 + 0.06 + 0.05 = 0.18
        expected_weights = [0.07 / 0.18, 0.06 / 0.18, 0.05 / 0.18]
        for target, expected in zip(targets, expected_weights):
            self.assertIsInstance(target, HoldingTarget)
            self.assertAlmostEqual(target.target_weight, expected, places=7)
            self.assertEqual(target.target_dollar, 0.0)
            self.assertEqual(target.target_shares, 0.0)

        # Sum of normalized weights must be 1.0
        self.assertAlmostEqual(sum(t.target_weight for t in targets), 1.0, places=7)

    def test_performance_selector_selection_and_relative_market_cap_weighting(self):
        """PerformanceSelector selects top N by trailing_1y_return, weighted by relative market cap."""
        selector = PerformanceSelector(n=3)
        targets = selector.select(self.universe)

        self.assertEqual(len(targets), 3)
        # Expected tickers in order of trailing_1y_return descending:
        # NVDA (1.20), AMZN (0.25), AAPL (0.15)
        self.assertEqual([t.ticker for t in targets], ["NVDA", "AMZN", "AAPL"])

        # Relative market cap weighting: NVDA (0.05), AMZN (0.04), AAPL (0.07) -> sum = 0.16
        expected_weights = [0.05 / 0.16, 0.04 / 0.16, 0.07 / 0.16]
        for target, expected in zip(targets, expected_weights):
            self.assertIsInstance(target, HoldingTarget)
            self.assertAlmostEqual(target.target_weight, expected, places=7)

        # Sum of normalized weights must be 1.0
        self.assertAlmostEqual(sum(t.target_weight for t in targets), 1.0, places=7)

    def test_performance_selector_equal_weighting(self):
        """PerformanceSelector supports weight_by='equal'."""
        selector = PerformanceSelector(n=3, weight_by="equal")
        targets = selector.select(self.universe)

        self.assertEqual(len(targets), 3)
        self.assertEqual([t.ticker for t in targets], ["NVDA", "AMZN", "AAPL"])
        for target in targets:
            self.assertAlmostEqual(target.target_weight, 1.0 / 3.0, places=7)
        self.assertAlmostEqual(sum(t.target_weight for t in targets), 1.0, places=7)

    def test_market_cap_selector_equal_weighting(self):
        """MarketCapSelector also supports weight_by='equal'."""
        selector = MarketCapSelector(n=4, weight_by="equal")
        targets = selector.select(self.universe)

        self.assertEqual(len(targets), 4)
        self.assertEqual([t.ticker for t in targets], ["AAPL", "MSFT", "NVDA", "AMZN"])
        for target in targets:
            self.assertAlmostEqual(target.target_weight, 0.25, places=7)
        self.assertAlmostEqual(sum(t.target_weight for t in targets), 1.0, places=7)

    def test_universe_smaller_than_n(self):
        """Gracefully handle universe with fewer constituents than N."""
        small_universe = self.universe[:2]  # AAPL (0.07), MSFT (0.06)
        selector = MarketCapSelector(n=5)
        targets = selector.select(small_universe)

        self.assertEqual(len(targets), 2)
        self.assertEqual([t.ticker for t in targets], ["AAPL", "MSFT"])
        expected_sum = 0.07 + 0.06
        self.assertAlmostEqual(targets[0].target_weight, 0.07 / expected_sum, places=7)
        self.assertAlmostEqual(targets[1].target_weight, 0.06 / expected_sum, places=7)
        self.assertAlmostEqual(sum(t.target_weight for t in targets), 1.0, places=7)

    def test_empty_universe(self):
        """Selecting from an empty universe returns an empty list."""
        selector = MarketCapSelector(n=5)
        self.assertEqual(selector.select([]), [])

        perf_selector = PerformanceSelector(n=5)
        self.assertEqual(perf_selector.select([]), [])

    def test_all_zero_weights_fallback_to_equal(self):
        """If market cap weights are all 0, fall back to equal weighting."""
        zero_mc_universe = [
            ConstituentSnapshot("A", "Company A", market_cap_weight=0.0, trailing_1y_return=0.1, year=2024),
            ConstituentSnapshot("B", "Company B", market_cap_weight=0.0, trailing_1y_return=0.2, year=2024),
            ConstituentSnapshot("C", "Company C", market_cap_weight=0.0, trailing_1y_return=0.3, year=2024),
        ]
        selector = MarketCapSelector(n=2)
        targets = selector.select(zero_mc_universe)
        self.assertEqual(len(targets), 2)
        for target in targets:
            self.assertAlmostEqual(target.target_weight, 0.5, places=7)
        self.assertAlmostEqual(sum(t.target_weight for t in targets), 1.0, places=7)

        perf_selector = PerformanceSelector(n=2)
        perf_targets = perf_selector.select(zero_mc_universe)
        self.assertEqual(len(perf_targets), 2)
        self.assertEqual([t.ticker for t in perf_targets], ["C", "B"])
        for target in perf_targets:
            self.assertAlmostEqual(target.target_weight, 0.5, places=7)
        self.assertAlmostEqual(sum(t.target_weight for t in perf_targets), 1.0, places=7)

    def test_override_n_in_select(self):
        """Calling select(universe, n=...) overrides default n."""
        selector = MarketCapSelector(n=5)
        targets = selector.select(self.universe, n=2)
        self.assertEqual(len(targets), 2)
        self.assertEqual([t.ticker for t in targets], ["AAPL", "MSFT"])
        self.assertAlmostEqual(sum(t.target_weight for t in targets), 1.0, places=7)

    def test_negative_returns_ranking(self):
        """PerformanceSelector correctly ranks negative returns."""
        down_universe = [
            ConstituentSnapshot("LOSER1", "L1", market_cap_weight=0.05, trailing_1y_return=-0.50, year=2024),
            ConstituentSnapshot("LOSER2", "L2", market_cap_weight=0.05, trailing_1y_return=-0.10, year=2024),
            ConstituentSnapshot("LOSER3", "L3", market_cap_weight=0.05, trailing_1y_return=-0.25, year=2024),
        ]
        selector = PerformanceSelector(n=2)
        targets = selector.select(down_universe)
        self.assertEqual([t.ticker for t in targets], ["LOSER2", "LOSER3"])

    def test_invalid_parameters(self):
        """Invalid parameters raise ValueError."""
        with self.assertRaises(ValueError):
            MarketCapSelector(n=0)
        with self.assertRaises(ValueError):
            MarketCapSelector(n=-1)
        with self.assertRaises(ValueError):
            MarketCapSelector(n=5, weight_by="invalid_mode")
        with self.assertRaises(ValueError):
            PerformanceSelector(n=0)
        with self.assertRaises(ValueError):
            PerformanceSelector(n=5, weight_by="invalid_mode")

        selector = MarketCapSelector(n=5)
        with self.assertRaises(ValueError):
            selector.select(self.universe, n=0)
        with self.assertRaises(ValueError):
            selector.select(self.universe, n=-3)

    def test_package_level_exports(self):
        """BaseSelector, MarketCapSelector, PerformanceSelector must be exported in engine."""
        self.assertTrue(hasattr(engine, "BaseSelector"))
        self.assertTrue(hasattr(engine, "MarketCapSelector"))
        self.assertTrue(hasattr(engine, "PerformanceSelector"))
        self.assertIn("BaseSelector", engine.__all__)
        self.assertIn("MarketCapSelector", engine.__all__)
        self.assertIn("PerformanceSelector", engine.__all__)


if __name__ == "__main__":
    unittest.main()
