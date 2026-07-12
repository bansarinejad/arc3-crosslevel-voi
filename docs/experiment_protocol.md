# Frozen experiment protocol

## Data roles

- Snapshot the current 25 public games and their version hashes before tuning.
- Split 15 development and 10 locked confirmation games with seed `20260712`, balancing
  action modality, level count, and median human-baseline action quartiles.
- Public results are controlled engineering evidence, not external generalization.
- The linked private Kaggle score is the headline Accuracy/generalization result.

## Variants and budgets

- `D`: direct model policy.
- `S`: one executable program with contradiction repair.
- `M`: four-program version space with current-level EVSI.
- `X`: four-program version space with cross-level EVSI.

All variants share the model, rendered and symbolic observations, context, action cap
(256), output-token cap (12,288), and 1,200-second per-game wall-time cap. The wall cap
is the smallest round bound above `12,288 / 12 = 1,024` seconds that leaves planning and
environment overhead at the minimum accepted decoding rate. Even if every development
run reaches it, 180 runs consume 60 GPU-hours, below the preregistered 80-hour fallback
trigger. Kaggle additionally applies its global evaluator deadline and the 20% headroom
gate.

The active hashed experiment configuration freezes prompt contract
`grounded-actions-palette-graded-goals-v3` and perception contract
`arc-agi-0.9.9-color-map-scale8-grid-v1`. The original four-row pilot used a renderer
whose value-to-color mapping disagreed with the official toolkit; it and its manifest are
retained only as pre-grounding diagnostics and cannot enter any aggregate or claim gate.

Development uses seeds `11, 23, 47`. Confirmation uses `101, 211, 307, 401, 503` and
compares `X` only to the strongest development comparator. If projected local compute
exceeds 80 GPU-hours, the frozen fallback uses the first two and first three seeds.

## Statistical unit

Average seed replicates within each game. The ten paired game differences are the
independent observations. Report mean delta, wins/losses/ties, a 90% two-stage
hierarchical bootstrap interval (resample games, then paired seed replicates within each
sampled game), bootstrap probability above zero, exact one-sided sign test, and paired
sign-flip permutation test. Never count steps or episodes as independent samples, and
fail rather than compare variants with missing or asymmetric seed cells.

## Claim gates

- Mechanism: two valid distinct programs at 80% of decisions, timeout below 1%, and
  best-committee prequential loss 15% below `S`.
- Development score: at least +0.5 RHAE points or an action-neutral extra level, positive
  on 60% of games, and no more than 1.5× `M` wall time.
- Confirmation: at least 6/10 game wins and bootstrap probability of positive mean at
  least 0.90.

Failed gates must remain in the results and force claim downgrades documented in the
paper outline.

### Current scale-up state — 12 July 2026

The historical corrected fair-v2 seed-11 D/S/M/X cell is complete and retained as valid negative
engineering evidence. All variants completed zero levels. M/X kept at least two programs
at every decision and had no timeout, but improved best-committee prequential loss only
7.87% over S rather than the required 15%. Their 241 non-reset planning rows had identical
cost vectors across actions, making EVSI zero and X behaviorally identical to M. The formal
X/M runtime condition passed at 0.992×; the 2.54× M/S ratio is an efficiency diagnostic,
not a preregistered gate. The other 176 fair-v2 rows were superseded and abandoned after
the goal contract changed; they are not pending. This negative result and its claim limits
remain recorded in `artifacts/pilot_bp35_seed11_fair_v2.json`.

The replacement schema-v4 goal-v3 grounding gate passes on WSL and native Windows. WSL
has 2 safe programs in 2 distinct behavior classes, 1 with an action-conditioned graded
goal, and enforced hard memory ceilings for both eligible workers. Windows has 3 safe
programs in 3 distinct classes and 2 conditioned graded programs; its POSIX hard-memory
limit is unavailable and not required. The two artifacts establish functional contract
parity, not bit-identical generation. The active `development_matrix.json` now contains
180 pending rows over 15 games, seeds `11`, `23`, and `47`, and D/S/M/X. No goal-v3
gameplay has run.

The maximum-shape WSL planner benchmark did not authorize concurrent committee
evaluation: its three order-alternated trials produced identical snapshots and no
timeouts, but parallel median wall time was 6.53 seconds versus 5.01 seconds serial.
Parallel evaluation remains an explicit opt-in experiment and is off by default. This
decision changes scheduling only; depth, beam width, action frontier, and budgets remain
frozen.

`evaluate_mechanism_gate`, `evaluate_development_score_gate`, and
`evaluate_confirmation_gate` consume the immutable run records and implement these
thresholds directly. The mechanism check fails closed if exact worker-call timeout
telemetry is missing; a default zero is never treated as observed evidence.

## Trace and instrumentation contract

Every action row contains the complete pre-action eight-step history, selected action,
available-action sets, revealed grid/state/level delta, decision diagnostics, Gibbs
weights, persistence estimate, prequential losses, and boundary-survival event when one
is resolved. The final `WIN` observation is ingested before the runner exits, so its
prediction loss is not silently dropped. Worker call/error/timeout counters are
monotone agent totals, refresh invalid-program counts are per-decision deltas, and peak
VRAM is the maximum of model-reported and runtime-measured peaks. Raw working traces remain
outside Git while experiments are in progress. Small content-addressed fixtures required by
tests are tracked directly; completed controlled traces are copied into the hashed release
bundle and public reproduction artifact rather than silently omitted.

## Conditional ARC-AGI-2 branch

The static ARC-AGI-2 pipeline remains disabled unless the ARC-AGI-3 development score gate
passes. Passing authorizes at most eight human hours: adapt only on the 1,000 training tasks,
keep all 120 public evaluation tasks untouched, then evaluate them exactly once. Compare
`K=4` against `K=1` with paired task outcomes, exact accuracy, and exact McNemar analysis.
This branch can support only a finite-version-space transfer claim. It cannot support an
active-exploration or ARC-AGI-3 generalization claim. No ARC-AGI-2 result currently exists.
