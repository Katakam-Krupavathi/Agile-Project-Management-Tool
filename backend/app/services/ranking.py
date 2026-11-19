from collections.abc import Callable, Sequence
from typing import TypeVar

RANK_STEP: float = 1024.0
MIN_GAP: float = 1e-6

T = TypeVar("T")


def compute_insert_position(
    before_pos: float | None,
    after_pos: float | None,
) -> tuple[float, bool]:
    """Compute a fractional rank between optional neighbor positions.

    Returns ``(position, needs_rebalance)``. When ``needs_rebalance`` is True,
    callers should rebalance the ordered sibling list via ``rebalance_positions``
    so wide gaps are restored.
    """
    if before_pos is None and after_pos is None:
        return RANK_STEP, False

    if before_pos is None:
        assert after_pos is not None
        if after_pos <= MIN_GAP * 2:
            return 0.0, True
        return after_pos / 2.0, False

    if after_pos is None:
        return before_pos + RANK_STEP, False

    gap = after_pos - before_pos
    if gap <= MIN_GAP:
        return 0.0, True

    midpoint = (before_pos + after_pos) / 2.0
    if midpoint in (before_pos, after_pos):
        return 0.0, True

    return midpoint, False


def rebalance_positions(
    ordered_items: Sequence[T],
    set_position: Callable[[T, float], None],
) -> None:
    """Assign evenly spaced positions to an already-ordered sequence of items."""
    for index, item in enumerate(ordered_items, start=1):
        set_position(item, float(index) * RANK_STEP)
