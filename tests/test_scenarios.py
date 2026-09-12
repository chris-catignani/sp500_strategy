"""Unit tests for engine/scenarios.py scenario generation and data structures."""

import unittest
from engine.scenarios import (
    build_default_scenario_data,
    build_scenario_and_apps_script_data,
)


class TestScenarios(unittest.TestCase):
    """Test suite for multi-horizon scenario matrix generation."""

    def test_build_scenario_and_apps_script_data_default(self):
        """Verify default invocation builds scenario data across universes and tax tiers."""
        scenario_data, annual_data, trades_data = build_scenario_and_apps_script_data()

        self.assertIn("scenario_rows", scenario_data)
        scenario_rows = scenario_data["scenario_rows"]
        self.assertGreater(len(scenario_rows), 0)
        # 17 columns per scenario row ending with RowType
        for row in scenario_rows:
            self.assertEqual(len(row), 17)
            self.assertIn(row[16], ("Strategy", "Index"))

        # Verify benchmark rows exist without duplicates (5 tax rates x 3 horizons = 15 rows each)
        spx_bench_rows = [r for r in scenario_rows if r[4] == "S&P 500" and r[16] == "Index"]
        msci_bench_rows = [r for r in scenario_rows if r[4] == "MSCI World" and r[16] == "Index"]
        self.assertEqual(len(spx_bench_rows), 15)
        self.assertEqual(len(msci_bench_rows), 15)

        # Annual data checks
        expected_keys = [
            "top_3",
            "top_5",
            "top_10",
            "world_top_3",
            "world_top_5",
            "world_top_10",
            "spx",
            "era_data",
            "trajectory_data",
            "drawdown_data",
        ]
        for key in expected_keys:
            self.assertIn(key, annual_data)
            self.assertGreater(len(annual_data[key]), 0)

        # Trades data checks
        self.assertIsInstance(trades_data, list)
        self.assertGreater(len(trades_data), 0)

    def test_build_scenario_single_universe(self):
        """Verify single universe does not crash era or trajectory generation."""
        scenario_data, annual_data, trades_data = build_scenario_and_apps_script_data(
            universes=["world"],
            initial_capital=50000.0,
            strategy_name="performance",
        )
        self.assertIn("scenario_rows", scenario_data)
        self.assertIn("world_top_3", annual_data)
        # Trajectories should have full 31 years (1994..2024)
        self.assertEqual(len(annual_data["trajectory_data"]), 31)
        self.assertEqual(len(annual_data["drawdown_data"]), 31)

    def test_build_default_scenario_data_helper(self):
        """Verify backward-compatible build_default_scenario_data dictionary contract."""
        defaults = build_default_scenario_data()
        self.assertIsInstance(defaults, dict)
        required_keys = [
            "scenario_rows",
            "top3_annual",
            "top5_annual",
            "top10_annual",
            "world_top3_annual",
            "world_top5_annual",
            "world_top10_annual",
            "spx_data",
            "trades_data",
            "era_data",
            "trajectory_data",
            "drawdown_data",
        ]
        for k in required_keys:
            self.assertIn(k, defaults)
            self.assertGreater(len(defaults[k]), 0)


if __name__ == "__main__":
    unittest.main()
