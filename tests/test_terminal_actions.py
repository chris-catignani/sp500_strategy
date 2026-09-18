"""Terminal value for constituents that stop trading mid-horizon (issue #56).

Three layers are covered here:

- the **dataset** layer, where index-removal dates are enforced beside inclusion dates
  and the compiled terminal-action records are built;
- the **engine** layer, driven by synthetic fixtures rather than the shipped datasets,
  because no shipped configuration holds a constituent through a terminal action -- the
  paths would otherwise be untested code;
- the **universe invariant** that #37 calls the most valuable artifact of the work: every
  Top-20 position in an archived filing has a price series traceable to a source.
"""

import json
import re
import tempfile
import unittest
from pathlib import Path

from engine.backtest import PortfolioSimulator
from engine.data_loader import DataLoader
from engine.tax_lots import FIFOTaxLotManager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"

QUARTER_END_DATES = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}


def _period_end_date(period: str) -> str:
    """Return the calendar date a price observation key falls on."""
    if "-Q" in period:
        year, quarter = period.split("-Q")
        return f"{year}-{QUARTER_END_DATES[int(quarter)]}"
    return f"{period}-12-31"


class TestRemovalDatesEnforced(unittest.TestCase):
    """Index removal is enforced in the dataset layer, beside inclusion (4.3.4)."""

    @classmethod
    def setUpClass(cls):
        with open(RAW_DIR / "corporate_actions" / "terminal_actions.json", encoding="utf-8") as f:
            cls.raw_actions = json.load(f)["actions_by_ticker"]
        cls.removal_dates = {t: a["effective_date"] for t, a in cls.raw_actions.items()}

    def test_removal_dates_are_read_from_the_sourced_dataset(self):
        """The filter's dates are the filings' dates, not a second hand-kept list.

        A copy would be free to drift from the record it was copied out of, and nothing
        would report that it had.
        """
        from scripts.build_datasets_from_raw import EFFECTIVE_REMOVAL_DATES

        self.assertEqual(EFFECTIVE_REMOVAL_DATES, self.removal_dates)
        self.assertEqual(len(EFFECTIVE_REMOVAL_DATES), 13)

    def test_no_constituent_is_selectable_after_its_removal_date(self):
        """No roster, annual or quarterly, offers a constituent that had stopped trading."""
        for name, path, to_date in (
            ("annual", DATA_DIR / "sp500_constituents.json", lambda k: f"{k}-12-31"),
            ("quarterly", DATA_DIR / "sp500_quarterly_constituents.json", _period_end_date),
            ("world", DATA_DIR / "world_constituents.json", lambda k: f"{k}-12-31"),
            (
                "world quarterly",
                DATA_DIR / "world_quarterly_constituents.json",
                _period_end_date,
            ),
        ):
            with open(path, encoding="utf-8") as f:
                rosters = json.load(f)
            for period, entries in rosters.items():
                period_date = to_date(period)
                for entry in entries:
                    removal = self.removal_dates.get(entry["ticker"])
                    if removal is not None:
                        self.assertLessEqual(
                            period_date,
                            removal,
                            f"{name}: {entry['ticker']} is selectable at {period}, after it "
                            f"stopped trading on {removal}",
                        )

    def test_no_price_is_published_after_a_removal_date(self):
        """A price asserts the named security traded at that value on that date.

        Three observations fail that test and are withheld: BellSouth at 2006-12-31, two
        days after its merger closed, and Tyco International at 2007-Q3 and 2008-Q3, which
        are a continuing company that kept the ticker.
        """
        for name, path, to_date in (
            ("annual", DATA_DIR / "sp500_prices.json", lambda k: f"{k}-12-31"),
            ("quarterly", DATA_DIR / "sp500_quarterly_prices.json", _period_end_date),
            ("world", DATA_DIR / "world_prices.json", lambda k: f"{k}-12-31"),
            ("world quarterly", DATA_DIR / "world_quarterly_prices.json", _period_end_date),
        ):
            with open(path, encoding="utf-8") as f:
                prices = json.load(f)
            for ticker, removal in self.removal_dates.items():
                for period in prices.get(ticker, {}):
                    self.assertLessEqual(
                        to_date(period),
                        removal,
                        f"{name}: {ticker} carries a price at {period}, after it stopped "
                        f"trading on {removal}",
                    )

    def test_every_withheld_observation_is_recorded_rather_than_dropped(self):
        """What was withheld stays visible, so the suppression can be audited."""
        with open(DATA_DIR / "terminal_actions.json", encoding="utf-8") as f:
            compiled = json.load(f)

        withheld = {
            (ticker, frequency, period): value
            for ticker, record in compiled.items()
            for frequency in ("annual", "quarterly")
            for period, value in record[frequency]["withheld_observations"].items()
        }
        self.assertEqual(
            withheld,
            {
                ("BLS", "annual", "2006"): 47.11,
                ("BLS", "quarterly", "2006-Q4"): 47.11,
                ("TYC", "quarterly", "2007-Q3"): 44.34,
                ("TYC", "quarterly", "2008-Q3"): 35.02,
            },
        )


class TestCompiledTerminalActions(unittest.TestCase):
    """The record the engine reads says what the holder received, and on what basis."""

    @classmethod
    def setUpClass(cls):
        with open(DATA_DIR / "terminal_actions.json", encoding="utf-8") as f:
            cls.compiled = json.load(f)
        with open(RAW_DIR / "corporate_actions" / "terminal_actions.json", encoding="utf-8") as f:
            cls.raw = json.load(f)["actions_by_ticker"]

    def test_every_figure_traces_to_the_sourced_record(self):
        """Nothing in the compiled dataset is a restatement of a sourced figure."""
        self.assertEqual(set(self.compiled), set(self.raw))
        for ticker, record in self.compiled.items():
            source = self.raw[ticker]
            for field in (
                "effective_date",
                "consideration_type",
                "cash_per_share",
                "stock_exchange_ratio",
                "acquirer_ticker",
                "accession_number",
            ):
                self.assertEqual(record[field], source[field], f"{ticker}.{field}")

    def test_the_period_is_derived_from_the_effective_date(self):
        for ticker, record in self.compiled.items():
            effective = record["effective_date"]
            self.assertEqual(record["year"], int(effective[:4]), ticker)
            self.assertEqual(record["quarter"], (int(effective[5:7]) - 1) // 3 + 1, ticker)

    def test_only_a_stock_leg_carries_a_derived_value(self):
        """A stated cash consideration is the terminal value; nothing is derived beside it.

        Publishing a second figure next to $13.75 would put a number where a reader
        expects what Dell's holders received, and it would not be that.
        """
        for ticker, record in self.compiled.items():
            has_stock_leg = record["consideration_type"] in ("stock", "cash_and_stock")
            for frequency in ("annual", "quarterly"):
                block = record[frequency]
                if has_stock_leg:
                    self.assertIsNotNone(
                        block["stock_leg_value_per_share"], f"{ticker} {frequency}"
                    )
                    self.assertIn(
                        block["stock_leg_value_basis"],
                        ("filing_observed", "last_observed_price"),
                    )
                else:
                    self.assertIsNone(block["stock_leg_value_per_share"], f"{ticker} {frequency}")
                    self.assertIsNone(block["stock_leg_value_basis"], f"{ticker} {frequency}")

    def test_a_derived_value_never_postdates_the_action_it_values(self):
        """Except where a filing within days of the effective date reports the outcome."""
        for ticker, record in self.compiled.items():
            effective = record["effective_date"]
            for frequency in ("annual", "quarterly"):
                block = record[frequency]
                if block["source_period"] is None:
                    continue
                observed = _period_end_date(block["source_period"])
                if block["stock_leg_value_basis"] == "last_observed_price":
                    self.assertLessEqual(observed, effective, f"{ticker} {frequency}")
                else:
                    self.assertGreater(observed, effective, f"{ticker} {frequency}")

    def test_bellsouth_is_valued_at_what_the_schedule_reported_two_days_later(self):
        """Vanguard's 2006-12-31 schedule holds BellSouth after the merger closed.

        It lists AT&T Inc. at 35,821,382 shares / $1,280,614 thousand and BellSouth at
        17,002,851 / $801,004, so $35.75 and $47.11. At the filing's own exchange ratio
        1.325 x $35.75 is $47.37 -- the two readings of that row, the position's final
        value and the value of what it converted into, agree to within 0.6%. Either way
        the figure is a terminal value read from an audited schedule, and it is nine
        months fresher than the last price at which BellSouth genuinely traded.
        """
        block = self.compiled["BLS"]["annual"]
        self.assertEqual(block["stock_leg_value_basis"], "filing_observed")
        self.assertAlmostEqual(block["stock_leg_value_per_share"], 47.11)

        ratio = self.compiled["BLS"]["stock_exchange_ratio"]
        with open(RAW_DIR / "ground_truth" / "vanguard_audited_rosters.json", encoding="utf-8") as f:
            holdings = json.load(f)["rosters_by_year"]["2006"]["holdings"]
        att = next(h for h in holdings if h["name"].startswith("AT&T Inc"))
        implied = ratio * (att["value_usd_thousands"] * 1000.0 / att["shares"])
        self.assertLess(abs(implied - block["stock_leg_value_per_share"]) / implied, 0.006)

    def test_tycos_post_separation_prices_are_not_mistaken_for_consideration(self):
        """Nine months is not "within days", so the window rejects them.

        Tyco International kept trading after separating, so those observations are a
        different company under a recycled ticker -- the hazard 4.3.12 exists to name.
        """
        for frequency in ("annual", "quarterly"):
            block = self.compiled["TYC"][frequency]
            self.assertEqual(block["stock_leg_value_basis"], "last_observed_price")
            self.assertEqual(block["source_period"], "2006" if frequency == "annual" else "2006-Q4")

    def test_share_terms_need_no_conversion(self):
        """Cash amounts and exchange ratios apply to held shares directly.

        Each derived series is adjusted to its own final observation (4.3.9), so this
        holds only while every split on record precedes that observation -- otherwise a
        held share would not be an as-traded share on the effective date, and every
        consideration figure the engine applies would be out by the split.
        """
        with open(RAW_DIR / "corporate_actions" / "splits.json", encoding="utf-8") as f:
            splits = json.load(f)["splits_by_ticker"]
        with open(
            RAW_DIR / "ground_truth" / "derived_constituent_series.json", encoding="utf-8"
        ) as f:
            series = json.load(f)["series_by_ticker"]

        for ticker in self.compiled:
            observations = series.get(ticker)
            self.assertTrue(observations, f"{ticker} has no derived series")
            final_observation = f"{max(observations)}-12-31"
            for event in splits.get(ticker, {}).get("splits", []):
                self.assertLessEqual(
                    event["effective_date"],
                    final_observation,
                    f"{ticker} splits after its final observation, so its held share count "
                    "is not in as-traded terms on the effective date",
                )


class TestSection368And356(unittest.TestCase):
    """FIFO handling through a reorganisation."""

    def setUp(self):
        self.manager = FIFOTaxLotManager()

    def test_exchange_carries_basis_forward_and_realises_nothing(self):
        self.manager.add_lot("GTE", shares=100.0, price=30.0, year=1995)
        basis_before = self.manager.total_cost_basis()

        created = self.manager.exchange_lots("GTE", "VZ", share_multiplier=1.22)

        self.assertAlmostEqual(created, 122.0)
        self.assertAlmostEqual(self.manager.get_position_shares("VZ"), 122.0)
        self.assertAlmostEqual(self.manager.get_position_shares("GTE"), 0.0)
        self.assertNotIn("GTE", self.manager.get_all_positions())
        self.assertAlmostEqual(self.manager.total_cost_basis(), basis_before)
        self.assertAlmostEqual(self.manager.current_annual_realized_gain, 0.0)

    def test_exchange_preserves_fifo_order_and_purchase_dates(self):
        """A lot bought before the reorganisation still depletes before one bought after."""
        self.manager.add_lot("GTE", shares=10.0, price=10.0, year=1994)
        self.manager.add_lot("GTE", shares=10.0, price=50.0, year=1996)
        self.manager.exchange_lots("GTE", "VZ", share_multiplier=2.0)

        lots = self.manager.get_lots("VZ")
        self.assertEqual([lot.purchase_year for lot in lots], [1994, 1996])
        self.assertAlmostEqual(lots[0].shares, 20.0)
        self.assertAlmostEqual(lots[0].purchase_price, 5.0)
        self.assertAlmostEqual(lots[1].purchase_price, 25.0)

        # Selling 20 shares takes the 1994 lot, at its carried-forward basis of $5.
        gain, _ = self.manager.sell_shares("VZ", 20.0, 8.0, 2000)
        self.assertAlmostEqual(gain, 20.0 * (8.0 - 5.0))

    def test_exchange_into_a_ticker_already_held_keeps_fifo_by_purchase_date(self):
        """The surrendered shares keep their purchase date, so they keep their place.

        AT&T Corp converted into AT&T Inc., which a portfolio may already hold. Appending
        the arriving lots would put 1994 shares behind 2003 ones and deplete them last.
        """
        self.manager.add_lot("T", shares=10.0, price=30.0, year=2003)
        self.manager.add_lot("T_CORP", shares=10.0, price=10.0, year=1994)

        self.manager.exchange_lots("T_CORP", "T", share_multiplier=1.0)

        lots = self.manager.get_lots("T")
        self.assertEqual([lot.purchase_year for lot in lots], [1994, 2003])
        # Selling 10 shares takes the 1994 lot, at its carried-forward basis of $10.
        gain, _ = self.manager.sell_shares("T", 10.0, 20.0, 2006)
        self.assertAlmostEqual(gain, 100.0)

    def test_exchange_rejects_a_non_positive_multiplier_and_a_self_exchange(self):
        self.manager.add_lot("GTE", shares=10.0, price=10.0, year=1994)
        with self.assertRaises(ValueError):
            self.manager.exchange_lots("GTE", "VZ", share_multiplier=0.0)
        with self.assertRaises(ValueError):
            self.manager.exchange_lots("GTE", "GTE", share_multiplier=2.0)

    def test_boot_recognises_gain_only_up_to_the_cash_received(self):
        """Section 356: recognised gain is capped by the cash, not by the whole gain."""
        self.manager.add_lot("T_CORP", shares=100.0, price=10.0, year=1994)

        # Realised gain is 100 * (1.30 + 19.06) - 1000 = 1036; cash is only 130.
        recognized = self.manager.recognize_boot(
            "T_CORP", cash_per_share=1.30, stock_value_per_share=19.06, current_year=2005
        )
        self.assertAlmostEqual(recognized, 130.0)
        self.assertAlmostEqual(self.manager.current_annual_realized_gain, 130.0)
        # Basis: 1000 - 130 cash + 130 recognised = 1000, unchanged here.
        self.assertAlmostEqual(self.manager.total_cost_basis(), 1000.0)

    def test_boot_recognises_no_loss(self):
        """A position standing at a loss recognises nothing, and keeps its basis less cash."""
        self.manager.add_lot("T_CORP", shares=100.0, price=50.0, year=1994)

        recognized = self.manager.recognize_boot(
            "T_CORP", cash_per_share=1.30, stock_value_per_share=19.06, current_year=2005
        )
        self.assertAlmostEqual(recognized, 0.0)
        self.assertAlmostEqual(self.manager.total_cost_basis(), 5000.0 - 130.0)

    def test_boot_is_recognised_per_lot_rather_than_netted(self):
        """A losing lot does not shelter a winning one inside the same reorganisation."""
        self.manager.add_lot("T_CORP", shares=100.0, price=1.0, year=1994)  # large gain
        self.manager.add_lot("T_CORP", shares=100.0, price=90.0, year=2000)  # large loss

        recognized = self.manager.recognize_boot(
            "T_CORP", cash_per_share=1.30, stock_value_per_share=19.06, current_year=2005
        )
        # Winning lot recognises its cash of $130; losing lot recognises nothing.
        self.assertAlmostEqual(recognized, 130.0)

    def test_boot_capped_by_a_realised_gain_smaller_than_the_cash(self):
        self.manager.add_lot("EMC", shares=100.0, price=37.0, year=2000)
        # Realised gain is 100 * (24.05 + 13.20) - 3700 = 25; cash is 2405.
        recognized = self.manager.recognize_boot(
            "EMC", cash_per_share=24.05, stock_value_per_share=13.20, current_year=2016
        )
        self.assertAlmostEqual(recognized, 25.0)


class TerminalFixture:
    """A two-ticker universe on disk, so the engine's terminal paths can be driven.

    No shipped configuration reaches a terminal action -- a constituent falls out of the
    Top N long before it stops trading -- so testing these paths against the real datasets
    would assert nothing about them.
    """

    def __init__(self, tmpdir: str, action: dict, acquirer_priced: bool = True):
        root = Path(tmpdir)
        years = [str(y) for y in range(2000, 2004)]

        # DYING is the largest constituent in 2000 and absent from every later roster.
        constituents = {}
        for year in years:
            entries = [
                {
                    "ticker": "SAFE",
                    "name": "Safe Corp.",
                    "market_cap_weight": 1.0,
                    "trailing_1y_return": 0.1,
                    "year": int(year),
                },
                # A second survivor, so the roster still fills a Top 2 once DYING leaves
                # it and the selector has no reason to warn about a short universe.
                {
                    "ticker": "SAFE2",
                    "name": "Safe Two Corp.",
                    "market_cap_weight": 0.5,
                    "trailing_1y_return": 0.1,
                    "year": int(year),
                },
            ]
            if year == "2000":
                entries.insert(
                    0,
                    {
                        "ticker": "DYING",
                        "name": "Dying Corp.",
                        "market_cap_weight": 1.0,
                        "trailing_1y_return": 0.1,
                        "year": int(year),
                    },
                )
            constituents[year] = entries

        prices = {
            "SAFE": {y: 100.0 for y in years},
            "SAFE2": {y: 80.0 for y in years},
            # Priced up to its final year end, and no further: the removal filter
            # withholds observations dated after the effective date, and nothing before.
            "DYING": {"2000": 50.0},
            "^GSPC": {y: 1000.0 for y in years},
            "^SP500TR": {y: 1000.0 for y in years},
        }
        if acquirer_priced:
            prices["ACQ"] = {y: 20.0 for y in years}

        quarterly_prices = {
            ticker: {f"{y}-Q{q}": p for y, p in series.items() for q in (1, 2, 3, 4)}
            for ticker, series in prices.items()
        }
        # DYING trades on into the quarter its action falls in, and stops there.
        quarterly_prices["DYING"]["2001-Q1"] = 50.0
        quarterly_prices["DYING"]["2001-Q2"] = 50.0
        quarterly_constituents = {
            f"{y}-Q{q}": [dict(e, quarter=q) for e in entries]
            for y, entries in constituents.items()
            for q in (1, 2, 3, 4)
        }

        self.paths = {}
        for name, payload in (
            ("sp500_constituents.json", constituents),
            ("sp500_prices.json", prices),
            ("sp500_dividends.json", {t: {} for t in prices}),
            ("sp500_quarterly_constituents.json", quarterly_constituents),
            ("sp500_quarterly_prices.json", quarterly_prices),
            ("sp500_quarterly_dividends.json", {t: {} for t in prices}),
            ("terminal_actions.json", {"DYING": action}),
        ):
            path = root / name
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            self.paths[name] = path

    def loader(self) -> DataLoader:
        return DataLoader(
            constituents_path=self.paths["sp500_constituents.json"],
            prices_path=self.paths["sp500_prices.json"],
            dividends_path=self.paths["sp500_dividends.json"],
            quarterly_constituents_path=self.paths["sp500_quarterly_constituents.json"],
            quarterly_prices_path=self.paths["sp500_quarterly_prices.json"],
            quarterly_dividends_path=self.paths["sp500_quarterly_dividends.json"],
            spinoffs_path=self.paths["terminal_actions.json"].parent / "no_spinoffs.json",
            terminal_actions_path=self.paths["terminal_actions.json"],
        )


def _action(consideration_type, **overrides):
    """A 2001 terminal action for DYING, defaulting to no consideration at all."""
    record = {
        "effective_date": "2001-06-30",
        "year": 2001,
        "quarter": 2,
        "consideration_type": consideration_type,
        "cash_per_share": None,
        "stock_exchange_ratio": None,
        "acquirer_ticker": None,
        "accession_number": "0000000000-00-000000",
        "annual": {
            "stock_leg_value_per_share": None,
            "stock_leg_value_basis": None,
            "source_period": None,
            "withheld_observations": {},
        },
        "quarterly": {
            "stock_leg_value_per_share": None,
            "stock_leg_value_basis": None,
            "source_period": None,
            "withheld_observations": {},
        },
    }
    for key, value in overrides.items():
        if key in ("stock_leg_value_per_share", "stock_leg_value_basis"):
            record["annual"][key] = value
            record["quarterly"][key] = value
        else:
            record[key] = value
    return record


class TestEngineTerminalPaths(unittest.TestCase):
    """Each treatment, driven end to end through a rebalancing period."""

    def _run(self, action, acquirer_priced=True, frequency="annual", after_tax=False):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = TerminalFixture(tmpdir, action, acquirer_priced=acquirer_priced)
            simulator = PortfolioSimulator(fixture.loader())
            result = simulator.run_simulation(
                start_year=2000,
                end_year=2001,
                n=2,
                is_after_tax=after_tax,
                initial_capital=10000.0,
                rebalance_frequency=frequency,
            )
            return simulator, result

    def test_cash_consideration_credits_the_stated_amount(self):
        """Dell's holders received $13.75, not the last price Dell traded at."""
        simulator, _ = self._run(_action("cash", cash_per_share=13.75))

        terminal = [t for t in simulator.get_trades() if t.action == "TERMINAL"]
        self.assertEqual(len(terminal), 1)
        self.assertEqual(terminal[0].ticker, "DYING")
        self.assertAlmostEqual(terminal[0].price, 13.75)
        # 5000 dollars bought 100 shares at $50; $13.75 each is a $3,625 loss.
        self.assertAlmostEqual(terminal[0].shares, 100.0)
        self.assertAlmostEqual(terminal[0].realized_gain, -3625.0)
        self.assertNotIn("DYING", simulator.tax_manager.get_all_positions())

    def test_delisting_to_zero_writes_the_position_off_to_the_carryforward(self):
        """WorldCom's and Nortel's holders received nothing at all."""
        simulator, result = self._run(_action("zero"), after_tax=True)

        terminal = [t for t in simulator.get_trades() if t.action == "TERMINAL"]
        self.assertAlmostEqual(terminal[0].price, 0.0)
        self.assertAlmostEqual(terminal[0].realized_gain, -5000.0)
        # The whole basis becomes a capital loss, and no tax can be owed on it.
        self.assertGreater(result.annual_history[0].loss_carryforward, 0.0)
        self.assertAlmostEqual(result.annual_history[0].capital_gains_tax_paid, 0.0)

    def _settle(self, action, acquirer_priced=True, shares=100.0, basis=50.0, quarter=None):
        """Apply one terminal action to a seeded position and stop there.

        The end-to-end runs below carry on rebalancing afterwards, which sells the
        converted position again, so the state a conversion leaves behind has to be read
        at the moment it happens rather than at the end of the simulation.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = TerminalFixture(tmpdir, action, acquirer_priced=acquirer_priced)
            simulator = PortfolioSimulator(fixture.loader())
            simulator.tax_manager.add_lot("DYING", shares, basis, 2000)
            proceeds, gain, settled = simulator._apply_terminal_actions(2001, quarter)
            return simulator, proceeds, gain, settled

    def test_stock_conversion_realises_nothing_and_carries_basis_forward(self):
        """Section 368, where the acquirer can be priced."""
        simulator, proceeds, gain, settled = self._settle(
            _action(
                "stock",
                acquirer_ticker="ACQ",
                stock_exchange_ratio=2.0,
                stock_leg_value_per_share=40.0,
                stock_leg_value_basis="last_observed_price",
            )
        )

        self.assertEqual(settled, ["DYING"])
        self.assertAlmostEqual(proceeds, 0.0)
        self.assertAlmostEqual(gain, 0.0)
        self.assertAlmostEqual(simulator.tax_manager.current_annual_realized_gain, 0.0)
        self.assertNotIn("DYING", simulator.tax_manager.get_all_positions())

        # 100 shares worth $40 each is $4,000, which is 200 shares of ACQ at $20.
        acq_lots = simulator.tax_manager.get_lots("ACQ")
        self.assertAlmostEqual(sum(lot.shares for lot in acq_lots), 200.0)
        # Basis carries forward whole: the conversion is not a disposal.
        self.assertAlmostEqual(
            sum(lot.shares * lot.purchase_price for lot in acq_lots), 100.0 * 50.0
        )
        self.assertEqual([lot.purchase_year for lot in acq_lots], [2000])

    def test_a_conversion_is_recorded_as_an_exchange_in_the_trade_history(self):
        simulator, _ = self._run(
            _action(
                "stock",
                acquirer_ticker="ACQ",
                stock_exchange_ratio=2.0,
                stock_leg_value_per_share=40.0,
                stock_leg_value_basis="last_observed_price",
            )
        )
        exchanges = [t for t in simulator.get_trades() if t.action == "EXCHANGE"]
        self.assertEqual(len(exchanges), 1)
        self.assertEqual(exchanges[0].ticker, "DYING")
        self.assertAlmostEqual(exchanges[0].price, 40.0)
        self.assertAlmostEqual(exchanges[0].realized_gain, 0.0)
        self.assertNotIn("DYING", simulator.tax_manager.get_all_positions())

    def test_stock_conversion_into_an_unfollowable_successor_is_a_disposal(self):
        """Lucent's acquirer chain leaves the universe, so there is nothing to convert into.

        The position is realised at the stock leg's value and recorded as a disposal, not
        as a reorganisation -- the distinction is the whole reason the treatment is
        chosen explicitly rather than falling through to a default.
        """
        simulator, _ = self._run(
            _action(
                "stock",
                acquirer_ticker="ACQ",
                stock_exchange_ratio=2.0,
                stock_leg_value_per_share=40.0,
                stock_leg_value_basis="last_observed_price",
            ),
            acquirer_priced=False,
        )

        self.assertEqual([t.action for t in simulator.get_trades() if t.ticker == "DYING"][-1],
                         "TERMINAL")
        terminal = [t for t in simulator.get_trades() if t.action == "TERMINAL"]
        self.assertAlmostEqual(terminal[0].price, 40.0)
        self.assertAlmostEqual(terminal[0].realized_gain, -1000.0)
        self.assertNotIn("ACQ", simulator.tax_manager.get_all_positions())

    def test_cash_and_stock_recognises_the_cash_as_boot(self):
        """AT&T Corp's holders received $1.30 plus shares; only the cash is recognised."""
        simulator, proceeds, gain, _ = self._settle(
            _action(
                "cash_and_stock",
                cash_per_share=10.0,
                acquirer_ticker="ACQ",
                stock_exchange_ratio=2.0,
                stock_leg_value_per_share=60.0,
                stock_leg_value_basis="last_observed_price",
            )
        )

        # Realised gain is 100 * (10 + 60) - 5000 = 2000; the cash is 100 * 10 = 1000,
        # and Section 356 recognises the smaller of the two.
        self.assertAlmostEqual(proceeds, 1000.0)
        self.assertAlmostEqual(gain, 1000.0)
        self.assertAlmostEqual(simulator.cash, 1000.0)
        # Basis: 5000 - 1000 cash + 1000 recognised = 5000, carried into 300 ACQ shares.
        acq_lots = simulator.tax_manager.get_lots("ACQ")
        self.assertAlmostEqual(sum(lot.shares for lot in acq_lots), 300.0)
        self.assertAlmostEqual(
            sum(lot.shares * lot.purchase_price for lot in acq_lots), 5000.0
        )

    def test_cash_and_stock_into_an_unfollowable_successor_settles_at_both_legs(self):
        """EMC's holders received cash plus a tracking stock this universe cannot price."""
        simulator, _ = self._run(
            _action(
                "cash_and_stock",
                cash_per_share=10.0,
                acquirer_ticker="ACQ",
                stock_leg_value_per_share=60.0,
                stock_leg_value_basis="last_observed_price",
            ),
            acquirer_priced=False,
        )
        terminal = [t for t in simulator.get_trades() if t.action == "TERMINAL"]
        self.assertAlmostEqual(terminal[0].price, 70.0)
        self.assertAlmostEqual(terminal[0].realized_gain, 2000.0)

    def test_a_stock_leg_with_no_value_refuses_rather_than_guessing(self):
        with self.assertRaises(ValueError):
            self._run(_action("stock", acquirer_ticker="ACQ", stock_exchange_ratio=2.0))

    def test_the_unleveraged_cash_invariant_holds_through_every_treatment(self):
        """cash >= 0 at all times; a terminal action credits the portfolio, never debits it."""
        actions = [
            _action("cash", cash_per_share=13.75),
            _action("zero"),
            _action(
                "stock",
                acquirer_ticker="ACQ",
                stock_leg_value_per_share=40.0,
                stock_leg_value_basis="last_observed_price",
            ),
            _action(
                "cash_and_stock",
                cash_per_share=10.0,
                acquirer_ticker="ACQ",
                stock_leg_value_per_share=60.0,
                stock_leg_value_basis="last_observed_price",
            ),
        ]
        for action in actions:
            for frequency in ("annual", "quarterly"):
                for after_tax in (False, True):
                    with self.subTest(
                        consideration=action["consideration_type"],
                        frequency=frequency,
                        after_tax=after_tax,
                    ):
                        simulator, result = self._run(
                            action, frequency=frequency, after_tax=after_tax
                        )
                        self.assertGreaterEqual(simulator.cash, -1e-7)
                        for entry in result.annual_history + result.quarterly_history:
                            self.assertGreaterEqual(entry.cash, -1e-7)

    def test_a_terminal_action_fires_in_its_own_quarter_and_no_other(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = TerminalFixture(tmpdir, _action("cash", cash_per_share=13.75))
            loader = fixture.loader()
            self.assertIsNotNone(loader.get_terminal_action("DYING", 2001, 2))
            for quarter in (1, 3, 4):
                self.assertIsNone(loader.get_terminal_action("DYING", 2001, quarter))
            self.assertIsNotNone(loader.get_terminal_action("DYING", 2001))
            self.assertIsNone(loader.get_terminal_action("DYING", 2000))
            self.assertIsNone(loader.get_terminal_action("SAFE", 2001, 2))


class TestTopTwentyUniverseInvariant(unittest.TestCase):
    """#37's most valuable single artifact: no Top-20 constituent is unpriceable.

    The rule is traceability to an identified source, not residence in a particular
    directory. Satisfying it literally against `data/raw/tickers/` would mean writing
    filing-derived data into the raw-vendor directory in vendor shape, which is the
    confusion `docs/DATA_PROVENANCE.md` exists to prevent.
    """

    @staticmethod
    def _normalise(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    def test_every_top_20_position_in_an_audited_roster_has_a_price_that_year(self):
        with open(RAW_DIR / "constituents" / "issuer_ticker_map.json", encoding="utf-8") as f:
            issuer_map = json.load(f)["map"]
        with open(RAW_DIR / "ground_truth" / "vanguard_audited_rosters.json", encoding="utf-8") as f:
            rosters = json.load(f)["rosters_by_year"]
        with open(DATA_DIR / "sp500_prices.json", encoding="utf-8") as f:
            prices = json.load(f)

        lookup = {self._normalise(k): v for k, v in issuer_map.items()}
        checked = 0
        for year, roster in sorted(rosters.items()):
            for holding in roster["holdings"]:
                if holding["rank"] > 20:
                    continue
                ticker = lookup.get(self._normalise(holding["name"]))
                self.assertIsNotNone(
                    ticker, f"{year}: '{holding['name']}' resolves to no ticker"
                )
                self.assertIn(
                    year,
                    prices.get(ticker, {}),
                    f"{year}: {ticker} ('{holding['name']}') ranks "
                    f"#{holding['rank']} and has no price series",
                )
                checked += 1

        # Nineteen audited rosters, twenty positions each. Asserted exactly rather than
        # loosely, so that adding a roster fails here and the figure quoted in
        # docs/DATA_PROVENANCE.md 4.3.16 is revisited with it.
        self.assertEqual(checked, 380)

    def test_every_gap_constituent_reaching_a_top_20_is_now_priced(self):
        """The survivorship gap #37 opened with, measured against the compiled dataset."""
        with open(RAW_DIR / "ground_truth" / "universe_gap_report.json", encoding="utf-8") as f:
            gap = json.load(f)["missing_tickers"]
        with open(DATA_DIR / "sp500_prices.json", encoding="utf-8") as f:
            prices = json.load(f)

        reaching_top_20 = sorted(t for t, v in gap.items() if v["best_rank"] <= 20)
        self.assertEqual(len(reaching_top_20), 14)
        for ticker in reaching_top_20:
            self.assertTrue(
                prices.get(ticker),
                f"{ticker} reaches rank #{gap[ticker]['best_rank']} in an archived filing "
                "and has no price series",
            )


if __name__ == "__main__":
    unittest.main()
