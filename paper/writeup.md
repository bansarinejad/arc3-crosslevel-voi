# Learn Early, Exploit Late

## Subtitle

Cross-Level Value of Information for Resource-Constrained Interactive Rule Induction

> **Pre-results draft.** Bracketed fields must be filled only from frozen artifacts. The
> final Kaggle Writeup must remain between 1,400 and 1,450 words.

## Abstract — target 100 words

ARC-AGI-3 agents must infer dynamics and goals while every environmental probe reduces
action efficiency. We study premature commitment: an executable program may replay early
observations yet make the wrong counterfactual prediction. We introduce a bounded version
space of transition-and-goal programs and a controller that probes when predicted outcomes
disagree and the resulting decision improvement can carry into more heavily weighted later
levels. The linked offline submission scores **[PRIVATE RHAE]**. In a preregistered
same-backbone comparison on ten locked public games, the full controller changes mean RHAE
by **[DELTA AND 90% INTERVAL]** versus **[COMPARATOR]**. We release code, traces, and the
exact reproduction notebook.

## Introduction and prior work — target 250 words

Interactive abstraction creates an identification problem. Several world programs can be
consistent with the transitions an agent happened to observe, while recommending different
next actions. Committing to one explanation turns this underdetermination into planning
error; exploring indiscriminately instead destroys the efficiency score.

Executable World Models established code as an online dynamics representation. AERA
studied the trade-off between exploration and action efficiency. OPINE-World combined
object-centric program synthesis, replay verification, counterexample repair, and
uncertainty-directed probing. Our contribution is not executable modeling or generic active
exploration. We ask a narrower question: when several executable models remain plausible,
is their action-specific disagreement worth resolving now, given that learned mechanics can
persist into later levels whose official weights are larger?

## Method — target 400 words

The agent retains at most four restricted Python programs. Each receives the last eight
stable frames and predicts the next grid, terminal event, level delta, and a bounded goal
value. Programs are scored before the real transition is revealed using normalized grid
mismatch plus fixed event and level penalties. We call the resulting complexity-regularized
exponential weights an MDL-Gibbs version space, not a calibrated Bayesian posterior.

For every valid simple action and up to the remaining slots in a twelve-action set of
visually grounded clicks, each program performs depth-four, beam-eight search. Programs
therefore assign each action a predicted completion cost and predicted next-observation
signature. A candidate probe partitions the programs by these signatures. Its expected
value of sample information is the reduction in optimal expected plan cost after learning
which partition is correct.

At level `l` of `L`, the full controller multiplies this value by `1 + tau` times the ratio
of remaining level weight to current weight. `tau` starts at one half and updates according
to whether a pre-boundary program remains predictive for the first two transitions of the
next level. The controller subtracts one action and three times predicted game-over risk.
It probes only when this utility is positive, winning-plan agreement is below 0.8, and the
level has used fewer than three probes. Otherwise it minimizes weighted mean plan cost plus
half a weighted standard deviation.

All variants share one open-weight backbone, observations, action cap, token cap, and wall
time. Unsafe or timed-out programs receive zero weight. A collapsed pool gets a bounded
refresh; after refresh exhaustion, the same backbone selects a direct action and that route
is logged.

## Theory — target 200 words

For a finite deterministic committee, a probe partitions programs by their predicted
observation. Let `EVSI` be the reduction from the prior-optimal expected plan cost to the
expected cell-optimal cost. Under the explicit idealization that this per-weight decision
improvement transfers to later levels with factor `tau`, the difference between acting now
and probing is exactly `m_l EVSI - d - kappa r`. Therefore probing is beneficial precisely
when that quantity is positive. Holding EVSI, risk, persistence, and current weight fixed,
its derivative with respect to remaining weighted level mass is non-negative; equivalently,
the required-EVSI threshold is non-increasing. At the final level the multiplier is one, so
the rule equals myopic EVSI.

A three-hypothesis construction makes the distinction concrete. A correct routine costs
one action and either wrong routine costs two; a one-action level-1 query identifies the
persistent routine. Myopic EVSI is `2/3`, so it rejects the query. With level weights
`1,2,3`, no query costs `22/3` in expectation even after accounting for incidental learning,
whereas querying costs `7`. Thus the early query saves `1/3` weighted action. The full proof
and assumptions are in the public theory note and notebook.

The assumptions are intentionally narrow. The transfer idealization is not a Bellman theorem;
LLM proposals are not known samples from a prior, eight frames cannot identify arbitrary
hidden state, and finite-depth goal values only approximate long-horizon cost.

## Results — target 350 words

**Negative engineering gate.** A preregistered trajectory-sensitive unresolved-cost
variant produced action-varying plan costs on its generic synthetic bridge, but under the
registered Gibbs/MDL weights its agreement was `0.8417629` (required `<0.8`), maximum EVSI
was `0.04812365` actions (required `>=0.05`), and it produced no X-only probe. We froze the
variant before canonical audit, model inference, or gameplay. This is mechanism-debugging
evidence only and is not part of the controlled or private score. The conjunctive stop also
left the planned treatment-level palette/translation/scale/order metamorphic suite unrun.
At this pre-results stage, the deterministic failure awaits its one-time clean-commit
evidence artifact.

**Linked submission.** Configuration **[COMMIT/MODEL/PROFILE]** obtains private RHAE
**[SCORE]** with **[RUNTIME]** and no network access.

**Controlled comparison.** We froze fifteen development and ten confirmation games before
tuning. Seeds were averaged within game; games were the paired unit. Full results:

**[INSERT TABLE: D/S/M/X, RHAE, levels, actions, tokens, runtime, loss, fallback rate]**

Against the development-selected comparator, the full method won **[W]/10**, lost **[L]**,
and tied **[T]**. Its paired mean difference was **[DELTA]**, with 90% game-bootstrap
interval **[LOW, HIGH]**, positive-bootstrap probability **[P]**, sign-test **[P]**, and
sign-flip permutation **[P]**. **[STATE WHETHER THE CLAIM GATE PASSED; DO NOT SPIN FAILURE.]**

Mechanistically, **[REPORT VALID POOL RATE, TIMEOUTS, PREQUENTIAL LOSS, AND BOUNDARY
SURVIVAL]**. Failure cases include **[EXACT TRACE-LINKED EXAMPLES]**.

ARC-AGI-2 remains a conditional, unexecuted pipeline. Only if the ARC-AGI-3 score gate passes
may we spend the preregistered eight-hour budget, adapt on its 1,000 training tasks, and run
the untouched 120-task public evaluation once. If executed, it compares four-program and
one-program static transformation hypotheses with paired exact accuracy/McNemar analysis.
It tests only version-space transfer, not active exploration: **[INSERT GATE-PERMITTED RESULT,
OTHERWISE OMIT THIS PARAGRAPH]**.

## Limitations and conclusion — target 150 words

The 25 public games have published traces and known trivial strategies, so their results are
controlled engineering evidence rather than genuine generalization. The private score is
the only headline accuracy evidence. Exact predicted-grid partitions may overvalue harmless
pixel differences; generated programs inherit proposal bias from their backbone; bounded
history and depth miss latent or long-horizon mechanics; and the current implementation is
resource-efficient only relative to its declared hardware and budgets.

Within those limits, the study tests a concrete thesis: uncertainty should remain explicit
until an action matters, and information purchased early should be valued by the later
decisions it can improve. Every positive sentence above is conditional on the frozen claim
gates. The final submission will release every claim-bearing configuration, failure
artifact, and trace that actually exists; no absent controlled trace is implied here.
