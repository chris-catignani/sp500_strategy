"""Google Apps Script dashboard generator.

Generates self-contained, interactive Google Apps Script (.js) code
ready to be installed in Google Sheets Script Editor.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from engine.exporters.csv import _ensure_dir_exists
from engine.scenarios import build_default_scenario_data

GAS_TEMPLATE_DIR = (
    Path(__file__).resolve().parent.parent / "templates" / "gas"
)

EXPECTED_PLACEHOLDERS = (
    "/*__BASE_INITIAL_CAPITAL__*/10000",
    "/*__SCENARIO_DATA__*/[]",
    "/*__TOP3_ANNUAL_DATA__*/[]",
    "/*__TOP5_ANNUAL_DATA__*/[]",
    "/*__TOP10_ANNUAL_DATA__*/[]",
    "/*__WORLD_TOP3_ANNUAL_DATA__*/[]",
    "/*__WORLD_TOP5_ANNUAL_DATA__*/[]",
    "/*__WORLD_TOP10_ANNUAL_DATA__*/[]",
    "/*__SPX_DATA__*/[]",
    "/*__TRADE_DATA__*/[]",
    "/*__ERA_DATA__*/[]",
    "/*__TRAJECTORY_DATA__*/[]",
    "/*__DRAWDOWN_DATA__*/[]",
    "/*__ERA_MATRIX__*/[]",
    "/*__TRAJECTORY_MATRIX__*/[]",
    "/*__DRAWDOWN_MATRIX__*/[]",
)


def load_apps_script_template() -> str:
    """Load and concatenate modular Google Apps Script template partials.

    Reads all .js files in engine/templates/gas in alphabetical order,
    normalizes whitespace, joins with double newlines to prevent ASI and
    single-line comment swallowing issues, and asserts all 16 required
    placeholders are present.

    Returns:
        The concatenated template string.

    Raises:
        FileNotFoundError: If the template directory or partials are missing.
        ValueError: If any required placeholder is missing.
    """
    if not GAS_TEMPLATE_DIR.is_dir():
        raise FileNotFoundError(
            f"Google Apps Script template directory not found: {GAS_TEMPLATE_DIR}"
        )

    js_files = sorted(GAS_TEMPLATE_DIR.glob("*.js"))
    if not js_files:
        raise FileNotFoundError(
            f"No .js template partials found in {GAS_TEMPLATE_DIR}"
        )

    parts = [fpath.read_text(encoding="utf-8").strip() for fpath in js_files]
    template = "\n\n".join(parts) + "\n"

    for ph in EXPECTED_PLACEHOLDERS:
        if ph not in template:
            raise ValueError(
                f"Missing required template placeholder in Apps Script templates: {ph}"
            )

    return template


def generate_google_apps_script(
    scenario_data: Optional[Dict[str, Any]] = None,
    annual_data: Optional[Dict[str, Any]] = None,
    trades_data: Optional[List[Union[Dict[str, Any], Any]]] = None,
    initial_capital: Optional[float] = None,
) -> str:
    """Generate a complete, self-contained Google Apps Script (.js).

    The script creates and formats:
    - Executive Summary (Interactive Dashboard with tax rate and seed capital selectors)
    - Top 3 Strategy (30-year annual breakdown)
    - Top 5 Strategy (30-year annual breakdown)
    - Top 10 Strategy (30-year annual breakdown)
    - S&P 500 Benchmark (Annual levels & compounded growth)
    - Historical Holdings & Trades (Detailed transaction logs)
    - Scenario Data (Pre-calculated lookup matrix across tax tiers: 0%, 15%, 20%, 30%, 37%)

    Args:
        scenario_data: Optional custom scenario dataset.
        annual_data: Optional custom annual ledger dataset.
        trades_data: Optional custom trades dataset.
        initial_capital: Optional starting seed capital basis.

    Returns:
        A JavaScript string ready to be installed in Google Sheets Script Editor.
    """
    if scenario_data is None or annual_data is None or trades_data is None:
        defaults = build_default_scenario_data()
        scenario_rows = (
            defaults["scenario_rows"]
            if scenario_data is None
            else scenario_data.get("scenario_rows", defaults["scenario_rows"])
        )

        if annual_data is None:
            top3_annual = defaults["top3_annual"]
            top5_annual = defaults["top5_annual"]
            top10_annual = defaults["top10_annual"]
            world_top3_annual = defaults["world_top3_annual"]
            world_top5_annual = defaults["world_top5_annual"]
            world_top10_annual = defaults["world_top10_annual"]
            spx_data = defaults["spx_data"]
            era_data = defaults["era_data"]
            trajectory_data = defaults["trajectory_data"]
            drawdown_data = defaults["drawdown_data"]
            era_matrix = defaults.get("era_matrix", [])
            trajectory_matrix = defaults.get("trajectory_matrix", [])
            drawdown_matrix = defaults.get("drawdown_matrix", [])
        else:
            top3_annual = annual_data.get("top_3") or annual_data.get("top3_annual", defaults["top3_annual"])
            top5_annual = annual_data.get("top_5") or annual_data.get("top5_annual", defaults["top5_annual"])
            top10_annual = annual_data.get("top_10") or annual_data.get("top10_annual", defaults["top10_annual"])
            world_top3_annual = annual_data.get("world_top_3") or annual_data.get("world_top3_annual", defaults.get("world_top3_annual", []))
            world_top5_annual = annual_data.get("world_top_5") or annual_data.get("world_top5_annual", defaults.get("world_top5_annual", []))
            world_top10_annual = annual_data.get("world_top_10") or annual_data.get("world_top10_annual", defaults.get("world_top10_annual", []))
            spx_data = annual_data.get("spx") or annual_data.get("spx_data", defaults["spx_data"])
            era_data = annual_data.get("era_data", defaults["era_data"])
            trajectory_data = annual_data.get("trajectory_data", defaults["trajectory_data"])
            drawdown_data = annual_data.get("drawdown_data", defaults["drawdown_data"])
            era_matrix = annual_data.get("era_matrix", defaults.get("era_matrix", []))
            trajectory_matrix = annual_data.get("trajectory_matrix", defaults.get("trajectory_matrix", []))
            drawdown_matrix = annual_data.get("drawdown_matrix", defaults.get("drawdown_matrix", []))

        source_trades = defaults["trades_data"] if trades_data is None else trades_data
    else:
        scenario_rows = scenario_data.get("scenario_rows", [])
        top3_annual = annual_data.get("top_3") or annual_data.get("top3_annual", [])
        top5_annual = annual_data.get("top_5") or annual_data.get("top5_annual", [])
        top10_annual = annual_data.get("top_10") or annual_data.get("top10_annual", [])
        world_top3_annual = annual_data.get("world_top_3") or annual_data.get("world_top3_annual", [])
        world_top5_annual = annual_data.get("world_top_5") or annual_data.get("world_top5_annual", [])
        world_top10_annual = annual_data.get("world_top_10") or annual_data.get("world_top10_annual", [])
        spx_data = annual_data.get("spx") or annual_data.get("spx_data", [])
        era_data = annual_data.get("era_data")
        trajectory_data = annual_data.get("trajectory_data")
        drawdown_data = annual_data.get("drawdown_data")
        era_matrix = annual_data.get("era_matrix")
        trajectory_matrix = annual_data.get("trajectory_matrix")
        drawdown_matrix = annual_data.get("drawdown_matrix")

        if era_data is None or trajectory_data is None or drawdown_data is None or era_matrix is None or trajectory_matrix is None or drawdown_matrix is None:
            defaults = build_default_scenario_data()
            if era_data is None:
                era_data = defaults["era_data"]
            if trajectory_data is None:
                trajectory_data = defaults["trajectory_data"]
            if drawdown_data is None:
                drawdown_data = defaults["drawdown_data"]
            if era_matrix is None:
                era_matrix = defaults.get("era_matrix", [])
            if trajectory_matrix is None:
                trajectory_matrix = defaults.get("trajectory_matrix", [])
            if drawdown_matrix is None:
                drawdown_matrix = defaults.get("drawdown_matrix", [])
            if not world_top3_annual:
                world_top3_annual = defaults.get("world_top3_annual", [])
            if not world_top5_annual:
                world_top5_annual = defaults.get("world_top5_annual", [])
            if not world_top10_annual:
                world_top10_annual = defaults.get("world_top10_annual", [])

        source_trades = trades_data

    # Format trades records
    final_trade_rows: List[List[Any]] = []
    for t in source_trades:
        if isinstance(t, list):
            final_trade_rows.append(t)
        elif isinstance(t, dict):
            final_trade_rows.append([
                t.get("year", 0),
                t.get("strategy_name", ""),
                t.get("ticker", ""),
                t.get("action", ""),
                round(float(t.get("shares", 0.0)), 4),
                round(float(t.get("price", 0.0)), 2),
                round(float(t.get("realized_gain", 0.0)), 2),
            ])
        else:
            final_trade_rows.append([
                getattr(t, "year", 0),
                getattr(t, "strategy_name", ""),
                getattr(t, "ticker", ""),
                getattr(t, "action", ""),
                round(float(getattr(t, "shares", 0.0)), 4),
                round(float(getattr(t, "price", 0.0)), 2),
                round(float(getattr(t, "realized_gain", 0.0)), 2),
            ])

    if initial_capital is None:
        if spx_data and len(spx_data) > 0 and len(spx_data[0]) > 3 and isinstance(spx_data[0][3], (int, float)):
            initial_capital = float(spx_data[0][3])
        elif trajectory_data and len(trajectory_data) > 0 and len(trajectory_data[0]) > 1 and isinstance(trajectory_data[0][1], (int, float)):
            initial_capital = float(trajectory_data[0][1])
        else:
            initial_capital = 10000.0

    base_cap_str = str(int(initial_capital)) if float(initial_capital).is_integer() else str(initial_capital)

    template = load_apps_script_template()

    replacements = {
        "/*__BASE_INITIAL_CAPITAL__*/10000": base_cap_str,
        "/*__SCENARIO_DATA__*/[]": json.dumps(scenario_rows),
        "/*__TOP3_ANNUAL_DATA__*/[]": json.dumps(top3_annual),
        "/*__TOP5_ANNUAL_DATA__*/[]": json.dumps(top5_annual),
        "/*__TOP10_ANNUAL_DATA__*/[]": json.dumps(top10_annual),
        "/*__WORLD_TOP3_ANNUAL_DATA__*/[]": json.dumps(world_top3_annual),
        "/*__WORLD_TOP5_ANNUAL_DATA__*/[]": json.dumps(world_top5_annual),
        "/*__WORLD_TOP10_ANNUAL_DATA__*/[]": json.dumps(world_top10_annual),
        "/*__SPX_DATA__*/[]": json.dumps(spx_data),
        "/*__TRADE_DATA__*/[]": json.dumps(final_trade_rows),
        "/*__ERA_DATA__*/[]": json.dumps(era_data),
        "/*__TRAJECTORY_DATA__*/[]": json.dumps(trajectory_data),
        "/*__DRAWDOWN_DATA__*/[]": json.dumps(drawdown_data),
        "/*__ERA_MATRIX__*/[]": json.dumps(era_matrix),
        "/*__TRAJECTORY_MATRIX__*/[]": json.dumps(trajectory_matrix),
        "/*__DRAWDOWN_MATRIX__*/[]": json.dumps(drawdown_matrix),
    }

    for placeholder, val in replacements.items():
        template = template.replace(placeholder, val)

    return template


def export_google_apps_script(
    filepath: str,
    scenario_data: Optional[Dict[str, Any]] = None,
    annual_data: Optional[Dict[str, Any]] = None,
    trades_data: Optional[List[Union[Dict[str, Any], Any]]] = None,
    initial_capital: Optional[float] = None,
) -> str:
    """Write the complete Google Apps Script file to disk.

    Args:
        filepath: Target filepath (e.g. 'scripts/google_apps_script.js').
        scenario_data: Optional custom scenario dataset.
        annual_data: Optional custom annual ledger dataset.
        trades_data: Optional custom trades dataset.
        initial_capital: Optional starting seed capital basis.

    Returns:
        The target filepath written to.
    """
    _ensure_dir_exists(filepath)
    js_code = generate_google_apps_script(
        scenario_data=scenario_data,
        annual_data=annual_data,
        trades_data=trades_data,
        initial_capital=initial_capital,
    )
    with open(filepath, mode="w", encoding="utf-8") as f:
        f.write(js_code)
    return filepath
