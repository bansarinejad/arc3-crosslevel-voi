# Frozen experiment protocol

## Data roles

- Snapshot the current 25 public games and their version hashes before tuning.
- Split 15 development and 10 locked confirmation games with seed `20260712`, balancing
  action modality, level count, and median human-baseline action quartiles.
- Public results are controlled engineering evidence, not external generalization.
- The linked private Kaggle score is the headline Accuracy/generalization result.

## Variants and budgets

The dated proposal-source amendment is frozen in
`docs/experiment_amendment_2026-07-13.md`. It introduces explicit Qwen (`-Q`) and
template-v1 (`-T`) arm identities without modifying the locked Qwen manifest. The clean
cross-level contrast for the new source is `M-T` versus `X-T`; cross-source comparisons are
not same-backbone evidence. The separate template manifest is registration-only until its
offline admission gate passes.

- `D`: direct model policy.
- `S`: one executable program with contradiction repair.
- `M`: four-program version space with current-level EVSI.
- `X`: four-program version space with cross-level EVSI.

Qwen arms share one model contract; template S/M/X arms share one scene compiler and
proposal-source contract. `D-Q` is contextual rather than a same-source template ablation.
All registered arms share rendered and symbolic observations, context, action cap (256),
output-token cap (12,288), and 1,200-second per-game wall-time cap. The wall cap
is the smallest round bound above `12,288 / 12 = 1,024` seconds that leaves planning and
environment overhead at the minimum accepted decoding rate. Even if every development
run reaches it, 180 runs consume 60 GPU-hours, below the preregistered 80-hour fallback
trigger. Kaggle additionally applies its global evaluator deadline and the 20% headroom
gate.

The registered source-v2 configuration freezes prompt contract
`evidence-first-visible-causal-alternatives-v5`, perception contract
`arc-agi-0.9.9-color-map-scale8-grid-v1`, implementation contract
`crosslevel-voi-runtime-v3`, and content-addressed candidate/compiler contracts. The
pre-amendment runtime-v2 Qwen matrix is audit-only. The original four-row pilot used a renderer
whose value-to-color mapping disagreed with the official toolkit; it and its manifest are
retained only as pre-grounding diagnostics and cannot enter any aggregate or claim gate.

### Canonical template-source admission

The scene-topology compiler is audited only with `configs/template_v1_x.yaml`, whose
semantic configuration SHA-256 is
`aa33d464cc7cae07607689e351bcbc9aadba61c9990d5150441dc5f31e367708` and therefore
matches the registered `X-T` arm. The audit rejects any other proposal source or controller
variant before constructing a worker. Canonical evidence must be produced from a clean
commit on Linux using `scripts/audit_scene_topology_admission.py`; every selected worker
must report an enforced `RLIMIT_DATA` hard allocation ceiling exactly 256 MiB above its
trusted baseline.

The scene-specific overlay additionally requires at least two eligible graded roles. The
underlying runtime-admission-v2 decision gate still requires at least one action with
agreement below `0.8`, EVSI at least `0.05`, positive cross-level utility, and non-positive
myopic utility. A blocked report is retained as negative mechanism evidence. A pass can
authorize only the frozen bp35 seed-11 S-T/M-T/X-T pilot after an artifact-pinned live
template producer exists; it cannot unlock the 180-row matrix, and the Qwen path must never
execute under a template label.

The canonical audit ran on 13 July 2026 from clean commit
`46bf052cd9254a8837f27db9119ffdc34c46cb65`. Its four programs were eligible, selected,
behaviorally distinct, and planning-valid; all three graded roles qualified; and each
selected persistent Linux worker enforced exactly 268,435,456 bytes of
`RLIMIT_DATA` allocation headroom. `offline=true` and `planner_error=null`. The structural
checks passed, but every program's cost vector was action-flat: agreement and indifference
were 1.0, there were no differing optimal sets, maximum EVSI was 0.0, and both maximum
myopic and cross-level utilities were -1.0. The report therefore has
`status=pilot_blocked` and authorizes zero environment actions. It is preserved at
`artifacts/template_v1_runtime_admission_v2_bp35_seed11.json`, SHA-256
`546cf508fa36e1d0ddd39b16e79c35f79fc597577609b3350add8f1c146e1033`.

### Frozen path-deficit-v2 treatment

The second dated amendment is frozen in
`docs/experiment_amendment_2026-07-13_trajectory_deficit_v2.md`. Historical runtime-v2/v3
configurations retain `endpoint-v1`, which ranks unresolved paths and maps cost from the
depth-four endpoint goal alone. The opt-in runtime-v4 treatment `path-deficit-v2` ranks by
cumulative progress deficit and maps the full unresolved trajectory into the same `[4,8]`
cost range. Its zero-run source-v2 manifest is
`artifacts/development_matrix_template_v1_path_deficit_v2.json`, SHA-256
`949fe7a7455e3637acdeb2ec278ff9822e78a15284854fd730e47a3c84775d5e`.

The preregistered generic synthetic bridge was conjunctive. Structural checks succeeded:
four valid behaviorally distinct programs survived, at least two graded programs had
action-varying depth-four costs, and optimal sets differed. With the registered Gibbs/MDL
weights, however, agreement was `0.8417629130389278` (required: `<0.8`), maximum EVSI was
`0.048123650158264475` actions (required: `>=0.05`), and no X-only action existed. The
treatment is therefore a frozen scientific failure. The scene, weights, thresholds, and
implementation must not be retuned or rerun for admission; one identical clean Linux run
is permitted only to publish the already-disposed result. The remaining planner-level
metamorphic condition was not needed after the conjunctive failure and is not claimed as
completed.

No replacement bp35 audit, producer wiring, model preflight, model call, GPU use, generated
token, environment action, reward/RHAE observation, gameplay pilot, or matrix row is
authorized. Live boundaries reject runtime-v4 before backend or environment construction,
even if its config is relabeled as Qwen. The zero-run manifest is abandoned negative
registration evidence and cannot be revived by a later treatment.

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

The pre-amendment runtime filtered role grounding before worker admission and deduplication,
clamps EVSI magnitudes at or below `1e-12` to zero, labels mandatory RESET decisions as
lifecycle, and separates controller-decision latency from environment latency. Its then-active
`development_matrix.json` has 180 unexecuted rows with content-addressed IDs under
implementation contract `crosslevel-voi-runtime-v2`. No row ran; the amendment preserves
that manifest as audit-only.

The deterministic offline runtime-admission audit then re-evaluated both historical
schema-v4 source batches under the corrected ordering. In both audits every selected
program was role-eligible and planning-valid, but agreement remained 1.0, maximum EVSI
was 0.0, and maximum cross-level probe utility was -1.0. The WSL-source programs had flat
costs over all twelve candidates. The Windows-source pool contained one program with a
small 0.02246-action cost range and differing optimal sets, but no observation partition
changed the weighted optimal action, so EVSI was still zero. The gate blocked a fresh pilot. See
`artifacts/runtime_admission_goal_v3_wsl.json` and
`artifacts/runtime_admission_goal_v3_windows.json`. Scale-up remained locked while the
replacement evidence-first v5 prompt/grounding contract was tested. Its offline grounding
smoke requires two eligible graded-role programs, while the stricter runtime-admission v2
gate requires at least one material low-agreement probe with positive X utility and
non-positive M utility. The v5/runtime-v2 path adds at most one grounding-repair batch with
source-free categorical feedback. Both calls share the frozen token, wall-time, and game
batch budgets; candidate roles reset within the repair batch before admission and dedup.
These are pre-pilot diagnostics, not performance claims. No v5 model-gate pass,
runtime-admission pass, or gameplay-pilot pass is claimed. Native Windows v5 measurements
then rejected both local backbones on grounding: 4B retained two safe distinct programs
but no eligible graded role after repair; serial 9B NF4 passed compute at 14.20 tokens/s
and 8.58 GiB but retained zero grounded-safe programs. That matrix remained locked and is
now audit-only.

After those failures, one isolated offline capability diagnostic evaluated four fixed,
history-invariant generic visual priors through a newly extracted producer-neutral source
batch path. This did not amend the then-active experiment: it used no model, generated tokens,
GPU, environment calls, gameplay, recorded-transition scoring, or proposal-budget batch.
All four sources passed sandbox, role, behavioral-distinctness, and planning checks, but
agreement was 0.84758, maximum EVSI was 0.00572 actions, maximum X utility was -0.86841,
and no X-only probe existed. Runtime admission therefore remained blocked. The priors are
not described as learned, scene-compiled, or empirically accurate; palette-tie and scale
equivariance also remain unverified. The clean-commit report is
`artifacts/structured_prior_admission_v1.json`. It is excluded from performance aggregates
and does not unlock or regenerate `development_matrix.json`.

The later scene-conditioned topology compiler likewise passed the structural portion of
the canonical Linux gate but failed its decision-relevance requirement. Four selected
programs formed four eligible behavior classes and the persistent workers met the exact
hard-memory contract, yet all four plan-cost vectors were action-invariant. Agreement and
indifference were 1.0, maximum EVSI was 0.0, both M and X maximum probe utilities were
-1.0, and no X-only probe existed. This clean-commit negative result is the artifact named
above; it leaves the fixed pilot, the template runtime, and all 180 registered template
rows locked.

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
