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
                if quarter.get("price_basis_restatement"):
                    # The filing restated these prices for a spin-off or split-off, which
                    # splits.json does not model, so the two sides are not on one basis
                    # and the comparison would be meaningless. AT&T's FY2001 report is
                    # the case; its dividends are unaffected and still used.
                    continue
                year, label = period.split("-")
                # A figure is stated in the share terms current at its FILING, which is
                # not always the quarter's own as-traded basis: a filing published after
                # a split restates the quarters before it. Lucent's fiscal tables do
                # exactly this. Both readings are admitted and the closer one is taken;
                # neither can absorb a wrong split ratio, which moves the price by half
                # or double.
                yield (
                    ticker,
                    period,
                    quarter,
                    derived * split_factor(self.splits.get(ticker), year + QUARTER_END[label]),
                    derived * split_factor(self.splits.get(ticker), quarter["filing_date"]),
                )

    def test_every_derived_price_lies_inside_its_registrants_reported_range(self):
        """The structural check: a close outside its own quarter's high/low is impossible.

        Covers 55 quarters across AN, BLS, DD, GTE and T_CORP -- every quarter for which
        the issuer tables carry a band and the derived series carries a price. A missing or
        wrong split record moves the derived price by the ratio, which no 1990s quarterly
        range is wide enough to absorb.
        """
        checked = 0
        for ticker, period, quarter, as_quarter, as_filed in self._comparable():
            low, high = quarter["low"], quarter["high"]
            with self.subTest(ticker=ticker, period=period):
                self.assertTrue(
                    low <= as_quarter <= high or low <= as_filed <= high,
                    f"{ticker} {period}: derived reads {as_quarter:.4f} in the quarter's "
                    f"own terms and {as_filed:.4f} in the filing's, neither inside the "
                    f"[{low}, {high}] range reported in {quarter['accession_number']}",
                )
            checked += 1
        # Pinned as a floor, not an equality: sourcing more filings should raise this
        # number without failing the test, which is the point of 4.3.15's coverage note.
        self.assertGreaterEqual(checked, 93, "issuer-reported bands lost coverage")

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
        for ticker, period, quarter, as_quarter, as_filed in self._comparable():
            close = quarter.get("quarter_end_close")
            if close is None:
                continue
            gap = min(abs(as_quarter / close - 1.0), abs(as_filed / close - 1.0))
            with self.subTest(ticker=ticker, period=period):
                self.assertLess(
                    gap,
                    session_mismatch_tolerance,
                    f"{ticker} {period}: derived {as_quarter:.4f}/{as_filed:.4f} against "
                    f"reported close {close} in {quarter['accession_number']}",
                )
            checked += 1
            if gap < 0.005:
                tight += 1
        self.assertGreaterEqual(checked, 42, "issuer-reported closes lost coverage")
        self.assertGreaterEqual(tight, 38, "close agreement degraded")

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
        for ticker, period, quarter, as_quarter, _ in self._comparable():
            if ticker != "GTE" or quarter.get("quarter_end_close") is None:
                continue
            with self.subTest(period=period):
                self.assertLess(abs(as_quarter / quarter["quarter_end_close"] - 1.0), 0.02)
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
        reachable = {t for t, _, _, _, _ in self._comparable()}
        self.assertEqual(reachable, {"AN", "BLS", "DD", "GTE", "LU", "T_CORP"})
        unreachable = set(self.tables) - reachable
        self.assertIn("RD", unreachable)
        self.assertIn("NT", unreachable)
        self.assertEqual(len(unreachable), 13)


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


class TestSplitCompleteness(unittest.TestCase):
    """Two filings reporting one quarter disagree by exactly the corporate action between.

    This is the check #84 actually needed, and the band check above is not it. A band is
    compared at its own date, where the recorded factor divides out of the derived price
    and multiplies back in -- so a split MISSING from `splits.json` cancels and the band
    still passes. BellSouth's missing 1995 two-for-one passed its 1994 and 1996 bands for
    exactly that reason (docs/DATA_PROVENANCE.md 4.3.20).

    Comparing one period across two filings has no such blind spot. The later filing
    restates the period for every corporate action since the earlier one, so the ratio
    between them IS the product of those actions, and it can be tested against the record
    without a second source.

    The discriminator against a mis-read cell is that a corporate action rescales **every**
    per-share figure by the same factor. A wrong-cell read disagrees with itself across
    fields; a split does not. So a pair counts only where at least two of dividend, high,
    low and close agree on the ratio to within 1%.
    """

    FIELDS = ("dividend_declared_per_share", "high", "low", "quarter_end_close")

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

    @staticmethod
    def _expected(records, ticker, earlier, later):
        ratio = 1.0
        for split in (records.get(ticker) or {}).get("splits", []):
            if earlier < split["effective_date"] <= later:
                ratio *= split["ratio"]
        return ratio

    def _pairs(self):
        """Self-consistent cross-filing views of one period: (ticker, period, a, b, ratio)."""
        for ticker, body in sorted(self.tables.items()):
            for period, views in sorted((body.get("observations_by_filing") or {}).items()):
                for index in range(len(views) - 1):
                    a, b = views[index], views[index + 1]
                    if a["filing_date"] == b["filing_date"]:
                        continue
                    ratios = [a[f] / b[f] for f in self.FIELDS if a.get(f) and b.get(f)]
                    if len(ratios) < 2 or max(ratios) / min(ratios) - 1 > 0.01:
                        continue
                    yield ticker, period, a, b, sum(ratios) / len(ratios)

    def test_every_cross_filing_disagreement_is_explained_by_a_recorded_split(self):
        """The split record is complete for every registrant this dataset reaches."""
        checked = 0
        for ticker, period, a, b, observed in self._pairs():
            checked += 1
            expected = self._expected(self.splits, ticker, a["filing_date"], b["filing_date"])
            with self.subTest(ticker=ticker, period=period):
                self.assertLess(
                    abs(observed / expected - 1.0),
                    0.02,
                    f"{ticker} {period}: filings {a['filing_date']} and {b['filing_date']} "
                    f"disagree by {observed:.4f}, but splits.json records {expected:.4f} "
                    f"between them. A corporate action is missing or wrong.",
                )
        # A floor, not an equality: more sourcing should raise this.
        self.assertGreaterEqual(checked, 150, "cross-filing coverage regressed")

    def test_the_check_fires_when_a_known_split_is_removed(self):
        """A test that cannot fail proves nothing, so this removes a split and checks it.

        BellSouth's 1995 two-for-one is the one this check found. Dropping it from the
        record must make the 1993 and 1994 quarters disagree at a ratio of two.
        """
        control = json.loads(json.dumps(self.splits))
        control["BLS"]["splits"] = [
            s for s in control["BLS"]["splits"] if s["effective_date"] != "1995-11-08"
        ]
        fired = [
            (ticker, period, observed)
            for ticker, period, a, b, observed in self._pairs()
            if abs(observed / self._expected(control, ticker, a["filing_date"], b["filing_date"]) - 1.0) > 0.02
        ]
        self.assertTrue(fired, "removing a real split did not trip the check")
        self.assertTrue(all(t == "BLS" for t, _, _ in fired))
        for _, _, observed in fired:
            self.assertAlmostEqual(observed, 2.0, delta=0.01)


class TestAlphabetConsolidationEffect(unittest.TestCase):
    """Alphabet's two share classes are one issuer, and one issuer holds one slot (#45).

    The audited December-31 rosters (4.3.10) file Alphabet as two positions from 2014
    onward. `_apply_audited_rosters` used to take the larger line and drop the other,
    which halves the issuer and drops it in the ranking -- Alphabet came out at rank 20
    in 2014 on its Class A weight alone, against rank 4 consolidated.

    Two claims are pinned here, and neither is a cell value:

    1. Wherever a filing reports two classes, the dataset's weight is their sum.
    2. Consolidation puts Alphabet in Top N books it was otherwise excluded from, and
       every affected S&P 500 cell moves down. The direction is the point: Alphabet
       displaces a name that did better over these spans, so correcting the weight
       *lowers* the published figures rather than flattering them.
    """

    ROSTER_YEARS = ("2014", "2015", "2016", "2017", "2018", "2019")

    @classmethod
    def setUpClass(cls):
        import json as _json
        import re as _re
        from pathlib import Path as _Path

        root = _Path(__file__).resolve().parent.parent
        raw = root / "data" / "raw"
        with open(raw / "ground_truth" / "vanguard_audited_rosters.json", encoding="utf-8") as f:
            cls.rosters = _json.load(f)["rosters_by_year"]
        with open(raw / "constituents" / "issuer_ticker_map.json", encoding="utf-8") as f:
            cls.issuer_map = {
                _re.sub(r"^[#*^\s]+", "", k).strip().rstrip(".").strip(): v
                for k, v in _json.load(f)["map"].items()
            }
        with open(root / "data" / "sp500_constituents.json", encoding="utf-8") as f:
            cls.constituents = _json.load(f)
        cls._re = _re

    def _roster_lines(self, year):
        """Every mapped (ticker, weight) line in a year's roster, duplicates kept."""
        out = []
        for holding in self.rosters[year]["holdings"]:
            if holding.get("unidentified"):
                continue
            name = self._re.sub(r"^[#*^\s]+", "", holding["name"]).strip().rstrip(".").strip()
            ticker = self.issuer_map.get(name)
            if ticker is not None:
                out.append((ticker, holding["weight"]))
        return out

    def test_a_dual_class_issuer_holds_one_slot_at_the_sum_of_its_classes(self):
        """The consolidation rule of 4.3.8, checked against the filing it reads from."""
        checked = 0
        for year in self.ROSTER_YEARS:
            lines = self._roster_lines(year)
            summed = {}
            for ticker, weight in lines:
                summed[ticker] = summed.get(ticker, 0.0) + weight
            duplicated = {t for t, _ in lines if sum(1 for u, _ in lines if u == t) > 1}
            self.assertIn(
                "GOOGL", duplicated, f"{year}: the filing should report two Alphabet classes"
            )

            published = self.constituents[year]
            for ticker in duplicated:
                rows = [r for r in published if r["ticker"] == ticker]
                if not rows:
                    continue
                self.assertEqual(
                    len(rows), 1, f"{year}: {ticker} occupies two slots in one book"
                )
                self.assertAlmostEqual(
                    rows[0]["market_cap_weight"], summed[ticker], places=5,
                    msg=f"{year}: {ticker} is not the sum of its share classes",
                )
                # A consolidation that did not roughly double the line would mean the
                # second class was dropped rather than added.
                largest = max(w for t, w in lines if t == ticker)
                self.assertGreater(rows[0]["market_cap_weight"] / largest, 1.9, year)
                checked += 1
        self.assertEqual(checked, len(self.ROSTER_YEARS))

    def test_consolidation_moves_alphabet_into_books_it_was_excluded_from(self):
        """The selection change #45 predicted, measured on the built rosters."""
        moved = 0
        for year in self.ROSTER_YEARS:
            lines = self._roster_lines(year)
            # Reconstruct the pre-#45 rule: first occurrence wins, the other class is
            # dropped. This is the comparison the claim above is made against.
            unconsolidated, seen = [], set()
            for ticker, weight in lines:
                if ticker in seen:
                    continue
                seen.add(ticker)
                unconsolidated.append((ticker, weight))
            old_rank = [t for t, _ in unconsolidated[:20]].index("GOOGL") + 1
            new_rank = [r["ticker"] for r in self.constituents[year]].index("GOOGL") + 1
            self.assertLess(
                new_rank, old_rank,
                f"{year}: consolidation must raise Alphabet's rank, not lower it",
            )
            if old_rank > 5 >= new_rank or old_rank > 3 >= new_rank:
                moved += 1
        # Not every year crosses a Top N boundary, but most do, and that is the whole
        # impact this issue was opened about.
        self.assertGreaterEqual(moved, 4)

    def test_consolidating_alphabet_lowers_the_top_3_book(self):
        """Top 3 is where Alphabet's entry is decisive, and it is decisive downward.

        This compares like with like: the same audited rosters read twice, once under the
        rule that dropped the second share class and once under the rule that sums it.

        **The claim is deliberately narrow.** At Top 5 and Top 10 the sign is mixed --
        raising Alphabet's rank displaces a different name at each depth, and at Top 5
        consolidation happens to *raise* the figures. Asserting "lowers everywhere" would
        pin a coincidence. Top 3 is the book Alphabet enters in every corrected year, so
        it is the one where the effect is structural rather than incidental.

        The before/after table in 4.3.21 measures something else again -- the rosters
        against the factsheet anchors they replaced -- and is published as a record of
        this change rather than as a standing invariant.

        **Market-cap path only**, as with `TestDerivedDividendEffect`.
        """
        from engine.backtest import PortfolioSimulator
        from engine.data_loader import DataLoader
        from engine.metrics import calculate_cagr
        from engine.selector import resolve_selector

        consolidated = DataLoader()
        single_class = DataLoader()

        for year in self.ROSTER_YEARS:
            keep, seen = [], set()
            for ticker, weight in self._roster_lines(year):
                if ticker in seen:
                    continue
                seen.add(ticker)
                keep.append((ticker, weight))

            known = {r["ticker"]: r for r in single_class._raw_constituents[year]}
            rebuilt = []
            for ticker, weight in keep:
                try:
                    single_class.get_price(ticker, int(year))
                except (KeyError, ValueError):
                    continue
                row = dict(known.get(ticker, {"ticker": ticker, "name": ticker,
                                              "trailing_1y_return": 0.0, "year": int(year)}))
                row["market_cap_weight"] = weight
                rebuilt.append(row)
                if len(rebuilt) == 20:
                    break
            self.assertEqual(len(rebuilt), 20, f"{year}: single-class roster is short")
            rebuilt.sort(key=lambda r: -r["market_cap_weight"])
            single_class._raw_constituents[year] = rebuilt

        def cagr(simulator, start_year, end_year):
            result = simulator.run_simulation(
                start_year, end_year, n=3,
                selector=resolve_selector("market_cap", n=3, weight_by="market_cap"),
                is_after_tax=False, initial_capital=10000.0,
                universe="sp500", rebalance_frequency="annual",
            )
            return calculate_cagr(10000.0, result.final_equity, end_year - start_year) * 100.0

        for start_year, end_year in ((2014, 2024), (2004, 2024), (1994, 2024)):
            with self.subTest(horizon=end_year - start_year):
                before = cagr(PortfolioSimulator(single_class), start_year, end_year)
                after = cagr(PortfolioSimulator(consolidated), start_year, end_year)
                self.assertLess(
                    after, before,
                    "consolidating Alphabet is expected to lower the Top 3 book; if it no "
                    "longer does, the reading in 4.3.21 is stale",
                )
