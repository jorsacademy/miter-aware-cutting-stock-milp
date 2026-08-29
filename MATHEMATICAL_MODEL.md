# Mathematical Model — Miter-Aware Cutting Stock MILP

## 1. Problem statement

Metal profiles are cut from stock bars of fixed length `L` (typically 6000 mm). Some demanded profiles use straight cuts; others require 45-degree miter cuts. A miter-cut piece cannot be produced as an isolated orientation: within the same compatible production group and stock bar, miter pieces must be balanced as one **normal** and one **flipped/upside-down** orientation. The objective is to minimize the number of stock bars used.

The formulation below is a bar-indexed mixed-integer linear program (MILP). It is intended for instances in which pieces belonging to the same miter compatibility group may be reordered on the stock bar and the physical requirement is orientation balance rather than explicit pairwise adjacency.

---

## 2. Sets and indices

- `I^S`: set of straight-cut part types.
- `I^M`: set of miter-cut part types.
- `I = I^S ∪ I^M`: all part types.
- `B = {1,...,N}`: candidate stock bars, where `N` is a valid upper bound on the number of bars that may be required.
- `G`: set of miter compatibility groups.
- `I_g ⊆ I^M`: miter part types belonging to compatibility group `g ∈ G`.
- `O = {0,1}`: miter orientations, where `0` means normal and `1` means flipped/upside-down.

Each miter part type belongs to exactly one compatibility group in the implemented model.

---

## 3. Parameters

- `L`: stock-bar length in mm; normally `L = 6000`.
- `d_i`: required demand of part type `i`.
- `ℓ_i`: **effective** cut length of part type `i` in mm.
- `a_i`: optional cut allowance associated with part type `i`.
- `n_i`: nominal length of part type `i`, if nominal/effective lengths are stored separately.
- `U_g`: upper bound on the number of complete miter pairs of compatibility group `g` that can occur on one bar.

Effective length can incorporate additional material caused by miter geometry. For example, if a nominal 1490 mm double-miter part consumes 10 mm additional material,

`ℓ_i = n_i + a_i = 1490 + 10 = 1500 mm`.

The MILP uses `ℓ_i`, not nominal length, in stock-capacity constraints.

A safe simple value for the activation bound is

`U_g = floor((Σ_{i∈I_g} d_i)/2)`.

Tighter bounds based on stock length may improve performance.

---

## 4. Decision variables

### Stock-bar activation

`y_b ∈ {0,1}`

- `y_b = 1` if stock bar `b` is used.
- `y_b = 0` otherwise.

### Straight-cut production

`x^S_{ib} ∈ Z_+`, for `i ∈ I^S`, `b ∈ B`

Number of straight pieces of type `i` cut from stock bar `b`.

### Miter-cut production by orientation

`x^M_{ibo} ∈ Z_+`, for `i ∈ I^M`, `b ∈ B`, `o ∈ O`

Number of miter pieces of type `i` cut from bar `b` in orientation `o`.

In particular:

- `x^M_{ib0}` = number of normal pieces,
- `x^M_{ib1}` = number of flipped/upside-down pieces.

### Complete miter-pair count

`p_{gb} ∈ Z_+`, for `g ∈ G`, `b ∈ B`

Number of complete normal/flipped miter pairs of compatibility group `g` on stock bar `b`.

### Binary miter-group activation

`z_{gb} ∈ {0,1}`, for `g ∈ G`, `b ∈ B`

- `z_{gb} = 1` if at least one complete pair of miter group `g` is produced on bar `b`.
- `z_{gb} = 0` if the group is absent from bar `b`.

This is the binary variable that explicitly represents the physical on/off miter-matching condition.

---

## 5. Objective function

Minimize the total number of used stock bars:

`min  Σ_{b∈B} y_b`

This is the primary cutting-stock objective requested for production planning.

---

## 6. Demand-fulfillment constraints

### Straight-cut demand

For every `i ∈ I^S`:

`Σ_{b∈B} x^S_{ib} = d_i`

### Miter-cut demand

For every `i ∈ I^M`:

`Σ_{b∈B} Σ_{o∈O} x^M_{ibo} = d_i`

Demand is therefore met exactly, while the model is free to choose the orientation of individual demanded miter pieces as long as the matching rules are satisfied.

---

## 7. Stock-capacity constraints

For every candidate stock bar `b ∈ B`:

`Σ_{i∈I^S} ℓ_i x^S_{ib} + Σ_{i∈I^M} Σ_{o∈O} ℓ_i x^M_{ibo} ≤ L y_b`

Consequences:

1. If `y_b = 0`, no part can be assigned to bar `b`.
2. If `y_b = 1`, total effective cut length cannot exceed `L`.
3. Additional miter allowance is automatically reflected through `ℓ_i`.

---

## 8. Miter matching constraints

For every compatibility group `g ∈ G` and stock bar `b ∈ B`:

### Normal-side count

`Σ_{i∈I_g} x^M_{ib0} = p_{gb}`

### Flipped-side count

`Σ_{i∈I_g} x^M_{ib1} = p_{gb}`

Combining these two equations gives

`Σ_{i∈I_g} x^M_{ib0} = Σ_{i∈I_g} x^M_{ib1}`.

Thus the number of normal miter pieces and flipped miter pieces is identical on every bar for every compatibility group. A lone unmatched miter orientation is infeasible.

This is the mathematical expression of the shop-floor rule "one upside down, one straight/normal."

---

## 9. Binary activation constraints for miter logic

For every `g ∈ G`, `b ∈ B`:

`p_{gb} ≤ U_g z_{gb}`

`p_{gb} ≥ z_{gb}`

`z_{gb} ≤ y_b`

Interpretation:

- If `z_{gb} = 0`, then `p_{gb} = 0`; therefore no miter pair from group `g` may occur on bar `b`.
- If `z_{gb} = 1`, then `p_{gb} ≥ 1`; therefore the bar must contain at least one complete pair.
- Since normal count and flipped count both equal `p_{gb}`, activating the group forces at least one normal and one flipped miter piece.
- `z_{gb} ≤ y_b` prevents activation on an unused bar.

The binary variable does not merely label a bar; together with the pair-count equalities it enforces the physical disjunction:

**either no miter group is present, or at least one complete normal/flipped pair is present.**

---

## 10. Variable domains

`y_b ∈ {0,1}`

`z_{gb} ∈ {0,1}`

`x^S_{ib} ∈ Z_+`

`x^M_{ibo} ∈ Z_+`

`p_{gb} ∈ Z_+`

These domains make the formulation a mixed-integer linear program.

---

## 11. Optional symmetry-breaking constraint

Because candidate bars are identical, many equivalent solutions can exist. The following valid inequalities force lower-indexed bars to be used first:

`y_b ≥ y_{b+1}`, for `b = 1,...,N-1`.

They do not change the optimum but can reduce branch-and-bound symmetry.

---

## 12. Feasibility implication of strict miter matching

Under the strict formulation, the total demand in each compatibility group must be even:

`Σ_{i∈I_g} d_i` must be even for each `g ∈ G`.

If it is odd, exact one-normal/one-flipped pairing is impossible unless production is allowed to create an extra sacrificial/waste piece.

The Python implementation checks this condition before solving and reports the instance as infeasible under the strict model.

If sacrificial pieces are permitted, an extension can introduce `w_g ∈ Z_+` and penalize extra pieces in a secondary objective or explicit material-waste cost.

---

## 13. Complete compact MILP

### Minimize

`Σ_{b∈B} y_b`

### Subject to

Straight demand:

`Σ_b x^S_{ib} = d_i                                 ∀ i∈I^S`

Miter demand:

`Σ_b Σ_o x^M_{ibo} = d_i                           ∀ i∈I^M`

Stock capacity:

`Σ_{i∈I^S} ℓ_i x^S_{ib} + Σ_{i∈I^M}Σ_o ℓ_i x^M_{ibo} ≤ L y_b    ∀ b∈B`

Normal miter count:

`Σ_{i∈I_g} x^M_{ib0} = p_{gb}                      ∀ g∈G, b∈B`

Flipped miter count:

`Σ_{i∈I_g} x^M_{ib1} = p_{gb}                      ∀ g∈G, b∈B`

Binary activation upper link:

`p_{gb} ≤ U_g z_{gb}                                ∀ g∈G, b∈B`

Binary activation lower link:

`p_{gb} ≥ z_{gb}                                    ∀ g∈G, b∈B`

Bar-use link:

`z_{gb} ≤ y_b                                       ∀ g∈G, b∈B`

Optional symmetry breaking:

`y_b ≥ y_{b+1}                                      b=1,...,N-1`

Domains:

`y_b, z_{gb} ∈ {0,1}`

`x^S_{ib}, x^M_{ibo}, p_{gb} ∈ Z_+`

---

## 14. Relation to the classic Cutting Stock Problem

A classic cutting-stock model usually considers only demanded lengths and stock capacity. A largest-to-smallest placement heuristic can therefore produce a length-feasible pattern that is physically invalid for miter production.

This formulation adds orientation-aware integer variables and binary miter-group activation. Therefore a pattern is accepted only if it is both:

1. length-feasible, and
2. miter-feasible.

This explicitly goes beyond a purely geometric largest-to-smallest CSP heuristic.

---

## 15. Solver recommendations

### Current implementation

The Python code uses `scipy.optimize.milp`, backed by HiGHS. This is suitable for prototypes and many small-to-medium MILP instances.

### Larger industrial instances

Recommended commercial solvers:

- Gurobi
- IBM ILOG CPLEX

Recommended open-source alternatives:

- HiGHS
- SCIP
- CBC

For very large cutting-stock instances, a pattern-based master problem with column generation or branch-and-price is generally more scalable. In that architecture, the pricing/pattern-generation subproblem must generate only patterns satisfying the same miter-orientation compatibility rules.

---

## 16. Modeling boundary: balance versus adjacency

The current MILP enforces **orientation balance by compatibility group on each stock bar**. It does not explicitly model the physical cutting sequence or require two specific pieces to occupy consecutive positions.

If the saw process requires exact adjacency — for example, a particular normal piece must be immediately followed by a compatible flipped piece — then the model should be extended with:

- slot/position indices,
- assignment binaries,
- predecessor/successor or adjacency binaries,
- compatibility constraints between consecutive slots.

That extension is a sequencing MILP and is intentionally separate from the aggregate cutting-stock formulation implemented in this repository.
