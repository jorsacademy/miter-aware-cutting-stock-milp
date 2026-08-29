# Miter-Aware Cutting Stock MILP

A mixed-integer linear programming model for cutting demanded metal profiles from 6000 mm stock bars while enforcing strict 45-degree miter pairing: every active miter compatibility group on a stock bar must contain equal numbers of **normal** and **flipped** pieces.

The model minimizes the number of stock bars used. Effective part length is data-driven, so extra allowance for double-miter pieces (for example nominal length + 10 mm) is included directly in capacity consumption.

See [`MATHEMATICAL_MODEL.md`](MATHEMATICAL_MODEL.md) for the complete mathematical formulation.

## Core formulation

Sets:
- `I_S`: straight-cut part types
- `I_M`: miter-cut part types
- `G`: miter compatibility groups
- `B`: candidate stock bars
- `O={0,1}`: normal / flipped orientation

Variables:
- `y_b ∈ {0,1}`: stock bar `b` is used
- `x^S_{ib} ∈ Z_+`: straight parts of type `i` on bar `b`
- `x^M_{ibo} ∈ Z_+`: miter parts of type `i` on bar `b` in orientation `o`
- `p_{gb} ∈ Z_+`: complete miter pairs of group `g` on bar `b`
- `z_{gb} ∈ {0,1}`: miter group `g` is active on bar `b`

Objective:

`min Σ_b y_b`

Demand:

- straight: `Σ_b x^S_{ib} = d_i`
- miter: `Σ_b Σ_o x^M_{ibo} = d_i`

Capacity:

`Σ_i ell_i x^S_{ib} + Σ_i Σ_o ell_i x^M_{ibo} ≤ L y_b`

Strict miter matching for every group/bar:

- `Σ_{i∈g} x^M_{ib0} = p_{gb}`
- `Σ_{i∈g} x^M_{ib1} = p_{gb}`
- `p_{gb} ≤ U_g z_{gb}`
- `p_{gb} ≥ z_{gb}`
- `z_{gb} ≤ y_b`

Therefore, if a miter group is present (`z=1`), at least one complete normal/flipped pair exists, and the normal and flipped counts are identical. An unmatched miter singleton is impossible in the strict model.

## Run

```bash
python -m pip install -r requirements.txt
python miter_cutting_stock_milp.py
pytest -q
```

## Solver

The implementation uses `scipy.optimize.milp`, which calls the HiGHS MILP solver. For larger industrial instances, Gurobi or CPLEX are recommended. A pattern-based/column-generation formulation becomes attractive when the number of orders and candidate bars grows substantially.

## Modeling scope

This aggregate formulation is exact when pieces in the same compatibility group can be reordered on a bar and only the normal/flipped balance matters. If the saw sequence requires specific **adjacency** between individual pieces, extend the model with slot-indexed assignment and adjacency binaries.
