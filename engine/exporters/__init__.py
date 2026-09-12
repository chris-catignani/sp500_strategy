"""Reporting and Exporters Suite for S&P 500 Top N Strategy.

Modular package providing CSV, Google Apps Script, and multi-artifact export pipelines.
"""

from engine.exporters.csv import (
    export_annual_breakdown_csv,
    export_summary_metrics_csv,
    export_trade_log_csv,
)
from engine.exporters.apps_script import (
    export_google_apps_script,
    generate_google_apps_script,
    load_apps_script_template,
)
from engine.exporters.pipeline import (
    ReportExporter,
    export_all,
)
from engine.scenarios import (
    build_default_scenario_data,
    build_scenario_and_apps_script_data,
)

__all__ = [
    "export_summary_metrics_csv",
    "export_annual_breakdown_csv",
    "export_trade_log_csv",
    "generate_google_apps_script",
    "export_google_apps_script",
    "load_apps_script_template",
    "ReportExporter",
    "export_all",
    "build_default_scenario_data",
    "build_scenario_and_apps_script_data",
]
