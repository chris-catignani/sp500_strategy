"""Unit tests for reporting and exporters suite (CSVs & Google Apps Script)."""

import csv
import os
import shutil
import subprocess
import tempfile
import unittest
from engine.models import AnnualLedgerEntry, StrategyResult, TradeOrder
from engine.exporters import (
    export_summary_metrics_csv,
    export_annual_breakdown_csv,
    export_trade_log_csv,
    export_google_apps_script,
    generate_google_apps_script,
    load_apps_script_template,
    ReportExporter,
    export_all,
)
import engine


class TestExporters(unittest.TestCase):
    """Test suite for engine/exporters.py reporting and export utilities."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

        # Sample StrategyResult fixtures
        self.entry_2023 = AnnualLedgerEntry(
            year=2023,
            start_value=10000.0,
            gross_return=0.20,
            ending_value_pretax=12000.0,
            realized_capital_gain=500.0,
            net_taxable_gain=500.0,
            tax_paid=150.0,
            loss_carryforward=0.0,
            ending_value_aftertax=11850.0,
            spx_return=0.15,
            turnover=0.30,
            holdings={"AAPL": 20.0, "MSFT": 15.0},
            cash=0.0,
            dividend_income=100.0,
            dividend_tax_paid=30.0,
            capital_gains_tax_paid=120.0,
        )
        self.entry_2024 = AnnualLedgerEntry(
            year=2024,
            start_value=11850.0,
            gross_return=0.10,
            ending_value_pretax=13035.0,
            realized_capital_gain=200.0,
            net_taxable_gain=200.0,
            tax_paid=60.0,
            loss_carryforward=0.0,
            ending_value_aftertax=12975.0,
            spx_return=0.10,
            turnover=0.25,
            holdings={"AAPL": 22.0, "NVDA": 10.0},
            cash=0.0,
            dividend_income=50.0,
            dividend_tax_paid=15.0,
            capital_gains_tax_paid=45.0,
        )

        self.res_aftertax = StrategyResult(
            strategy_name="top_5_market_cap",
            n=5,
            start_year=2022,
            end_year=2024,
            is_after_tax=True,
            tax_rate=0.30,
            initial_capital=10000.0,
            final_equity=12975.0,
            cagr=0.1390,
            cumulative_return=0.2975,
            max_drawdown=-0.05,
            total_taxes_paid=210.0,
            pre_liquidation_wealth=12975.0,
            post_liquidation_wealth=12500.0,
            post_liquidation_cagr=0.1180,
            annual_history=[self.entry_2023, self.entry_2024],
            total_dividends_received=150.0,
            total_dividend_taxes_paid=45.0,
        )

        self.res_pretax = StrategyResult(
            strategy_name="top_5_market_cap",
            n=5,
            start_year=2022,
            end_year=2024,
            is_after_tax=False,
            tax_rate=0.30,
            initial_capital=10000.0,
            final_equity=13200.0,
            cagr=0.1489,
            cumulative_return=0.3200,
            max_drawdown=-0.05,
            total_taxes_paid=0.0,
            pre_liquidation_wealth=13200.0,
            post_liquidation_wealth=13200.0,
            post_liquidation_cagr=0.1489,
            annual_history=[self.entry_2023, self.entry_2024],
        )
        self.results = [self.res_pretax, self.res_aftertax]

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_summary_csv_has_dividend_column(self):
        tmp_path = os.path.join(self.test_dir, "test_summary.csv")
        export_summary_metrics_csv(self.results, tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
        self.assertIn("total_dividends_received", headers)

    def test_annual_csv_has_dividend_columns(self):
        tmp_path = os.path.join(self.test_dir, "test_annual.csv")
        export_annual_breakdown_csv(self.results, tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
        self.assertIn("dividend_income", headers)
        self.assertIn("dividend_tax_paid", headers)
        self.assertIn("capital_gains_tax_paid", headers)

    def test_engine_reexports(self):
        """Verify exporter functions and classes are re-exported by the engine module."""
        self.assertIs(engine.export_summary_metrics_csv, export_summary_metrics_csv)
        self.assertIs(engine.export_annual_breakdown_csv, export_annual_breakdown_csv)
        self.assertIs(engine.export_trade_log_csv, export_trade_log_csv)
        self.assertIs(engine.generate_google_apps_script, generate_google_apps_script)
        self.assertIs(engine.export_google_apps_script, export_google_apps_script)
        self.assertIs(engine.ReportExporter, ReportExporter)
        self.assertIs(engine.export_all, export_all)

    def test_export_summary_metrics_csv(self):
        """Test summary metrics CSV generation, column headers, and calculations."""
        filepath = os.path.join(self.test_dir, "outputs", "summary_metrics.csv")
        results = [self.res_pretax, self.res_aftertax]
        spx_benchmarks = {"2y": 0.125}

        export_summary_metrics_csv(results, filepath, spx_benchmarks=spx_benchmarks)
        self.assertTrue(os.path.exists(filepath))

        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        expected_columns = [
            "strategy_name",
            "n",
            "horizon",
            "start_year",
            "end_year",
            "is_after_tax",
            "tax_rate",
            "initial_capital",
            "final_equity",
            "cumulative_return",
            "cagr",
            "max_drawdown",
            "total_taxes_paid",
            "total_dividends_received",
            "pre_liquidation_wealth",
            "post_liquidation_wealth",
            "post_liquidation_cagr",
            "tax_drag",
            "alpha_vs_spx",
        ]
        self.assertEqual(reader.fieldnames, expected_columns)
        self.assertEqual(len(rows), 2)

        # Pre-tax row checks
        row_pre = rows[0]
        self.assertEqual(row_pre["strategy_name"], "top_5_market_cap")
        self.assertEqual(row_pre["n"], "5")
        self.assertEqual(row_pre["horizon"], "2y")
        self.assertEqual(row_pre["start_year"], "2022")
        self.assertEqual(row_pre["end_year"], "2024")
        self.assertEqual(row_pre["is_after_tax"], "False")
        self.assertAlmostEqual(float(row_pre["tax_drag"]), 0.0, places=4)
        self.assertAlmostEqual(float(row_pre["alpha_vs_spx"]), 0.1489 - 0.125, places=4)

        # After-tax row checks
        row_post = rows[1]
        self.assertEqual(row_post["is_after_tax"], "True")
        self.assertAlmostEqual(float(row_post["total_taxes_paid"]), 210.0, places=2)
        self.assertAlmostEqual(float(row_post["total_dividends_received"]), 150.0, places=2)
        # Tax drag = pretax CAGR (0.1489) - aftertax CAGR (0.1390) ~ 0.0099
        self.assertAlmostEqual(float(row_post["tax_drag"]), 0.1489 - 0.1390, places=4)
        self.assertAlmostEqual(float(row_post["alpha_vs_spx"]), 0.1390 - 0.125, places=4)

    def test_export_annual_breakdown_csv(self):
        """Test annual breakdown CSV output schema and row-level accounting values."""
        filepath = os.path.join(self.test_dir, "outputs", "annual_breakdown.csv")
        results = [self.res_aftertax]

        export_annual_breakdown_csv(results, filepath)
        self.assertTrue(os.path.exists(filepath))

        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        expected_columns = [
            "strategy_name",
            "n",
            "is_after_tax",
            "tax_rate",
            "year",
            "start_value",
            "gross_return",
            "dividend_income",
            "ending_value_pretax",
            "realized_capital_gain",
            "net_taxable_gain",
            "capital_gains_tax_paid",
            "dividend_tax_paid",
            "tax_paid",
            "loss_carryforward",
            "ending_value_aftertax",
            "cash",
            "spx_return",
            "turnover",
        ]
        self.assertEqual(reader.fieldnames, expected_columns)
        self.assertEqual(len(rows), 2)

        self.assertEqual(rows[0]["year"], "2023")
        self.assertAlmostEqual(float(rows[0]["start_value"]), 10000.0, places=2)
        self.assertAlmostEqual(float(rows[0]["dividend_income"]), 100.0, places=2)
        self.assertAlmostEqual(float(rows[0]["dividend_tax_paid"]), 30.0, places=2)
        self.assertAlmostEqual(float(rows[0]["capital_gains_tax_paid"]), 120.0, places=2)
        self.assertAlmostEqual(float(rows[0]["tax_paid"]), 150.0, places=2)
        self.assertAlmostEqual(float(rows[0]["spx_return"]), 0.15, places=4)
        self.assertAlmostEqual(float(rows[0]["turnover"]), 0.30, places=4)

        self.assertEqual(rows[1]["year"], "2024")
        self.assertAlmostEqual(float(rows[1]["start_value"]), 11850.0, places=2)
        self.assertAlmostEqual(float(rows[1]["dividend_income"]), 50.0, places=2)
        self.assertAlmostEqual(float(rows[1]["dividend_tax_paid"]), 15.0, places=2)
        self.assertAlmostEqual(float(rows[1]["capital_gains_tax_paid"]), 45.0, places=2)
        self.assertAlmostEqual(float(rows[1]["tax_paid"]), 60.0, places=2)

    def test_export_trade_log_csv(self):
        """Test trade log CSV with both dictionary records and TradeOrder instances."""
        filepath = os.path.join(self.test_dir, "outputs", "trade_log.csv")
        trade_dict = {
            "strategy_name": "top_5_market_cap",
            "n": 5,
            "year": 2023,
            "ticker": "AAPL",
            "action": "BUY",
            "shares": 20.0,
            "price": 150.0,
            "realized_gain": 0.0,
        }
        trade_order = TradeOrder(
            ticker="MSFT",
            action="SELL",
            shares=5.0,
            price=300.0,
            year=2024,
            realized_gain=250.0,
        )
        trade_order.strategy_name = "top_5_market_cap"
        trade_order.n = 5

        records = [trade_dict, trade_order]
        export_trade_log_csv(records, filepath)
        self.assertTrue(os.path.exists(filepath))

        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        expected_columns = [
            "strategy_name",
            "n",
            "year",
            "ticker",
            "action",
            "shares",
            "price",
            "realized_gain",
        ]
        self.assertEqual(reader.fieldnames, expected_columns)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["ticker"], "AAPL")
        self.assertEqual(rows[0]["action"], "BUY")
        self.assertEqual(rows[1]["ticker"], "MSFT")
        self.assertEqual(rows[1]["action"], "SELL")
        self.assertAlmostEqual(float(rows[1]["realized_gain"]), 250.0, places=2)

    def test_directory_auto_creation(self):
        """Test automatic directory hierarchy creation if paths do not exist."""
        nested_path = os.path.join(self.test_dir, "nested", "level2", "test.csv")
        export_summary_metrics_csv([self.res_pretax], nested_path)
        self.assertTrue(os.path.exists(nested_path))

    def test_load_apps_script_template(self):
        """Test that load_apps_script_template concatenates partials and validates placeholders."""
        from unittest.mock import patch
        from pathlib import Path

        # 1. Successful load from gas directory
        template = load_apps_script_template()
        self.assertIsInstance(template, str)
        self.assertGreater(len(template), 10000)
        self.assertIn("function onOpen()", template)
        self.assertIn("function buildAllSheets()", template)
        self.assertIn("function buildExecutiveSummarySheet", template)
        self.assertIn("function buildPerformanceAndTradeoffsSheet", template)

        # Verify all expected placeholders are present
        from engine.exporters.apps_script import EXPECTED_PLACEHOLDERS
        for ph in EXPECTED_PLACEHOLDERS:
            self.assertIn(ph, template)

        # 2. Test FileNotFoundError if directory does not exist
        with patch("engine.exporters.apps_script.GAS_TEMPLATE_DIR", Path("/non/existent/dir")):
            with self.assertRaises(FileNotFoundError):
                load_apps_script_template()

        # 3. Test ValueError if placeholder is missing
        with tempfile.TemporaryDirectory() as empty_gas_dir:
            with patch("engine.exporters.apps_script.GAS_TEMPLATE_DIR", Path(empty_gas_dir)):
                # Empty dir raises FileNotFoundError
                with self.assertRaises(FileNotFoundError):
                    load_apps_script_template()

                # Dir with partial missing placeholder raises ValueError
                p = Path(empty_gas_dir) / "00_test.js"
                p.write_text("console.log('hello');", encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_apps_script_template()

    def test_generate_google_apps_script(self):
        """Test Google Apps Script generator creates valid JS with required sheets and styling."""
        js_code = generate_google_apps_script()
        self.assertIsInstance(js_code, str)
        self.assertGreater(len(js_code), 500)

        # Essential functions and menu
        self.assertIn("function onOpen()", js_code)
        self.assertIn("function buildAllSheets()", js_code)
        self.assertIn("function recalculateSheet()", js_code)
        self.assertIn("function RECALCULATE_STRATEGY", js_code)
        self.assertIn("S&P 500 Strategy", js_code)
        self.assertIn("Build All Sheets", js_code)
        self.assertIn("Recalculate Sheet", js_code)
        self.assertIn("sheet.getRange('F3').getValue()", js_code)
        self.assertIn("sheet.getRange('H3').getValue()", js_code)

        # Required tabs
        self.assertIn("Executive Summary", js_code)
        self.assertIn("Top 3 Strategy", js_code)
        self.assertIn("Top 5 Strategy", js_code)
        self.assertIn("Top 10 Strategy", js_code)
        self.assertIn("S&P 500 Benchmark", js_code)
        self.assertIn("Historical Holdings & Trades", js_code)

        # Styling & formatting elements
        self.assertIn("#1B365D", js_code)  # Navy header
        self.assertIn("$#,##0.00", js_code)  # Currency format
        self.assertIn("0.00%", js_code)  # Percentage format
        self.assertIn("30.0%", js_code)  # Default tax rate
        self.assertIn("autoResizeColumns", js_code)

        # Test writing to file
        output_js = os.path.join(self.test_dir, "scripts", "google_apps_script.js")
        export_google_apps_script(output_js)
        self.assertTrue(os.path.exists(output_js))

        # Check syntax using Node.js if available in PATH
        if shutil.which("node"):
            result = subprocess.run(["node", "-c", output_js], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"Node syntax check failed: {result.stderr}")

    def test_google_apps_script_interactive_dashboard(self):
        code = generate_google_apps_script()
        # Executive Summary checks (14-column layout A1:N1)
        self.assertIn("clearDataValidations", code)
        self.assertIn("Total Dividends Received", code)
        self.assertIn("'A1:N1'", code)
        self.assertIn("HEAD-TO-HEAD PERFORMANCE & TAX SPOTLIGHT", code)
        self.assertIn("KEY METRIC DEFINITIONS & GLOSSARY", code)
        self.assertIn("METHODOLOGY NOTE — REBALANCING, TAXES & DIVIDENDS", code)
        # 18-Column SCENARIO_HEADERS
        self.assertIn('"LookupKey"', code)
        self.assertIn('"TaxRate"', code)
        self.assertIn('"Universe"', code)
        self.assertIn('"Horizon"', code)
        self.assertIn('"Strategy"', code)
        self.assertIn('"Weighting"', code)
        self.assertIn('"Frequency"', code)
        self.assertIn('"RowType"', code)
        # Controls in Row 2 & 3
        self.assertIn("'Universe:'", code)
        self.assertIn("['S&P 500', 'All World']", code)
        self.assertIn("'Strategy:'", code)
        self.assertIn("['Top 3', 'Top 5', 'Top 10']", code)
        self.assertIn("'Weighting:'", code)
        self.assertIn("['Market Cap', 'Equal Weight']", code)
        self.assertIn("'Horizon:'", code)
        self.assertIn("['10y', '20y', '30y']", code)
        self.assertIn("'Rebalance:'", code)
        self.assertIn("['Annual', 'Quarterly']", code)
        self.assertIn("'Benchmark:'", code)
        self.assertIn("['S&P 500', 'MSCI World']", code)
        self.assertIn("'Tax Rate:'", code)
        self.assertIn("['0.0%', '15.0%', '20.0%', '30.0%', '37.0%']", code)
        self.assertIn("'Seed Capital:'", code)
        self.assertIn("requireNumberGreaterThan(0)", code)
        self.assertIn("BASE_INITIAL_CAPITAL = 10000;", code)
        self.assertIn("SCALE_EXPR", code)
        # Fully dynamic KPI formulas querying Scenario Data using user selections
        self.assertIn("stratKeyExpr = '$H$2 & \"_\" & $B$2 & \"_\" & $D$2 & \"_\" & $F$2 & \"_\" & $B$3", code)
        self.assertIn("benchKeyExpr = '$H$2 & \"_\" & IF($D$3=\"MSCI World\"", code)
        # Head-to-Head Spotlight & Net Advantage Delta Row
        self.assertIn("Net Advantage (Strategy vs", code)
        self.assertIn("=(G11 - G12)", code)
        # Legacy spilling FILTER formula should NOT be in Executive Summary
        self.assertNotIn("=IFNA(FILTER('Scenario Data'!$C$2:$P", code)
        # Multi-universe tabs and menus
        self.assertIn("'World Top 3 Strategy'", code)
        self.assertIn("'World Top 5 Strategy'", code)
        self.assertIn("'World Top 10 Strategy'", code)
        self.assertIn("Show S&P 500 Tabs Only", code)
        self.assertIn("Show All World Tabs Only", code)
        self.assertIn("Show All Tabs", code)

    def test_google_apps_script_performance_charts_and_regimes(self):
        code = generate_google_apps_script()
        # Check tab presence
        self.assertIn("'Performance & Tradeoffs'", code)
        self.assertIn("buildPerformanceAndTradeoffsSheet", code)

        # Check regime attribution
        self.assertIn("ERA_HEADERS", code)
        self.assertIn("ERA_DATA", code)
        self.assertIn("Late '90s Dot-Com Boom", code)
        self.assertIn("The 'Lost Decade' (Tech Bust & GFC)", code)
        self.assertIn("ZIRP & Tech Expansion", code)
        self.assertIn("Mega-Cap Tech & AI Concentration", code)

        # Check trajectory and drawdown series
        self.assertIn("TRAJECTORY_HEADERS", code)
        self.assertIn("TRAJECTORY_DATA", code)
        self.assertIn("DRAWDOWN_HEADERS", code)
        self.assertIn("DRAWDOWN_DATA", code)

        # Check multi-universe & multi-frequency matrix datasets
        self.assertIn("ERA_MATRIX", code)
        self.assertIn("ERA_MATRIX_HEADERS", code)
        self.assertIn("TRAJECTORY_MATRIX", code)
        self.assertIn("TRAJECTORY_MATRIX_HEADERS", code)
        self.assertIn("DRAWDOWN_MATRIX", code)
        self.assertIn("DRAWDOWN_MATRIX_HEADERS", code)

        # Check dynamic filter formulas on Performance & Tradeoffs tab
        self.assertIn("FILTER(\\'Scenario Data\\'!$AI$2:$AP$21", code)
        self.assertIn("FILTER(\\'Scenario Data\\'!$U$2:$Y$125", code)
        self.assertIn("FILTER(\\'Scenario Data\\'!$AB$2:$AF$125", code)

        # Check Rebalancing Frequency Tradeoff Table
        self.assertIn("REBALANCING FREQUENCY TRADEOFF ANALYSIS", code)
        self.assertIn("Annual Pre-Tax CAGR", code)
        self.assertIn("Quarterly Pre-Tax CAGR", code)
        self.assertIn("Frequency Advantage", code)
        self.assertIn("Quarterly Outperformance", code)

        # Check Google Sheets ChartBuilder integration
        self.assertIn("asLineChart()", code)
        self.assertIn("insertChart", code)
        self.assertIn("Growth of Seed Capital (Log Scale, 1994–2024)", code)
        self.assertIn("scaleType: 'log'", code)
        self.assertIn("Historical Drawdown from Peak (1994–2024)", code)
        self.assertIn("removeChart", code)
        self.assertIn("sheet.getRange(42, 1, 32, 5)", code)
        self.assertIn("sheet.getRange(42, 7, 32, 5)", code)

    def test_google_apps_script_custom_initial_capital(self):
        """Verify custom initial capital is injected into BASE_INITIAL_CAPITAL."""
        code = generate_google_apps_script(initial_capital=50000.0)
        self.assertIn("var BASE_INITIAL_CAPITAL = 50000;", code)

    def test_report_exporter_coordinator(self):
        """Test ReportExporter class and export_all convenience function."""
        exporter = ReportExporter(
            output_dir=os.path.join(self.test_dir, "outputs"),
            scripts_dir=os.path.join(self.test_dir, "scripts"),
        )
        trade_record = {
            "strategy_name": "top_5_market_cap",
            "n": 5,
            "year": 2023,
            "ticker": "AAPL",
            "action": "BUY",
            "shares": 10.0,
            "price": 100.0,
            "realized_gain": 0.0,
        }
        results = [self.res_pretax, self.res_aftertax]
        generated_files = exporter.export_all(results=results, trade_records=[trade_record])

        self.assertIn("summary_metrics", generated_files)
        self.assertIn("annual_breakdown", generated_files)
        self.assertIn("trade_log", generated_files)
        self.assertIn("google_apps_script", generated_files)

        for name, path in generated_files.items():
            self.assertTrue(os.path.exists(path), f"File {path} for {name} was not created")

        # Also test export_all standalone function
        generated_files_2 = export_all(
            results=results,
            trade_records=[trade_record],
            output_dir=os.path.join(self.test_dir, "out2"),
            scripts_dir=os.path.join(self.test_dir, "scripts2"),
        )
        for name, path in generated_files_2.items():
            self.assertTrue(os.path.exists(path), f"Standalone export_all failed for {name}")


if __name__ == "__main__":
    unittest.main()
