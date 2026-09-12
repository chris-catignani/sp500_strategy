"""Historical S&P 500 constituents and split-adjusted prices data loader."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

from engine.models import ConstituentSnapshot


class DataLoader:
    """Loads point-in-time constituent snapshots and split-adjusted prices."""

    def __init__(
        self,
        constituents_path: Optional[Union[str, Path]] = None,
        prices_path: Optional[Union[str, Path]] = None,
        dividends_path: Optional[Union[str, Path]] = None,
        quarterly_constituents_path: Optional[Union[str, Path]] = None,
        quarterly_prices_path: Optional[Union[str, Path]] = None,
        quarterly_dividends_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """Initialize DataLoader with dataset paths.

        Args:
            constituents_path: Optional path to sp500_constituents.json.
                Defaults to data/sp500_constituents.json relative to project root.
            prices_path: Optional path to sp500_prices.json.
                Defaults to data/sp500_prices.json relative to project root.
            dividends_path: Optional path to sp500_dividends.json.
                Defaults to data/sp500_dividends.json relative to project root.
            quarterly_constituents_path: Optional path to quarterly constituents dataset.
            quarterly_prices_path: Optional path to quarterly prices dataset.
            quarterly_dividends_path: Optional path to quarterly dividends dataset.
        """
        project_root = Path(__file__).resolve().parent.parent

        if constituents_path is None:
            constituents_path = project_root / "data" / "sp500_constituents.json"
        else:
            constituents_path = Path(constituents_path)

        if prices_path is None:
            prices_path = project_root / "data" / "sp500_prices.json"
        else:
            prices_path = Path(prices_path)

        if dividends_path is None:
            dividends_path = project_root / "data" / "sp500_dividends.json"
        else:
            dividends_path = Path(dividends_path)

        if quarterly_constituents_path is None:
            quarterly_constituents_path = project_root / "data" / "sp500_quarterly_constituents.json"
        else:
            quarterly_constituents_path = Path(quarterly_constituents_path)

        if quarterly_prices_path is None:
            quarterly_prices_path = project_root / "data" / "sp500_quarterly_prices.json"
        else:
            quarterly_prices_path = Path(quarterly_prices_path)

        if quarterly_dividends_path is None:
            quarterly_dividends_path = project_root / "data" / "sp500_quarterly_dividends.json"
        else:
            quarterly_dividends_path = Path(quarterly_dividends_path)

        if not constituents_path.exists():
            raise FileNotFoundError(
                f"Constituents dataset file not found: {constituents_path}"
            )
        if not prices_path.exists():
            raise FileNotFoundError(f"Prices dataset file not found: {prices_path}")
        if not dividends_path.exists():
            raise FileNotFoundError(f"Dividends dataset file not found: {dividends_path}")

        with open(constituents_path, "r", encoding="utf-8") as f:
            self._raw_constituents: Dict[str, list] = json.load(f)

        with open(prices_path, "r", encoding="utf-8") as f:
            self._raw_prices: Dict[str, Dict[str, float]] = json.load(f)

        with open(dividends_path, "r", encoding="utf-8") as f:
            self._raw_dividends: Dict[str, Dict[str, float]] = json.load(f)

        # Multi-universe constituent registry
        self._universes: Dict[str, Dict[str, list]] = {
            "sp500": self._raw_constituents,
        }

        # Quarterly datasets registry
        self._quarterly_universes: Dict[str, Dict[str, list]] = {}
        self._raw_quarterly_prices: Dict[str, Dict[str, float]] = {}
        self._raw_quarterly_dividends: Dict[str, Dict[str, float]] = {}

        if quarterly_constituents_path.exists():
            with open(quarterly_constituents_path, "r", encoding="utf-8") as f:
                self._quarterly_universes["sp500"] = json.load(f)

        if quarterly_prices_path.exists():
            with open(quarterly_prices_path, "r", encoding="utf-8") as f:
                self._raw_quarterly_prices = json.load(f)

        if quarterly_dividends_path.exists():
            with open(quarterly_dividends_path, "r", encoding="utf-8") as f:
                self._raw_quarterly_dividends = json.load(f)

        # Check for co-located All-World datasets
        world_const_path = project_root / "data" / "world_constituents.json"
        world_prices_path = project_root / "data" / "world_prices.json"
        world_divs_path = project_root / "data" / "world_dividends.json"
        world_q_const_path = project_root / "data" / "world_quarterly_constituents.json"
        world_q_prices_path = project_root / "data" / "world_quarterly_prices.json"
        world_q_divs_path = project_root / "data" / "world_quarterly_dividends.json"

        if world_const_path.exists():
            with open(world_const_path, "r", encoding="utf-8") as f:
                self._universes["world"] = json.load(f)
                self._universes["all_world"] = self._universes["world"]

        if world_q_const_path.exists():
            with open(world_q_const_path, "r", encoding="utf-8") as f:
                self._quarterly_universes["world"] = json.load(f)
                self._quarterly_universes["all_world"] = self._quarterly_universes["world"]

        if world_prices_path.exists():
            with open(world_prices_path, "r", encoding="utf-8") as f:
                world_prices = json.load(f)
                for sym, y_data in world_prices.items():
                    if sym not in self._raw_prices:
                        self._raw_prices[sym] = y_data
                    else:
                        self._raw_prices[sym].update(y_data)

        if world_q_prices_path.exists():
            with open(world_q_prices_path, "r", encoding="utf-8") as f:
                world_q_prices = json.load(f)
                for sym, q_data in world_q_prices.items():
                    if sym not in self._raw_quarterly_prices:
                        self._raw_quarterly_prices[sym] = q_data
                    else:
                        self._raw_quarterly_prices[sym].update(q_data)

        if world_divs_path.exists():
            with open(world_divs_path, "r", encoding="utf-8") as f:
                world_divs = json.load(f)
                for sym, y_data in world_divs.items():
                    if sym not in self._raw_dividends:
                        self._raw_dividends[sym] = y_data
                    else:
                        self._raw_dividends[sym].update(y_data)

        if world_q_divs_path.exists():
            with open(world_q_divs_path, "r", encoding="utf-8") as f:
                world_q_divs = json.load(f)
                for sym, q_data in world_q_divs.items():
                    if sym not in self._raw_quarterly_dividends:
                        self._raw_quarterly_dividends[sym] = q_data
                    else:
                        self._raw_quarterly_dividends[sym].update(q_data)

        # Parse available years
        self._available_years: List[int] = sorted(
            int(yr) for yr in self._raw_constituents.keys()
        )

    def get_available_years(self) -> List[int]:
        """Return sorted list of all available constituent years (1994..2024).

        Returns:
            List of integer years.
        """
        return list(self._available_years)

    def get_available_universes(self) -> List[str]:
        """Return list of distinct registered universes."""
        return [u for u in self._universes.keys() if u != "all_world"]

    def load_universe(self, year: int, universe: str = "sp500") -> List[ConstituentSnapshot]:
        """Load constituent snapshots for a given year and universe.

        Args:
            year: Four-digit calendar year (e.g. 1995, 2024).
            universe: Identifier of target universe ('sp500' or 'world').

        Returns:
            List of ConstituentSnapshot instances.

        Raises:
            ValueError: If year or universe is not available.
        """
        u_key = universe.lower().replace("-", "_")
        if u_key not in self._universes:
            raise ValueError(
                f"Universe '{universe}' not recognized. Available: {self.get_available_universes()}"
            )

        universe_data = self._universes[u_key]
        str_year = str(year)
        if str_year not in universe_data:
            raise ValueError(
                f"Year {year} is not available in universe '{universe}'. Available years: "
                f"{self._available_years[0]}..{self._available_years[-1]}"
            )

        items = universe_data[str_year]
        return [
            ConstituentSnapshot(
                ticker=c["ticker"],
                name=c["name"],
                market_cap_weight=float(c["market_cap_weight"]),
                trailing_1y_return=float(c["trailing_1y_return"]),
                year=int(c["year"]),
            )
            for c in items
        ]

    def get_price(self, ticker: str, year: int) -> float:
        """Retrieve year-end split-adjusted close price for a ticker and year.

        Args:
            ticker: Stock ticker symbol (e.g. 'AAPL', '^GSPC').
            year: Calendar year.

        Returns:
            Float price > 0.

        Raises:
            KeyError: If ticker is unknown or price for year is missing.
        """
        if ticker not in self._raw_prices:
            raise KeyError(f"Ticker '{ticker}' not found in prices dataset")

        ticker_prices = self._raw_prices[ticker]
        str_year = str(year)
        if str_year not in ticker_prices:
            raise KeyError(
                f"Price for ticker '{ticker}' in year {year} not found in prices dataset"
            )

        price = float(ticker_prices[str_year])
        if price <= 0.0:
            raise ValueError(f"Price for '{ticker}' in {year} must be positive, got {price}")
        return price

    BENCHMARK_KEY_MAP = {
        "sp500": ("^GSPC", "^SP500TR"),
        "s&p 500": ("^GSPC", "^SP500TR"),
        "^gspc": ("^GSPC", "^SP500TR"),
        "^sp500tr": ("^GSPC", "^SP500TR"),
        "sp500tr": ("^GSPC", "^SP500TR"),
        "msci_world": ("^MSCIWORLD_PR", "^MSCIWORLD_TR"),
        "msci world": ("^MSCIWORLD_PR", "^MSCIWORLD_TR"),
        "^msciworld_pr": ("^MSCIWORLD_PR", "^MSCIWORLD_TR"),
        "^msciworld_tr": ("^MSCIWORLD_PR", "^MSCIWORLD_TR"),
        "msciworld_tr": ("^MSCIWORLD_PR", "^MSCIWORLD_TR"),
        "fbgrx": ("FBGRX", "FBGRX_TR"),
        "fbgrx_tr": ("FBGRX", "FBGRX_TR"),
    }

    def get_benchmark_level(self, benchmark: str, year: int) -> float:
        """Retrieve benchmark Price Return / NAV level for a given year."""
        bmk_lower = benchmark.lower()
        if bmk_lower in self.BENCHMARK_KEY_MAP:
            ticker = self.BENCHMARK_KEY_MAP[bmk_lower][0]
        elif benchmark.upper().endswith(("_TR", "TR")):
            b_up = benchmark.upper()
            ticker = b_up[:-3] if b_up.endswith("_TR") else b_up[:-2]
        else:
            ticker = benchmark.upper()
        return self.get_price(ticker, year)

    def get_benchmark_tr_level(self, benchmark: str, year: int) -> float:
        """Retrieve benchmark Total Return level for a given year."""
        bmk_lower = benchmark.lower()
        if bmk_lower in self.BENCHMARK_KEY_MAP:
            ticker = self.BENCHMARK_KEY_MAP[bmk_lower][1]
        elif benchmark.upper().endswith(("_TR", "TR")):
            ticker = benchmark.upper()
        else:
            ticker = f"{benchmark.upper()}_TR"
        return self.get_price(ticker, year)

    def get_benchmark_quarterly_level(self, benchmark: str, year: int, quarter: int) -> float:
        """Retrieve benchmark Price Return / NAV level at end of (year, quarter)."""
        bmk_lower = benchmark.lower()
        if bmk_lower in self.BENCHMARK_KEY_MAP:
            ticker = self.BENCHMARK_KEY_MAP[bmk_lower][0]
        elif benchmark.upper().endswith(("_TR", "TR")):
            b_up = benchmark.upper()
            ticker = b_up[:-3] if b_up.endswith("_TR") else b_up[:-2]
        else:
            ticker = benchmark.upper()
        return self.get_quarterly_price(ticker, year, quarter)

    def get_benchmark_quarterly_tr_level(self, benchmark: str, year: int, quarter: int) -> float:
        """Retrieve benchmark Total Return level at end of (year, quarter)."""
        bmk_lower = benchmark.lower()
        if bmk_lower in self.BENCHMARK_KEY_MAP:
            ticker = self.BENCHMARK_KEY_MAP[bmk_lower][1]
        elif benchmark.upper().endswith(("_TR", "TR")):
            ticker = benchmark.upper()
        else:
            ticker = f"{benchmark.upper()}_TR"
        return self.get_quarterly_price(ticker, year, quarter)

    def get_benchmark_dividend_yield(self, benchmark: str, year: int) -> float:
        """Calculate the benchmark dividend / distribution yield for a given year."""
        tr_curr = self.get_benchmark_tr_level(benchmark, year)
        tr_prev = self.get_benchmark_tr_level(benchmark, year - 1)
        r_tr = (tr_curr - tr_prev) / tr_prev if tr_prev > 0.0 else 0.0
        pr_curr = self.get_benchmark_level(benchmark, year)
        pr_prev = self.get_benchmark_level(benchmark, year - 1)
        r_pr = (pr_curr - pr_prev) / pr_prev if pr_prev > 0.0 else 0.0
        return max(0.0, r_tr - r_pr)

    get_quarterly_benchmark_level = get_benchmark_quarterly_level
    get_quarterly_benchmark_tr_level = get_benchmark_quarterly_tr_level

    def get_fbgrx_level(self, year: int) -> float:
        """Retrieve FBGRX NAV close for a given year."""
        return self.get_benchmark_level("fbgrx", year)

    def get_fbgrx_tr_level(self, year: int) -> float:
        """Retrieve FBGRX Total Return level for a given year."""
        return self.get_benchmark_tr_level("fbgrx", year)

    def get_fbgrx_quarterly_level(self, year: int, quarter: int) -> float:
        """Retrieve FBGRX NAV close at end of (year, quarter)."""
        return self.get_benchmark_quarterly_level("fbgrx", year, quarter)

    def get_fbgrx_tr_quarterly_level(self, year: int, quarter: int) -> float:
        """Retrieve FBGRX Total Return level at end of (year, quarter)."""
        return self.get_benchmark_quarterly_tr_level("fbgrx", year, quarter)

    def get_fbgrx_dividend_yield(self, year: int) -> float:
        """Calculate FBGRX distribution yield for a given year."""
        return self.get_benchmark_dividend_yield("fbgrx", year)

    def get_spx_level(self, year: int) -> float:
        """Retrieve S&P 500 (^GSPC) benchmark index level for a given year."""
        return self.get_benchmark_level("sp500", year)

    def get_dividend(self, ticker: str, year: int) -> float:
        """Retrieve split-adjusted cash dividend per share for a ticker and year.

        Args:
            ticker: Stock ticker symbol (e.g. 'AAPL').
            year: Calendar year.

        Returns:
            Annual cash dividend per share as float, or 0.0 if not paid or missing.
        """
        ticker_divs = self._raw_dividends.get(ticker, {})
        return float(ticker_divs.get(str(year), 0.0))

    def get_spx_tr_level(self, year: int) -> float:
        """Retrieve S&P 500 Total Return (^SP500TR) index level for a given year."""
        return self.get_benchmark_tr_level("sp500", year)

    def get_spx_dividend_yield(self, year: int) -> float:
        """Calculate the benchmark S&P 500 dividend yield for a given year."""
        return self.get_benchmark_dividend_yield("sp500", year)

    def get_msci_world_level(self, year: int) -> float:
        """Retrieve MSCI World Price Return (^MSCIWORLD_PR) index level for a given year."""
        return self.get_benchmark_level("msci_world", year)

    def get_msci_world_tr_level(self, year: int) -> float:
        """Retrieve MSCI World Total Return (^MSCIWORLD_TR) index level for a given year."""
        return self.get_benchmark_tr_level("msci_world", year)

    def get_msci_world_dividend_yield(self, year: int) -> float:
        """Calculate the benchmark MSCI World dividend yield for a given year."""
        return self.get_benchmark_dividend_yield("msci_world", year)

    def get_quarterly_price(self, ticker: str, year: int, quarter: int) -> float:
        """Retrieve split-adjusted close for a ticker at the end of (year, quarter).

        Args:
            ticker: Equity or index symbol.
            year: Four-digit calendar year.
            quarter: Calendar quarter (1..4).

        Returns:
            Closing price as float.
        """
        key = f"{year}-Q{quarter}"
        if ticker in self._raw_quarterly_prices and key in self._raw_quarterly_prices[ticker]:
            return float(self._raw_quarterly_prices[ticker][key])
        if quarter == 4 and ticker in self._raw_prices and str(year) in self._raw_prices[ticker]:
            return float(self._raw_prices[ticker][str(year)])
        raise KeyError(f"Quarterly price not found for '{ticker}' at {key}")

    def get_quarterly_dividend(self, ticker: str, year: int, quarter: int) -> float:
        """Retrieve split-adjusted cash dividend per share for ticker during (year, quarter).

        Args:
            ticker: Equity symbol.
            year: Four-digit calendar year.
            quarter: Calendar quarter (1..4).

        Returns:
            Cash dividend per share as float, or 0.0 if not paid.
        """
        key = f"{year}-Q{quarter}"
        if ticker in self._raw_quarterly_dividends and key in self._raw_quarterly_dividends[ticker]:
            return float(self._raw_quarterly_dividends[ticker][key])
        return 0.0

    def load_quarterly_universe(
        self, year: int, quarter: int, universe: str = "sp500"
    ) -> List[ConstituentSnapshot]:
        """Load point-in-time constituent snapshot for a specific quarter.

        Supports pluggable external datasets via _quarterly_universes.

        Args:
            year: Four-digit calendar year.
            quarter: Calendar quarter (1..4).
            universe: Identifier of target universe ('sp500' or 'world').

        Returns:
            List of ConstituentSnapshot instances.
        """
        u_key = universe.lower()
        if u_key not in self._quarterly_universes:
            u_key = "world" if u_key in ("world", "all_world") else "sp500"

        key = f"{year}-Q{quarter}"
        if u_key in self._quarterly_universes and key in self._quarterly_universes[u_key]:
            raw_entries = self._quarterly_universes[u_key][key]
            return [
                ConstituentSnapshot(
                    ticker=item["ticker"],
                    name=item["name"],
                    market_cap_weight=float(item["market_cap_weight"]),
                    trailing_1y_return=float(item["trailing_1y_return"]),
                    year=int(item["year"]),
                    quarter=int(item.get("quarter", quarter)),
                )
                for item in raw_entries
            ]

        # Fallback to annual universe if Q4
        if quarter == 4:
            ann_u = self.load_universe(year, universe=universe)
            return [
                ConstituentSnapshot(
                    ticker=c.ticker,
                    name=c.name,
                    market_cap_weight=c.market_cap_weight,
                    trailing_1y_return=c.trailing_1y_return,
                    year=c.year,
                    quarter=4,
                )
                for c in ann_u
            ]

        raise KeyError(f"No quarterly constituent data found for universe '{universe}' at {key}")

    def get_spx_quarterly_level(self, year: int, quarter: int) -> float:
        """Retrieve S&P 500 Price Return (^GSPC) level at end of (year, quarter)."""
        return self.get_benchmark_quarterly_level("sp500", year, quarter)

    def get_spx_tr_quarterly_level(self, year: int, quarter: int) -> float:
        """Retrieve S&P 500 Total Return (^SP500TR) level at end of (year, quarter)."""
        return self.get_benchmark_quarterly_tr_level("sp500", year, quarter)

    def get_msci_world_quarterly_level(self, year: int, quarter: int) -> float:
        """Retrieve MSCI World Price Return (^MSCIWORLD_PR) level at end of (year, quarter)."""
        return self.get_benchmark_quarterly_level("msci_world", year, quarter)

    def get_msci_world_tr_quarterly_level(self, year: int, quarter: int) -> float:
        """Retrieve MSCI World Total Return (^MSCIWORLD_TR) level at end of (year, quarter)."""
        return self.get_benchmark_quarterly_tr_level("msci_world", year, quarter)
