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
`evidence-first-visible-causal-alternatives-v5`, perception contract
`arc-agi-0.9.9-color-map-scale8-grid-v1`, and implementation contract
`crosslevel-voi-runtime-v2`. The original four-row pilot used a renderer
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

### Current scale-up state — 13 July 2026

The historical corrected fair-v2 seed-11 D/S/M/X cell is complete and retained as valid negative
engineering evidence. All variants completed zero levels. M/X kept at least two programs
at every decision and had no timeout, but improved best-committee prequential loss only
7.87% over S rather than the required 15%. Their 241 non-reset planning rows had identical
cost vectors across actions, making EVSI zero and X behaviorally identical to M. The formal
X/M runtime condition passed at 0.992×; the 2.54× M/S ratio is an efficiency diagnostic,
not a preregistered gate. The other 176 fair-v2 rows were superseded and abandoned after
the goal contract changed; they are not pending. This negative result and its claim limits
remain recorded in `artifacts/pilot_bp35_seed11_fair_v2.json`.

The historical schema-v4 goal-v3 grounding gate passed on WSL and native Windows. WSL
had 2 safe programs in 2 distinct behavior classes, 1 with an action-conditioned graded
goal, and enforced hard memory ceilings for both eligible workers. Windows had 3 safe
programs in 3 distinct classes and 2 conditioned graded programs; its POSIX hard-memory
limit was unavailable and not required. The two artifacts establish functional contract
parity, not bit-identical generation.

The resulting historical goal-v3 seed-11 D/S/M/X pilot is complete and audited at
`artifacts/pilot_bp35_seed11_goal_v3.json`. Every variant completed zero levels and scored
zero RHAE. M's best prequential loss was 13.2913% below S, short of the 15% mechanism
gate, while X/M runtime was 1.00133x and passed the 1.5x condition. M and X were
semantically identical and selected no probes. The audit found that post-gate behavioral
deduplication selected a smaller ineligible candidate over its eligible conservative
equivalent, so only one live committee member satisfied the role-specific grounding
requirements. This invalidates the historical gate as admission evidence for that live
committee. Its four completed rows and the other 176 abandoned rows are preserved in
`artifacts/development_matrix_goal_v3_pilot.json`.

The current runtime filters role grounding before worker admission and deduplication,
clamps EVSI magnitudes at or below `1e-12` to zero, labels mandatory RESET decisions as
lifecycle, and separates controller-decision latency from environment latency. Its active
`development_matrix.json` has 180 pending rows with new content-addressed IDs under
implementation contract `crosslevel-voi-runtime-v2`. No row in that active matrix has
run.

The deterministic offline runtime-admission audit then re-evaluated both historical
schema-v4 source batches under the corrected ordering. In both audits every selected
program was role-eligible and planning-valid, but agreement remained 1.0, maximum EVSI
was 0.0, and maximum cross-level probe utility was -1.0. The WSL-source programs had flat
costs over all twelve candidates. The Windows-source pool contained one program with a
small 0.02246-action cost range and differing optimal sets, but no observation partition
changed the weighted optimal action, so EVSI was still zero. The gate blocked a fresh pilot. See
`artifacts/runtime_admission_goal_v3_wsl.json` and
`artifacts/runtime_admission_goal_v3_windows.json`. Scale-up remains locked while the
replacement evidence-first v5 prompt/grounding contract is tested. Its offline grounding
smoke requires two eligible graded-role programs, while the stricter runtime-admission v2
gate requires at least one material low-agreement probe with positive X utility and
non-positive M utility. The v5/runtime-v2 path adds at most one grounding-repair batch with
source-free categorical feedback. Both calls share the frozen token, wall-time, and game
batch budgets; candidate roles reset within the repair batch before admission and dedup.
These are pre-pilot diagnostics, not performance claims. No v5 model gate,
runtime-admission pass, or gameplay-pilot pass is claimed.

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
monotone agent totals, refresh invalid-program counts are per-decision deltas, mandatory
RESET decisions are recorded as lifecycle actions, controller-decision and environment
latencies are separate fields, and peak
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
