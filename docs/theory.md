# Finite deterministic VOI theory

This note fixes the exact decision problem for which the controller's probe rule is
valid. It is deliberately narrower than ARC-AGI-3: it does not establish optimality for
an arbitrary partially observed game, and it does not treat Gibbs weights as calibrated
probabilities.

## Setup

Let `H` be a non-empty finite set of deterministic transition-and-goal programs. At the
decision time, program `h` has normalized Gibbs weight `q(h) >= 0`, with
`sum_h q(h) = 1`. Conditioning below is ordinary normalization of these decision
weights; no generative-posterior interpretation is required.

Let `B` be a finite set of exploitation plans and let `c_h(b)` be the predicted number
of actions to completion under `h`. A diagnostic action `a` has a deterministic
signature `z_a(h)` (the exact predicted next grid, game state, and level delta). It
therefore induces cells `H_z = {h : z_a(h) = z}` with

```text
p_a(z) = sum_{h in H_z} q(h),
q(h | z) = q(h) / p_a(z)  for h in H_z.
```

Zero-mass cells are omitted. Define prior and post-query Bayes decision costs with
respect to the finite weighted committee:

```text
C0 = min_{b in B} sum_h q(h) c_h(b),
C1(a) = sum_z p_a(z) min_{b in B} sum_h q(h | z) c_h(b),
EVSI(a) = C0 - C1(a).
```

`EVSI(a) >= 0`: after observing `z`, the controller could always ignore it and reuse a
prior-optimal plan. This is a decision-theoretic statement about the committee, not a
claim that a generated program is true.

At current level `l`, let its positive score weight be `w_l`, and let
`W_l^+ = sum_{j=l+1}^L w_j`. The following idealization is the explicit bridge from a
one-level EVSI to future levels:

- the program identity relevant to the decision persists to later levels with expected
  transfer factor `tau_l in [0, 1]`;
- conditional on persistence, the normalized decision improvement per unit level
  weight equals the current `EVSI(a)`;
- the probe does not otherwise improve or damage the continuation, except for one
  current-level action of cost `d(a)` and catastrophe loss `kappa` with committee
  probability `r(a)`.

These are modeling assumptions, not properties proved for ARC games. With the official
one-indexed weights `w_j = j`, `d(a) = 1`, and `kappa = 3`, define

```text
m_l = 1 + tau_l W_l^+ / w_l
    = 1 + tau_l * sum_{j=l+1}^L j / l,
J_l(a) = m_l EVSI(a) - d(a) - kappa r(a).
```

## Proposition 1: exact one-query threshold

**Proposition.** Under the setup and transfer idealization above, querying `a` and then
choosing a cell-optimal exploitation plan has lower expected weighted action loss than
acting immediately if and only if

```text
m_l EVSI(a) > d(a) + kappa r(a).
```

Equality is indifference.

**Proof.** Without the probe, the current normalized decision cost is `C0`; after the
probe it is `C1(a)`, so the current-level reduction is
`C0 - C1(a) = EVSI(a)`. By the transfer assumption, the expected future reduction,
expressed in current-level weight units, is
`tau_l (W_l^+ / w_l) EVSI(a)`. Add the two reductions and subtract the only stipulated
probe liabilities, `d(a)` and `kappa r(a)`. The difference “act now loss minus query
loss” is exactly

```text
[1 + tau_l W_l^+ / w_l] EVSI(a) - d(a) - kappa r(a) = J_l(a).
```

The query is strictly better exactly when this difference is positive. QED.

This proposition is a one-query comparison, not a Bellman-optimality theorem. In the
implementation, finite-depth search estimates `c_h`, Gibbs weights replace an unknown
prior, and later observations may create information not represented by the multiplier.

## Proposition 2: monotone remaining-mass threshold

**Proposition.** Hold `EVSI(a)`, `tau_l`, `w_l`, `d(a)`, and `r(a)` fixed, with
non-negative values and `w_l > 0`. Then `J_l(a)` is non-decreasing in `W_l^+`. Equivalently,
the minimum EVSI needed to query,

```text
T(W_l^+) = [d(a) + kappa r(a)] /
           [1 + tau_l W_l^+ / w_l],
```

is non-increasing in remaining weighted level mass. The relationship is strict when
`tau_l > 0`, `EVSI(a) > 0` for utility, and `d(a) + kappa r(a) > 0` for the threshold.

**Proof.** For `W_2 >= W_1`,

```text
J(W_2) - J(W_1)
  = tau_l EVSI(a) (W_2 - W_1) / w_l >= 0.
```

The denominator of `T` is positive and non-decreasing, proving the threshold claim.
If `tau_l = 0`, both are constant. QED.

**Corollary (final level).** At `l = L`, `W_L^+ = 0`, so `m_L = 1`; the cross-level and
myopic query rules are identical for the same costs and risk. This is also an automated
controller test.

## Constructive staged counterexample

The following finite deterministic three-level task shows that rejecting a locally
unprofitable probe can increase total weighted action cost. There are three persistent
hypotheses `H = {A, B, C}`, initially weighted uniformly. At the start of each level the
agent chooses routine `A`, `B`, or `C`. The routine matching `h` completes in one action;
either other routine completes in two. Completion deterministically reveals whether the
chosen routine matched, eliminating at least that possibility. A diagnostic action,
available only before the level-1 routine, costs one action and reveals `h` exactly. There
is no catastrophe. Level weights are `1, 2, 3`.

At level 1, every routine has expected cost `(1 + 2 + 2) / 3 = 5/3`. Perfect information
reduces the routine cost to `1`, hence `EVSI = 2/3`. A current-level-only controller sees
`2/3 - 1 < 0` and rejects the probe.

Without the probe, the level-1 routine costs `5/3` in expectation. With probability
`1/3` it identifies `h`; otherwise it leaves two possibilities. The optimal level-2
routine therefore costs

```text
(1/3) * 1 + (2/3) * [(1 + 2) / 2] = 4/3.
```

After that routine `h` is known, so level 3 costs `1`. The expected weighted total is

```text
1 * (5/3) + 2 * (4/3) + 3 * 1 = 22/3.
```

Probing first yields a level-1 cost of `2` (probe plus correct routine), followed by
known correct routines, for total

```text
1 * 2 + 2 * 1 + 3 * 1 = 7.
```

Thus the early probe saves `1/3` expected weighted action even though its level-1 net
value is `-1/3`. The controller's homogeneous-transfer multiplier (`tau_1 = 1`,
`m_1 = 6`) would accept it. Its numerical utility overestimates the saving because the
no-probe strategy learns incidentally at later completions; the sign is nevertheless
correct. This gap is why the empirical paper must report controller outcomes rather than
present the multiplier as an exact model of every ARC trajectory.

## Scope boundary

All statements above concern a finite deterministic shared-hypothesis decision model.
They do not cover unrestricted hidden state, misspecified program pools, stochastic
environments, arbitrary history dependence beyond the recorded eight frames, or the
quality of LLM proposal probabilities. A positive empirical cross-level claim remains
conditional on the frozen development and confirmation gates.
