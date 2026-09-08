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
    ) -> None:
        """Initialize DataLoader with dataset paths.

        Args:
            constituents_path: Optional path to sp500_constituents.json.
                Defaults to data/sp500_constituents.json relative to project root.
            prices_path: Optional path to sp500_prices.json.
                Defaults to data/sp500_prices.json relative to project root.
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

        if not constituents_path.exists():
            raise FileNotFoundError(
                f"Constituents dataset file not found: {constituents_path}"
            )
        if not prices_path.exists():
            raise FileNotFoundError(f"Prices dataset file not found: {prices_path}")

        with open(constituents_path, "r", encoding="utf-8") as f:
            self._raw_constituents: Dict[str, list] = json.load(f)

        with open(prices_path, "r", encoding="utf-8") as f:
            self._raw_prices: Dict[str, Dict[str, float]] = json.load(f)

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

    def load_universe(self, year: int) -> List[ConstituentSnapshot]:
        """Load constituent snapshots for a given year.

        Args:
            year: Four-digit calendar year (e.g. 1995, 2024).

        Returns:
            List of ConstituentSnapshot instances.

        Raises:
            ValueError: If year is outside the available dataset range.
        """
        str_year = str(year)
        if str_year not in self._raw_constituents:
            raise ValueError(
                f"Year {year} is not available. Available years: "
                f"{self._available_years[0]}..{self._available_years[-1]}"
            )

        items = self._raw_constituents[str_year]
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

    def get_spx_level(self, year: int) -> float:
        """Retrieve S&P 500 (^GSPC) benchmark index level for a given year.

        Args:
            year: Calendar year (1994..2024).

        Returns:
            Benchmark index level as float.

        Raises:
            KeyError: If year is not available for benchmark index.
        """
        return self.get_price("^GSPC", year)
