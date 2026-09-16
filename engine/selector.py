"""Pluggable portfolio constituent selector interface and implementations."""

from abc import ABC, abstractmethod
from typing import List, Optional, Sequence
import warnings
from engine.models import ConstituentSnapshot, HoldingTarget

EPSILON = 1e-9


class BaseSelector(ABC):
    """Abstract base class for constituent portfolio selection and weight allocation."""

    def __init__(self, n: int = 5, weight_by: str = "market_cap") -> None:
        """Initialize selector.

        Args:
            n: Target number of constituents to select (e.g. 3, 5, 10).
            weight_by: Weighting mode, either 'market_cap' (relative market cap) or 'equal'.
        """
        if n <= 0:
            raise ValueError(f"n must be positive, got {n}")
        if weight_by not in ("market_cap", "equal"):
            raise ValueError(
                f"Unknown weight_by mode: '{weight_by}'. Expected 'market_cap' or 'equal'."
            )
        self.n = n
        self.weight_by = weight_by

    def _compute_weights(
        self, constituents: Sequence[ConstituentSnapshot], weight_by: str
    ) -> List[float]:
        """Compute normalized weights summing to 1.0.

        Args:
            constituents: Selected constituents.
            weight_by: 'market_cap' or 'equal'.

        Returns:
            List of float weights summing to 1.0.
        """
        count = len(constituents)
        if count == 0:
            return []

        if weight_by == "equal":
            return [1.0 / count] * count

        # weight_by == "market_cap"
        sum_w = sum(c.market_cap_weight for c in constituents)
        if sum_w <= EPSILON:
            return [1.0 / count] * count

        return [c.market_cap_weight / sum_w for c in constituents]

    @abstractmethod
    def select(
        self,
        universe: Sequence[ConstituentSnapshot],
        n: Optional[int] = None,
    ) -> List[HoldingTarget]:
        """Select top N constituents and compute normalized target weights.

        Args:
            universe: Sequence of ConstituentSnapshot instances.
            n: Optional override for constituent count. Defaults to self.n.

        Returns:
            List of HoldingTarget instances with normalized target_weight summing to 1.0.
        """
        pass


class MarketCapSelector(BaseSelector):
    """Selector that picks top N constituents sorted descending by market cap weight."""

    def select(
        self,
        universe: Sequence[ConstituentSnapshot],
        n: Optional[int] = None,
    ) -> List[HoldingTarget]:
        """Select top N constituents by market cap weight.

        Args:
            universe: Point-in-time constituent snapshots.
            n: Optional override for constituent count. Defaults to self.n.

        Returns:
            List of HoldingTarget instances ordered by market_cap_weight descending.
        """
        eff_n = self.n if n is None else n
        if eff_n <= 0:
            raise ValueError(f"n must be positive, got {eff_n}")

        if not universe:
            return []

        if eff_n > len(universe):
            warnings.warn(
                f"Requested Top {eff_n} constituents, but universe only contains {len(universe)}. "
                f"Allocating across available {len(universe)} constituents.",
                UserWarning,
                stacklevel=2,
            )

        # Sort descending by market_cap_weight
        sorted_constituents = sorted(
            universe, key=lambda c: c.market_cap_weight, reverse=True
        )
        selected = sorted_constituents[:eff_n]
        weights = self._compute_weights(selected, self.weight_by)

        return [
            HoldingTarget(ticker=c.ticker, target_weight=w)
            for c, w in zip(selected, weights)
        ]


class PerformanceSelector(BaseSelector):
    """Selector that picks top N constituents sorted descending by trailing 1-year total return.

    Evaluates candidate constituents from the eligible mega-cap universe (e.g. top 10-12
    index market-cap leaders) and selects the top N performers ranked by trailing 1-year total
    return (split-adjusted capital appreciation plus cash dividends).
    """

    def select(
        self,
        universe: Sequence[ConstituentSnapshot],
        n: Optional[int] = None,
    ) -> List[HoldingTarget]:
        """Select top N constituents from the candidate mega-cap universe by trailing 1-year total return.

        Constituents whose trailing return is not computable from primary data
        (``trailing_1y_return is None``) are excluded from the ranking. Imputing a value
        would rank them against real returns on fabricated evidence - a 0.0 placeholder
        outranks every loser in a down year purely because data is missing.

        Args:
            universe: Point-in-time constituent snapshots representing the eligible mega-cap universe.
            n: Optional override for constituent count. Defaults to self.n.

        Returns:
            List of HoldingTarget instances ordered by trailing_1y_return descending.

        Raises:
            ValueError: If no constituent in the universe has a computable trailing return.
        """
        eff_n = self.n if n is None else n
        if eff_n <= 0:
            raise ValueError(f"n must be positive, got {eff_n}")

        if not universe:
            return []

        rankable = [c for c in universe if c.trailing_1y_return is not None]
        if not rankable:
            raise ValueError(
                f"No constituent in the universe has a computable trailing 1-year return; "
                f"cannot rank {len(universe)} candidates by momentum."
            )

        excluded = len(universe) - len(rankable)
        if excluded:
            skipped = ", ".join(
                c.ticker for c in universe if c.trailing_1y_return is None
            )
            warnings.warn(
                f"Excluding {excluded} constituent(s) with no computable trailing 1-year "
                f"return from momentum ranking: {skipped}.",
                UserWarning,
                stacklevel=2,
            )

        if eff_n > len(rankable):
            warnings.warn(
                f"Requested Top {eff_n} constituents, but universe only contains {len(rankable)}. "
                f"Allocating across available {len(rankable)} constituents.",
                UserWarning,
                stacklevel=2,
            )

        # Sort descending by trailing_1y_return
        sorted_constituents = sorted(
            rankable, key=lambda c: c.trailing_1y_return, reverse=True
        )
        selected = sorted_constituents[:eff_n]
        weights = self._compute_weights(selected, self.weight_by)

        return [
            HoldingTarget(ticker=c.ticker, target_weight=w)
            for c, w in zip(selected, weights)
        ]


def resolve_selector(
    strategy_name: str, n: int = 5, weight_by: str = "market_cap"
) -> BaseSelector:
    """Instantiate constituent selector based on strategy name and weighting mode.

    Args:
        strategy_name: 'market_cap' or 'performance'.
        n: Number of constituents to select.
        weight_by: Weighting mode, either 'market_cap' or 'equal'.

    Returns:
        Instance of BaseSelector.

    Raises:
        ValueError: If strategy_name or weight_by is unrecognized.
    """
    if weight_by not in ("market_cap", "equal"):
        raise ValueError(
            f"Unknown weight_by mode: '{weight_by}'. Expected 'market_cap' or 'equal'."
        )

    normalized = strategy_name.strip().lower()
    if normalized in ("market_cap", "marketcap"):
        return MarketCapSelector(n=n, weight_by=weight_by)
    elif normalized in ("performance", "momentum"):
        return PerformanceSelector(n=n, weight_by=weight_by)
    else:
        raise ValueError(
            f"Unknown strategy: '{strategy_name}'. Expected 'market_cap' or 'performance'."
        )

