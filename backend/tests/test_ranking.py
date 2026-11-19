from dataclasses import dataclass

from app.services.ranking import MIN_GAP, RANK_STEP, compute_insert_position, rebalance_positions


@dataclass
class _Item:
    id: str
    position: float


def test_compute_insert_position_empty_prepend_append_and_between() -> None:
    pos_empty, rebalance = compute_insert_position(None, None)
    assert pos_empty == RANK_STEP
    assert rebalance is False

    pos_append, rebalance = compute_insert_position(1024.0, None)
    assert pos_append == 2048.0
    assert rebalance is False

    pos_prepend, rebalance = compute_insert_position(None, 1024.0)
    assert pos_prepend == 512.0
    assert rebalance is False

    pos_mid, rebalance = compute_insert_position(1024.0, 2048.0)
    assert pos_mid == 1536.0
    assert rebalance is False


def test_compute_insert_position_triggers_rebalance_when_gap_too_small() -> None:
    low = 100.0
    high = 100.0 + MIN_GAP / 2
    _, needs_rebalance = compute_insert_position(low, high)
    assert needs_rebalance is True

    # Prepending before a near-zero position also triggers rebalance
    _, needs_rebalance_prepend = compute_insert_position(None, MIN_GAP)
    assert needs_rebalance_prepend is True

    # Repeated midpoint insertions eventually hit MIN_GAP and request rebalance
    left, right = 1.0, 2.0
    rebalanced = False
    for _ in range(40):
        mid, needs = compute_insert_position(left, right)
        if needs:
            rebalanced = True
            break
        right = mid
    assert rebalanced is True


def test_rebalance_positions_preserves_order_and_restores_gaps() -> None:
    items = [_Item("a", 1.0), _Item("b", 1.0000001), _Item("c", 1.0000002)]
    rebalance_positions(items, lambda item, pos: setattr(item, "position", pos))

    assert [item.id for item in items] == ["a", "b", "c"]
    assert [item.position for item in items] == [RANK_STEP, 2 * RANK_STEP, 3 * RANK_STEP]
