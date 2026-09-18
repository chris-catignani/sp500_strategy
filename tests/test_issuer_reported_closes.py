"""Check every derived price series against the closes its registrant reported (issue #84).

A fund Schedule of Investments gives an implied price; the registrant's own Form 10-K
gives the high, low and quarter-end close for the same date. The split factor is the only
thing standing between the two, so disagreement localises to the factor. That is how
`T_CORP`'s missing three-for-two of 1999-04-15 was found (docs/DATA_PROVENANCE.md 4.3.9);
this generalises the check to every registrant the issuer tables reach.

Two checks, in increasing strength:

- **Band.** The derived price, expressed back in as-traded terms, must lie inside the
  registrant's own reported high/low for that quarter. Outside is impossible rather than
  merely unlikely -- the structural reject docs/SUBAGENTS.md argues for, needing no second
  source. Under a wrong split factor every comparison is out by the ratio.
- **Close.** Where the registrant also reported the quarter-end close, the two figures are
  compared directly. This is tighter than the band by an order of magnitude.
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

QUARTER_END = {"Q1": "-03-31", "Q2": "-06-30", "Q3": "-09-30", "Q4": "-12-31"}


def split_factor(record, as_of):
    """Divisor converting an as-traded price at as_of into final share terms."""
    factor = 1.0
    for split in (record or {}).get("splits", []):
        if split["effective_date"] > as_of:
            factor *= split["ratio"]
    return factor


class TestIssuerReportedCloses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(
            ROOT / "data" / "raw" / "ground_truth" / "issuer_dividend_tables.json",
            "r",
            encoding="utf-8",
        ) as f:
            cls.tables = json.load(f)["tickers"]
        with open(
            ROOT / "data" / "raw" / "corporate_actions" / "splits.json", "r", encoding="utf-8"
        ) as f:
            cls.splits = json.load(f)["splits_by_ticker"]
        with open(ROOT / "data" / "sp500_quarterly_prices.json", "r", encoding="utf-8") as f:
            cls.prices = json.load(f)

    def _comparable(self):
        """Every quarter where an issuer-reported band and a derived price both exist."""
        for ticker, body in sorted(self.tables.items()):
            series = self.prices.get(ticker, {})
            for period, quarter in sorted((body.get("quarters") or {}).items()):
                high, low = quarter.get("high"), quarter.get("low")
                derived = series.get(period)
                if high is None or low is None or derived is None:
                    continue
                year, label = period.split("-")
                factor = split_factor(self.splits.get(ticker), year + QUARTER_END[label])
                yield ticker, period, quarter, derived * factor

    def test_every_derived_price_lies_inside_its_registrants_reported_range(self):
        """The structural check: a close outside its own quarter's high/low is impossible.

        Covers 55 quarters across AN, BLS, DD, GTE and T_CORP -- every quarter for which
        the issuer tables carry a band and the derived series carries a price. A missing or
        wrong split record moves the derived price by the ratio, which no 1990s quarterly
        range is wide enough to absorb.
        """
        checked = 0
        for ticker, period, quarter, as_traded in self._comparable():
            with self.subTest(ticker=ticker, period=period):
                self.assertGreaterEqual(
                    as_traded,
                    quarter["low"],
                    f"{ticker} {period}: derived {as_traded:.4f} below the low "
                    f"{quarter['low']} reported in {quarter['accession_number']}",
                )
                self.assertLessEqual(
                    as_traded,
                    quarter["high"],
                    f"{ticker} {period}: derived {as_traded:.4f} above the high "
                    f"{quarter['high']} reported in {quarter['accession_number']}",
                )
            checked += 1
        # Pinned as a floor, not an equality: sourcing more filings should raise this
        # number without failing the test, which is the point of 4.3.15's coverage note.
        self.assertGreaterEqual(checked, 55, "issuer-reported bands lost coverage")

    def test_derived_prices_match_the_closes_the_registrants_themselves_reported(self):
        """The tighter check, where a registrant reported the quarter-end close itself.

        Fifteen comparisons across GTE and T_CORP. Thirteen agree to within 0.5% and ten
        to within 0.02%; the fund values at its own business day while the registrant
        quotes the composite tape close, which are not always the same session. T_CORP
        1994-Q2 is the widest at 1.874% and is recorded rather than tuned away
        (docs/DATA_PROVENANCE.md 4.3.9).
        """
        session_mismatch_tolerance = 0.03
        checked = 0
        tight = 0
        for ticker, period, quarter, as_traded in self._comparable():
            close = quarter.get("quarter_end_close")
            if close is None:
                continue
            with self.subTest(ticker=ticker, period=period):
                self.assertLess(
                    abs(as_traded / close - 1.0),
                    session_mismatch_tolerance,
                    f"{ticker} {period}: derived {as_traded:.4f} against reported close "
                    f"{close} in {quarter['accession_number']}",
                )
            checked += 1
            if abs(as_traded / close - 1.0) < 0.005:
                tight += 1
        self.assertGreaterEqual(checked, 15, "issuer-reported closes lost coverage")
        self.assertGreaterEqual(tight, 13, "close agreement degraded")

    def test_gte_carries_no_split_and_its_own_closes_say_so(self):
        """GTE's split record is `none_found`, and this is what makes that a finding.

        4.3.9 records that GTE's FY1999 Form 10-K contains no stock split for 1994-2000 and
        that the price series shows no halving. That is an argument from absence. GTE's own
        reported closes settle it positively: across twelve quarters of 1996-1999 the
        derived price reproduces the filed close at a factor of exactly one. A missing
        two-for-one would put every one of them out by half.
        """
        record = self.splits.get("GTE", {})
        self.assertEqual(record.get("splits"), [], "GTE gained a split record")
        compared = 0
        for ticker, period, quarter, as_traded in self._comparable():
            if ticker != "GTE" or quarter.get("quarter_end_close") is None:
                continue
            with self.subTest(period=period):
                self.assertLess(abs(as_traded / quarter["quarter_end_close"] - 1.0), 0.02)
            compared += 1
        self.assertEqual(compared, 12)

    def test_the_registrants_this_check_cannot_reach_are_named(self):
        """Coverage is five registrants of nineteen, and the shortfall is structural.

        The check needs an issuer-reported band, which needs Item 5 or the quarterly note
        to survive in the filing. For fourteen registrants no such table was recovered --
        mostly because a 1990s 10-K incorporates it by reference to a shareholder report
        filed separately (4.3.15). `RD` and `NT` are foreign private issuers filing 20-F
        and 40-F and were never expected to be reachable (#84). This asserts the shortfall
        rather than leaving it implicit, so recovering a registrant is a visible change.
        """
        reachable = {t for t, _, _, _ in self._comparable()}
        self.assertEqual(reachable, {"AN", "BLS", "DD", "GTE", "T_CORP"})
        unreachable = set(self.tables) - reachable
        self.assertIn("RD", unreachable)
        self.assertIn("NT", unreachable)
        self.assertEqual(len(unreachable), 14)


if __name__ == "__main__":
    unittest.main()


class TestDerivedDividendEffect(unittest.TestCase):
    """The size of the correction the sourced dividends make (issue #76).

    #76's sweeps bounded the effect of the missing dividends by injecting an assumed flat
    yield: at most 0.14pp on 30y quarterly Top 10, at a yield exceeding what any of these
    issuers paid. Now that the figures are sourced rather than assumed, the effect can be
    measured rather than bounded, and the claim worth pinning is not the value -- it is
    the shape of it. Dividends are income, so the corrected figure must be HIGHER, and the
    sweeps said it must be higher by a small amount.

    This runs the 30-year S&P 500 book twice, once against the built dividend series and
    once against the same series with the derived constituents' entries removed.

    **Scope: the market-cap path only.** `trailing_1y_return` is a total return, so under
    `PerformanceSelector` a sourced dividend changes the momentum *ranking* as well as the
    income, and that effect is larger and changes sign with frequency (4.3.18). "Positive
    at every depth" is true of the shipped default and is not a claim about momentum.
    """

    @classmethod
    def setUpClass(cls):
        from engine.backtest import PortfolioSimulator
        from engine.data_loader import DataLoader
        from engine.metrics import calculate_cagr
        from scripts.build_datasets_from_raw import DERIVED_NAMES

        cls.calculate_cagr = staticmethod(calculate_cagr)
        cls.with_dividends = PortfolioSimulator(DataLoader())

        # The comparison loader is stripped after construction rather than pointed at
        # edited files: DataLoader merges world_dividends.json over whatever annual path
        # it is given, and that file carries these tickers too, so overriding the S&P
        # paths alone leaves the series in place and the comparison reads as no change.
        stripped = DataLoader()
        for ticker in DERIVED_NAMES:
            stripped._raw_dividends.pop(ticker, None)
            stripped._raw_quarterly_dividends.pop(ticker, None)
        cls.without_dividends = PortfolioSimulator(stripped)

    def _cagr(self, simulator, n, frequency):
        from engine.selector import resolve_selector

        result = simulator.run_simulation(
            1994,
            2024,
            n=n,
            selector=resolve_selector("market_cap", n=n, weight_by="market_cap"),
            is_after_tax=False,
            initial_capital=10000.0,
            universe="sp500",
            rebalance_frequency=frequency,
        )
        return self.calculate_cagr(10000.0, result.final_equity, 30) * 100.0

    def test_sourcing_the_dividends_raises_the_thirty_year_figures(self):
        """Income can only add, and the addition must be visible at every depth."""
        for n in (3, 5, 10):
            for frequency in ("annual", "quarterly"):
                with self.subTest(n=n, frequency=frequency):
                    before = self._cagr(self.without_dividends, n, frequency)
                    after = self._cagr(self.with_dividends, n, frequency)
                    self.assertGreater(after, before)

    def test_the_effect_stays_inside_the_bound_the_issue_measured(self):
        """Under 0.1pp -- comfortably inside #76's 0.14pp over-bound.

        The bound matters more than the value. #63 attributed a decline of -0.19/-0.28/
        -0.68pp to survivorship; if sourcing the dividends moved the figures by anything
        near that, the attribution would be wrong rather than merely imprecise. Headroom
        is deliberate: a legitimate improvement in coverage should move the number without
        failing this.
        """
        widest = 0.0
        for n in (3, 5, 10):
            for frequency in ("annual", "quarterly"):
                delta = self._cagr(self.with_dividends, n, frequency) - self._cagr(
                    self.without_dividends, n, frequency
                )
                widest = max(widest, delta)
        self.assertLess(widest, 0.10)
        # And it is not nil: the series reaches constituents that are actually held.
        self.assertGreater(widest, 0.01)
