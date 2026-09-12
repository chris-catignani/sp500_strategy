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
    """Selector that picks top N constituents sorted descending by trailing 1-year return."""

    def select(
        self,
        universe: Sequence[ConstituentSnapshot],
        n: Optional[int] = None,
    ) -> List[HoldingTarget]:
        """Select top N constituents by trailing 1-year return.

        Args:
            universe: Point-in-time constituent snapshots.
            n: Optional override for constituent count. Defaults to self.n.

        Returns:
            List of HoldingTarget instances ordered by trailing_1y_return descending.
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

        # Sort descending by trailing_1y_return
        sorted_constituents = sorted(
            universe, key=lambda c: c.trailing_1y_return, reverse=True
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

