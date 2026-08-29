from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix


@dataclass(frozen=True)
class Part:
    """A demanded profile type.

    kind:
        "straight" or "miter"
    compatibility_group:
        Miter parts may only be paired with parts in the same group.
    effective_length_mm:
        Consumption of stock length, including any cut allowance/extra miter
        length (for example, nominal length + 10 mm for a double-miter part).
    """

    name: str
    demand: int
    effective_length_mm: int
    kind: str
    compatibility_group: Optional[str] = None

    def __post_init__(self) -> None:
        if self.demand < 0:
            raise ValueError(f"Demand must be non-negative for {self.name}")
        if self.effective_length_mm <= 0:
            raise ValueError(f"Length must be positive for {self.name}")
        if self.kind not in {"straight", "miter"}:
            raise ValueError(f"kind must be 'straight' or 'miter' for {self.name}")
        if self.kind == "miter" and not self.compatibility_group:
            raise ValueError(f"Miter part {self.name} needs a compatibility_group")


@dataclass
class BarPlan:
    bar: int
    used_length_mm: int
    waste_mm: int
    straight: Dict[str, int]
    miter_normal: Dict[str, int]
    miter_flipped: Dict[str, int]
    pairs_by_group: Dict[str, int]


@dataclass
class SolveResult:
    objective_bars: int
    total_waste_mm: int
    bars: List[BarPlan]
    raw_status: int
    raw_message: str


def _default_bar_upper_bound(parts: Iterable[Part]) -> int:
    return max(1, sum(p.demand for p in parts))


def solve_cutting_milp(
    parts: List[Part],
    stock_length_mm: int = 6000,
    max_bars: Optional[int] = None,
    time_limit_s: Optional[float] = 30.0,
) -> SolveResult:
    """Solve the bar minimization problem with strict miter matching.

    Miter logic (per stock bar and compatibility group):
        number_normal == number_flipped == number_of_pairs

    A binary activation variable z[g,b] links a group to a used pair count:
        p[g,b] <= U[g] * z[g,b]
        p[g,b] >= z[g,b]

    Hence a miter group can be inactive, or it must contain at least one
    complete normal/flipped pair. No unmatched single miter part is allowed.
    """

    if stock_length_mm <= 0:
        raise ValueError("stock_length_mm must be positive")
    if not parts:
        return SolveResult(0, 0, [], 0, "No demand")

    names = [p.name for p in parts]
    if len(set(names)) != len(names):
        raise ValueError("Part names must be unique")

    straight_idx = [i for i, p in enumerate(parts) if p.kind == "straight"]
    miter_idx = [i for i, p in enumerate(parts) if p.kind == "miter"]
    groups = sorted({parts[i].compatibility_group for i in miter_idx})
    miter_by_group: Dict[str, List[int]] = {
        g: [i for i in miter_idx if parts[i].compatibility_group == g] for g in groups
    }

    for g, idxs in miter_by_group.items():
        total = sum(parts[i].demand for i in idxs)
        if total % 2:
            raise ValueError(
                f"Compatibility group {g!r} has odd miter demand ({total}). "
                "Strict one-normal/one-flipped matching is infeasible unless "
                "sacrificial/waste pieces are explicitly modeled."
            )

    B = max_bars or _default_bar_upper_bound(parts)
    if B <= 0:
        raise ValueError("max_bars must be positive")

    offset = 0
    y = {b: offset + b for b in range(B)}
    offset += B

    xs: Dict[Tuple[int, int], int] = {}
    for i in straight_idx:
        for b in range(B):
            xs[(i, b)] = offset
            offset += 1

    xm: Dict[Tuple[int, int, int], int] = {}
    for i in miter_idx:
        for b in range(B):
            for o in (0, 1):
                xm[(i, b, o)] = offset
                offset += 1

    pair: Dict[Tuple[str, int], int] = {}
    for g in groups:
        for b in range(B):
            pair[(g, b)] = offset
            offset += 1

    z: Dict[Tuple[str, int], int] = {}
    for g in groups:
        for b in range(B):
            z[(g, b)] = offset
            offset += 1

    nvar = offset

    c = np.zeros(nvar)
    for b in range(B):
        c[y[b]] = 1.0

    integrality = np.ones(nvar, dtype=int)
    lb = np.zeros(nvar)
    ub = np.full(nvar, np.inf)

    for b in range(B):
        ub[y[b]] = 1.0
    for g in groups:
        for b in range(B):
            ub[z[(g, b)]] = 1.0

    for i in straight_idx:
        for b in range(B):
            ub[xs[(i, b)]] = parts[i].demand
    for i in miter_idx:
        for b in range(B):
            for o in (0, 1):
                ub[xm[(i, b, o)]] = parts[i].demand

    constraints: List[Tuple[Dict[int, float], float, float]] = []

    for i in straight_idx:
        row = {xs[(i, b)]: 1.0 for b in range(B)}
        constraints.append((row, parts[i].demand, parts[i].demand))

    for i in miter_idx:
        row: Dict[int, float] = {}
        for b in range(B):
            row[xm[(i, b, 0)]] = 1.0
            row[xm[(i, b, 1)]] = 1.0
        constraints.append((row, parts[i].demand, parts[i].demand))

    for b in range(B):
        row: Dict[int, float] = {y[b]: -float(stock_length_mm)}
        for i in straight_idx:
            row[xs[(i, b)]] = float(parts[i].effective_length_mm)
        for i in miter_idx:
            for o in (0, 1):
                row[xm[(i, b, o)]] = float(parts[i].effective_length_mm)
        constraints.append((row, -np.inf, 0.0))

    for g in groups:
        idxs = miter_by_group[g]
        total_group_demand = sum(parts[i].demand for i in idxs)
        U_g = total_group_demand // 2
        for b in range(B):
            row_n = {pair[(g, b)]: -1.0}
            for i in idxs:
                row_n[xm[(i, b, 0)]] = 1.0
            constraints.append((row_n, 0.0, 0.0))

            row_f = {pair[(g, b)]: -1.0}
            for i in idxs:
                row_f[xm[(i, b, 1)]] = 1.0
            constraints.append((row_f, 0.0, 0.0))

            constraints.append((
                {pair[(g, b)]: 1.0, z[(g, b)]: -float(U_g)},
                -np.inf,
                0.0,
            ))
            constraints.append((
                {z[(g, b)]: 1.0, pair[(g, b)]: -1.0},
                -np.inf,
                0.0,
            ))
            constraints.append((
                {z[(g, b)]: 1.0, y[b]: -1.0},
                -np.inf,
                0.0,
            ))

    for b in range(B - 1):
        constraints.append(({y[b]: -1.0, y[b + 1]: 1.0}, -np.inf, 0.0))

    A = lil_matrix((len(constraints), nvar), dtype=float)
    lhs = np.empty(len(constraints))
    rhs = np.empty(len(constraints))
    for r, (coeffs, lo, hi) in enumerate(constraints):
        for j, val in coeffs.items():
            A[r, j] = val
        lhs[r] = lo
        rhs[r] = hi

    options = {"disp": False}
    if time_limit_s is not None:
        options["time_limit"] = float(time_limit_s)

    res = milp(
        c=c,
        integrality=integrality,
        bounds=Bounds(lb, ub),
        constraints=LinearConstraint(A.tocsr(), lhs, rhs),
        options=options,
    )

    if res.x is None:
        raise RuntimeError(f"MILP did not return a solution: {res.message}")

    xsol = np.rint(res.x).astype(int)
    plans: List[BarPlan] = []
    for b in range(B):
        if xsol[y[b]] == 0:
            continue

        straight_counts: Dict[str, int] = {}
        normal_counts: Dict[str, int] = {}
        flipped_counts: Dict[str, int] = {}
        pairs: Dict[str, int] = {}
        used = 0

        for i in straight_idx:
            q = xsol[xs[(i, b)]]
            if q:
                straight_counts[parts[i].name] = int(q)
                used += q * parts[i].effective_length_mm

        for i in miter_idx:
            q0 = xsol[xm[(i, b, 0)]]
            q1 = xsol[xm[(i, b, 1)]]
            if q0:
                normal_counts[parts[i].name] = int(q0)
                used += q0 * parts[i].effective_length_mm
            if q1:
                flipped_counts[parts[i].name] = int(q1)
                used += q1 * parts[i].effective_length_mm

        for g in groups:
            q = xsol[pair[(g, b)]]
            if q:
                pairs[g] = int(q)

        plans.append(
            BarPlan(
                bar=b + 1,
                used_length_mm=int(used),
                waste_mm=int(stock_length_mm - used),
                straight=straight_counts,
                miter_normal=normal_counts,
                miter_flipped=flipped_counts,
                pairs_by_group=pairs,
            )
        )

    return SolveResult(
        objective_bars=len(plans),
        total_waste_mm=sum(p.waste_mm for p in plans),
        bars=plans,
        raw_status=int(res.status),
        raw_message=str(res.message),
    )


def demo_instance() -> List[Part]:
    """Demonstration only; replace these rows with actual shop orders."""
    return [
        Part("S-1200", demand=3, effective_length_mm=1200, kind="straight"),
        Part("S-850", demand=4, effective_length_mm=850, kind="straight"),
        Part("M-1490-DM", demand=4, effective_length_mm=1500, kind="miter", compatibility_group="45-A"),
        Part("M-990-DM", demand=2, effective_length_mm=1000, kind="miter", compatibility_group="45-A"),
    ]


def main() -> None:
    result = solve_cutting_milp(demo_instance(), stock_length_mm=6000, max_bars=10)
    print(f"Stock bars used: {result.objective_bars}")
    print(f"Total trim/waste: {result.total_waste_mm} mm")
    print(result.raw_message)
    for bar in result.bars:
        print("\nBar", bar.bar)
        print("  used / waste:", bar.used_length_mm, "/", bar.waste_mm, "mm")
        print("  straight:", bar.straight)
        print("  miter normal:", bar.miter_normal)
        print("  miter flipped:", bar.miter_flipped)
        print("  complete miter pairs:", bar.pairs_by_group)


if __name__ == "__main__":
    main()
