import pytest
from miter_cutting_stock_milp import Part, solve_cutting_milp


def test_strict_miter_pairing_and_capacity():
    parts = [
        Part("S", 2, 1000, "straight"),
        Part("M", 4, 1500, "miter", "G"),
    ]
    result = solve_cutting_milp(parts, stock_length_mm=6000, max_bars=5)
    assert result.objective_bars == 2
    for bar in result.bars:
        assert bar.used_length_mm <= 6000
        assert sum(bar.miter_normal.values()) == sum(bar.miter_flipped.values())


def test_odd_group_demand_is_rejected():
    parts = [Part("M", 3, 1000, "miter", "G")]
    with pytest.raises(ValueError, match="odd miter demand"):
        solve_cutting_milp(parts, max_bars=3)


def test_effective_length_controls_capacity():
    # 4 x 1510 = 6040, so a single bar is impossible even though nominal might be 1500.
    parts = [Part("M", 4, 1510, "miter", "G")]
    result = solve_cutting_milp(parts, stock_length_mm=6000, max_bars=4)
    assert result.objective_bars == 2
