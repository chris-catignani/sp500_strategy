"""Audit tool for quarterly candidate expansion and ground-truth holdings reconciliation.

Zero external dependencies - Python standard library only.
"""

import json
from pathlib import Path
import sys
from typing import Dict, List, Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.backtest import PortfolioSimulator
from engine.data_loader import DataLoader
from engine.selector import MarketCapSelector, PerformanceSelector
from engine.models import ConstituentSnapshot


# Q4 periods whose ground truth is the same filing the year-end candidate list is built
# from. They match 10/10 by construction and cannot corroborate the drift model.
CIRCULAR_Q4_PERIODS = frozenset({"2020-Q4", "2021-Q4", "2022-Q4", "2023-Q4", "2024-Q4"})


def audit_midyear_promotions():
    """Detect all instances where a stock ranked > 10 at year-end drifted into Top 10 in Q1-Q3."""
    with open(REPO_ROOT / "data" / "sp500_quarterly_constituents.json", "r", encoding="utf-8") as f:
        q_data = json.load(f)
    with open(REPO_ROOT / "data" / "raw" / "constituents" / "historical_index_weights.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    constituents_by_year = raw_data["constituents_by_year"]
    promotions = []

    for year in range(1994, 2025):
        prev_year = year - 1
        base_tickers = constituents_by_year.get(str(prev_year), constituents_by_year[str(year)])
        for q in (1, 2, 3):
            q_key = f"{year}-Q{q}"
            candidates = q_data.get(q_key, [])
            top10 = candidates[:10]
            for rank, c in enumerate(top10, 1):
                ticker = c["ticker"]
                if ticker in base_tickers:
                    start_rank = base_tickers.index(ticker) + 1
                    if start_rank > 10:
                        promotions.append({
                            "period": q_key,
                            "ticker": ticker,
                            "name": c["name"],
                            "start_rank": start_rank,
                            "q_rank": rank,
                            "weight": c["market_cap_weight"],
                            "from_expanded_tier": start_rank > 12,
                        })

    return promotions


def classify_promotions(promotions, gt_results):
    """Tag each promotion with whether the audited filing for that quarter agrees.

    A promotion is only evidence for the Top 20 expansion if the point-in-time filing
    shows the company genuinely in the Top 10. Promotions into quarters with no archived
    filing are UNVERIFIED; ones the filing contradicts are CONTRADICTED - artifacts of
    the drift model, not findings.

    Args:
        promotions: Promotion records from audit_midyear_promotions(), mutated in place.
        gt_results: Reconciliation output keyed by period.

    Returns:
        Dict of status -> count.
    """
    counts = {"CONFIRMED": 0, "CONTRADICTED": 0, "UNVERIFIED": 0}
    for promo in promotions:
        gt = gt_results.get(promo["period"])
        if gt is None or not gt.get("verified", False):
            promo["status"] = "UNVERIFIED"
        elif promo["ticker"] in gt["gt_tickers"]:
            promo["status"] = "CONFIRMED"
        else:
            promo["status"] = "CONTRADICTED"
        counts[promo["status"]] += 1
    return counts


def reconcile_with_ground_truth():
    """Compare simulated quarterly Top 10 against curated ground-truth holdings."""
    gt_path = REPO_ROOT / "data" / "raw" / "ground_truth" / "quarterly_ground_truth_holdings.json"
    with open(gt_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)
    with open(REPO_ROOT / "data" / "sp500_quarterly_constituents.json", "r", encoding="utf-8") as f:
        q_data = json.load(f)

    results = {}
    for period, p_val in gt_data["periods"].items():
        if isinstance(p_val, dict):
            gt_tickers = p_val.get("holdings", [])
            accession = p_val.get("accession_number", "N/A")
            form = p_val.get("form", "N/A")
        else:
            gt_tickers = p_val
            accession = "N/A"
            form = "N/A"

        candidates = q_data.get(period, [])
        sim_tickers = [c["ticker"] for c in candidates[:10]]
        is_verified = p_val.get("verified", True) if isinstance(p_val, dict) else True
        if not is_verified or not gt_tickers:
            results[period] = {
                "verified": False,
                "overlap_count": 0,
                "accuracy_pct": 0.0,
                "sim_tickers": sim_tickers,
                "gt_tickers": [],
                "missing_from_sim": [],
                "extra_in_sim": [],
                "accession": "N/A",
                "form": "Unverified",
                "note": p_val.get("note", "No point-in-time filing available for this quarter; unverified."),
            }
            continue

        overlap = set(sim_tickers) & set(gt_tickers)
        overlap_count = len(overlap)
        missing_from_sim = set(gt_tickers) - set(sim_tickers)
        extra_in_sim = set(sim_tickers) - set(gt_tickers)
        results[period] = {
            "verified": True,
            "overlap_count": overlap_count,
            "accuracy_pct": round(overlap_count / 10.0 * 100, 1),
            "sim_tickers": sim_tickers,
            "gt_tickers": gt_tickers,
            "missing_from_sim": sorted(list(missing_from_sim)),
            "extra_in_sim": sorted(list(extra_in_sim)),
            "accession": accession,
            "form": form,
        }
    return results


class TrueTop12DataLoader(DataLoader):
    """DataLoader wrapper that strictly isolates quarterly candidate drift to the prior December's base 12 companies."""

    def load_quarterly_universe(self, year: int, quarter: int, universe: str = "sp500") -> List[ConstituentSnapshot]:
        full_univ = super().load_quarterly_universe(year, quarter, universe=universe)
        if universe.lower() not in ("sp500",):
            return full_univ[:12]
        if quarter == 4:
            return full_univ[:12]
        prior_q4 = super().load_quarterly_universe(year - 1, 4, universe=universe)
        base_12_tickers = {s.ticker for s in prior_q4[:12]}
        return [s for s in full_univ if s.ticker in base_12_tickers]


def run_quarterly_side_by_side_comparison():
    """Run quarterly backtests comparing Top 12 baseline vs Top 20 expanded across selectors."""
    loader_top20 = DataLoader()
    loader_top12 = TrueTop12DataLoader()

    sim_top20 = PortfolioSimulator(data_loader=loader_top20)
    sim_top12 = PortfolioSimulator(data_loader=loader_top12)

    horizons = [
        (10, 2015, 2024),
        (20, 2005, 2024),
        (30, 1995, 2024),
    ]

    results = []

    # 1. MarketCapSelector
    sel_mc = MarketCapSelector()
    for n in (3, 5, 10):
        for h_label, start_yr, end_yr in horizons:
            # Top 12 baseline
            r12_pre = sim_top12.run_simulation(start_yr, end_yr, n=n, selector=sel_mc, universe="sp500", rebalance_frequency="quarterly", is_after_tax=False)
            r12_post = sim_top12.run_simulation(start_yr, end_yr, n=n, selector=sel_mc, universe="sp500", rebalance_frequency="quarterly", is_after_tax=True, tax_rate=0.30)
            
            # Top 20 expanded
            r20_pre = sim_top20.run_simulation(start_yr, end_yr, n=n, selector=sel_mc, universe="sp500", rebalance_frequency="quarterly", is_after_tax=False)
            r20_post = sim_top20.run_simulation(start_yr, end_yr, n=n, selector=sel_mc, universe="sp500", rebalance_frequency="quarterly", is_after_tax=True, tax_rate=0.30)

            results.append({
                "selector": "Market Cap",
                "strategy": f"Top {n}",
                "horizon": f"{h_label}y",
                "top12_pre": r12_pre.cagr * 100,
                "top20_pre": r20_pre.cagr * 100,
                "delta_pre": (r20_pre.cagr - r12_pre.cagr) * 100,
                "top12_post": r12_post.cagr * 100,
                "top20_post": r20_post.cagr * 100,
                "delta_post": (r20_post.cagr - r12_post.cagr) * 100,
            })

    # 2. PerformanceSelector
    for n in (3, 5, 10):
        sel_perf = PerformanceSelector(n=n)
        for h_label, start_yr, end_yr in horizons:
            r12_pre = sim_top12.run_simulation(start_yr, end_yr, n=n, selector=sel_perf, universe="sp500", rebalance_frequency="quarterly", is_after_tax=False)
            r12_post = sim_top12.run_simulation(start_yr, end_yr, n=n, selector=sel_perf, universe="sp500", rebalance_frequency="quarterly", is_after_tax=True, tax_rate=0.30)

            r20_pre = sim_top20.run_simulation(start_yr, end_yr, n=n, selector=sel_perf, universe="sp500", rebalance_frequency="quarterly", is_after_tax=False)
            r20_post = sim_top20.run_simulation(start_yr, end_yr, n=n, selector=sel_perf, universe="sp500", rebalance_frequency="quarterly", is_after_tax=True, tax_rate=0.30)

            results.append({
                "selector": "Performance",
                "strategy": f"Top {n}",
                "horizon": f"{h_label}y",
                "top12_pre": r12_pre.cagr * 100,
                "top20_pre": r20_pre.cagr * 100,
                "delta_pre": (r20_pre.cagr - r12_pre.cagr) * 100,
                "top12_post": r12_post.cagr * 100,
                "top20_post": r20_post.cagr * 100,
                "delta_post": (r20_post.cagr - r12_post.cagr) * 100,
            })

    return results


def main():
    print("=" * 85)
    print("          S&P 500 QUARTERLY TOP N REBALANCING AUDIT (ISSUE #26)")
    print("=" * 85)

    # 1. Mid-Year Promotions
    promotions = audit_midyear_promotions()
    expanded_tier_promotions = [p for p in promotions if p["from_expanded_tier"]]
    unique_expanded_companies = set(p["ticker"] for p in expanded_tier_promotions)
    
    print(f"\n[1] MID-YEAR PROMOTIONS INTO TOP 10 (1994-2024):")
    print(f"    Total mid-year promotion instances (company-quarters): {len(promotions)}")
    print(f"    Promotions originating from ranks #13-#20 (previously missed): {len(expanded_tier_promotions)}")
    print(f"    Unique companies promoted from ranks #13-#20: {len(unique_expanded_companies)} ({', '.join(sorted(unique_expanded_companies))})")
    status_counts = classify_promotions(
        expanded_tier_promotions, reconcile_with_ground_truth()
    )

    print(
        f"\n    Verified against audited filings: {status_counts['CONFIRMED']} confirmed, "
        f"{status_counts['CONTRADICTED']} contradicted, {status_counts['UNVERIFIED']} unverified "
        f"(no filing for that quarter)."
    )
    print("\n    Promotions enabled by Top 20 expansion:")
    for p in expanded_tier_promotions:
        print(
            f"      [{p['status']:<12}] {p['period']}: {p['ticker']:<5} ({p['name']:<25}) "
            f"jumped from #{p['start_rank']} -> #{p['q_rank']} (drifted weight: {p['weight']})"
        )
    contradicted = [p for p in expanded_tier_promotions if p["status"] == "CONTRADICTED"]
    if contradicted:
        print(
            "\n    NOTE: CONTRADICTED promotions are false positives of the drift model - the\n"
            "    audited filing for that quarter shows the company outside the true Top 10.\n"
            "    They must not be cited as evidence for the Top 20 expansion."
        )

    # 2. Ground-Truth Reconciliation
    gt_results = reconcile_with_ground_truth()
    verified_results = {k: v for k, v in gt_results.items() if v.get("verified", True)}
    total_verified = len(verified_results)
    avg_accuracy = sum(r["accuracy_pct"] for r in verified_results.values()) / total_verified if total_verified else 0.0
    xml_results = {k: v for k, v in verified_results.items() if v.get("form") == "NPORT-P"}
    xml_accuracy = sum(r["accuracy_pct"] for r in xml_results.values()) / len(xml_results) if xml_results else 0.0

    # Q4 2020-2023 are not independent checks: the year-end candidate lists are parsed
    # from those very filings, so they match 10/10 by construction. The out-of-sample
    # figure excludes them and is the one that actually measures the drift model.
    out_of_sample = {k: v for k, v in xml_results.items() if k not in CIRCULAR_Q4_PERIODS}
    oos_accuracy = (
        sum(r["accuracy_pct"] for r in out_of_sample.values()) / len(out_of_sample)
        if out_of_sample else 0.0
    )

    print(f"\n[2] GROUND-TRUTH RECONCILIATION AGAINST AUDITED SEC FILINGS:")
    print(f"    Audited sample periods: {total_verified} verified quarters ({len(gt_results) - total_verified} unverified periods labeled)")
    print(f"    Average Top 10 match accuracy (all {total_verified} verified quarters): {avg_accuracy:.1f}%")
    print(f"    Average Top 10 match accuracy ({len(xml_results)} modern Form NPORT-P XML quarters): {xml_accuracy:.1f}%")
    print(f"    OUT-OF-SAMPLE accuracy ({len(out_of_sample)} quarters, excluding the {len(CIRCULAR_Q4_PERIODS)} Q4 filings")
    print(f"      the year-end candidate lists are themselves parsed from): {oos_accuracy:.1f}%\n")
    print(f"    {'Period':<9} {'Match':<7} {'Acc':<7} {'SEC Accession':<23} {'Discrepancies / Status'}")
    print("    " + "-" * 80)
    for period, r in gt_results.items():
        if not r.get("verified", True):
            print(f"    {period:<9} {'--':<7} {'--':<7} {'[UNVERIFIED]':<23} {r.get('note', 'No point-in-time filing')}")
            continue
        disc = f"Missed: {r['missing_from_sim']}, Extra: {r['extra_in_sim']}" if r['missing_from_sim'] else "100% Exact Match"
        acc_str = f"{r['accession']}" if r['accession'] != "N/A" else "Audited Factsheet"
        print(f"    {period:<9} {r['overlap_count']}/10  {r['accuracy_pct']:>5.1f}%  {acc_str:<23} {disc}")

    # 3. Side-by-Side Comparison
    print(f"\n[3] QUARTERLY SIDE-BY-SIDE COMPARISON: TOP 12 BASELINE VS. TOP 20 EXPANDED:")
    print(f"    {'Selector':<12} {'Strategy':<8} {'Horiz':<6} {'Top 12 Pre':<12} {'Top 20 Pre':<12} {'Pre Delta':<11} {'Top 12 Post':<13} {'Top 20 Post':<13} {'Post Delta'}")
    print("    " + "-" * 95)
    side_by_side = run_quarterly_side_by_side_comparison()
    for row in side_by_side:
        p_delta = f"{row['delta_pre']:+.2f}%" if abs(row['delta_pre']) > 0.005 else "0.00%"
        a_delta = f"{row['delta_post']:+.2f}%" if abs(row['delta_post']) > 0.005 else "0.00%"
        print(f"    {row['selector']:<12} {row['strategy']:<8} {row['horizon']:<6} {row['top12_pre']:>8.2f}%    {row['top20_pre']:>8.2f}%    {p_delta:>9}   {row['top12_post']:>9.2f}%    {row['top20_post']:>9.2f}%    {a_delta:>10}")

    print("\n" + "=" * 85)
    print("Audit completed successfully.")
    print("=" * 85)


if __name__ == "__main__":
    main()
