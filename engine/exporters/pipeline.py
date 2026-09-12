"""Report and export pipeline orchestrator.

Coordinates writing of CSV summaries, annual ledgers, trade logs,
and Google Apps Script dashboards across target directories.
"""

import os
from typing import Any, Dict, List, Optional, Union

from engine.exporters.csv import (
    export_annual_breakdown_csv,
    export_summary_metrics_csv,
    export_trade_log_csv,
)
from engine.exporters.apps_script import export_google_apps_script
from engine.models import StrategyResult


class ReportExporter:
    """Coordinates reporting and file export pipelines for backtest results."""

    def __init__(self, output_dir: str = "outputs", scripts_dir: str = "scripts") -> None:
        """Initialize ReportExporter with target output directories.

        Args:
            output_dir: Directory for CSV outputs.
            scripts_dir: Directory for generated Google Apps Script file.
        """
        self.output_dir = output_dir
        self.scripts_dir = scripts_dir

    def export_summary(
        self,
        results: List[StrategyResult],
        spx_benchmarks: Optional[Dict[str, float]] = None,
        filename: str = "summary_metrics.csv",
    ) -> str:
        """Export summary metrics to CSV."""
        filepath = os.path.join(self.output_dir, filename)
        return export_summary_metrics_csv(results, filepath, spx_benchmarks=spx_benchmarks)

    def export_annual_breakdown(
        self,
        results: List[StrategyResult],
        filename: str = "annual_breakdown.csv",
    ) -> str:
        """Export annual ledger breakdowns to CSV."""
        filepath = os.path.join(self.output_dir, filename)
        return export_annual_breakdown_csv(results, filepath)

    def export_trade_log(
        self,
        trade_records: List[Union[Dict[str, Any], Any]],
        filename: str = "trade_log.csv",
    ) -> str:
        """Export trade transactions to CSV."""
        filepath = os.path.join(self.output_dir, filename)
        return export_trade_log_csv(trade_records, filepath)

    def export_apps_script(
        self,
        filename: str = "google_apps_script.js",
        scenario_data: Optional[Dict[str, Any]] = None,
        annual_data: Optional[Dict[str, Any]] = None,
        trades_data: Optional[List[Union[Dict[str, Any], Any]]] = None,
        initial_capital: Optional[float] = None,
    ) -> str:
        """Export standalone Google Apps Script file."""
        filepath = os.path.join(self.scripts_dir, filename)
        return export_google_apps_script(
            filepath,
            scenario_data=scenario_data,
            annual_data=annual_data,
            trades_data=trades_data,
            initial_capital=initial_capital,
        )

    def export_all(
        self,
        results: List[StrategyResult],
        trade_records: Optional[List[Union[Dict[str, Any], Any]]] = None,
        spx_benchmarks: Optional[Dict[str, float]] = None,
        scenario_data: Optional[Dict[str, Any]] = None,
        annual_data: Optional[Dict[str, Any]] = None,
        trades_data: Optional[List[Union[Dict[str, Any], Any]]] = None,
        initial_capital: Optional[float] = None,
    ) -> Dict[str, str]:
        """Export summary metrics, annual breakdown, trade log, and Apps Script.

        Args:
            results: List of StrategyResult objects.
            trade_records: Optional list of trade records.
            spx_benchmarks: Optional mapping of horizon to benchmark CAGR.
            scenario_data: Optional scenario dataset for Google Apps Script.
            annual_data: Optional annual dataset for Google Apps Script.
            trades_data: Optional trades dataset for Google Apps Script.
            initial_capital: Optional starting seed capital basis.

        Returns:
            Dictionary mapping artifact names to their created file paths.
        """
        files: Dict[str, str] = {}
        files["summary_metrics"] = self.export_summary(results, spx_benchmarks=spx_benchmarks)
        files["annual_breakdown"] = self.export_annual_breakdown(results)
        if trade_records is not None:
            files["trade_log"] = self.export_trade_log(trade_records)
        files["google_apps_script"] = self.export_apps_script(
            scenario_data=scenario_data,
            annual_data=annual_data,
            trades_data=trades_data,
            initial_capital=initial_capital,
        )
        return files


def export_all(
    results: List[StrategyResult],
    trade_records: Optional[List[Union[Dict[str, Any], Any]]] = None,
    output_dir: str = "outputs",
    scripts_dir: str = "scripts",
    spx_benchmarks: Optional[Dict[str, float]] = None,
    scenario_data: Optional[Dict[str, Any]] = None,
    annual_data: Optional[Dict[str, Any]] = None,
    trades_data: Optional[List[Union[Dict[str, Any], Any]]] = None,
    initial_capital: Optional[float] = None,
) -> Dict[str, str]:
    """Convenience helper function to export all report artifacts into target directories.

    Args:
        results: List of StrategyResult objects.
        trade_records: Optional list of trade records.
        output_dir: Output directory for CSV files.
        scripts_dir: Output directory for script files.
        spx_benchmarks: Optional mapping of horizon to benchmark CAGR.
        scenario_data: Optional scenario dataset for Google Apps Script.
        annual_data: Optional annual dataset for Google Apps Script.
        trades_data: Optional trades dataset for Google Apps Script.
        initial_capital: Optional starting seed capital basis.

    Returns:
        Dictionary mapping artifact names to their created file paths.
    """
    exporter = ReportExporter(output_dir=output_dir, scripts_dir=scripts_dir)
    return exporter.export_all(
        results=results,
        trade_records=trade_records,
        spx_benchmarks=spx_benchmarks,
        scenario_data=scenario_data,
        annual_data=annual_data,
        trades_data=trades_data,
        initial_capital=initial_capital,
    )
