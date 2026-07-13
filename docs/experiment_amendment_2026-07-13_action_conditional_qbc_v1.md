# Action-conditional outcome-QBC amendment - 13 July 2026

Status: adaptive sealed template/planner treatment attempt 3, frozen before generator
implementation, behavior implementation, model inference, or environment action. Earlier
Qwen, prompt, and fixed-prior diagnostics remain separately reported and are not renumbered
as sealed template/planner treatments.

The clean pre-amendment HEAD is
`15a8200fc898d37772939b9e84c2394c6cbc3ba2`. This document must be committed and pushed
alone before the data-only lockbox generator is implemented. It must never receive an
outcome section or be edited after that commit. Registration hashes and later outcomes
belong in the append-only experiment protocol.

## Adaptive disclosure and reason for the amendment

This is a post-failure adaptive amendment, not the unchanged controller from the original
plan. The thesis-level design named action-specific query-by-committee disagreement, but
the concrete controller used one global winning-action agreement statistic for every
candidate probe. This amendment replaces that eligibility statistic with a candidate-
specific exact-outcome concentration. Its numeric cutoff remains `0.8`, but the estimand
changes, so the agreement gate is not described as unchanged.

The two predecessor treatments remain scientific failures:

- The topology-v1 canonical audit produced four eligible distinct programs but action-flat
  depth-four costs, winning-action agreement `1.0`, maximum EVSI `0.0`, and no X-only
  action.
- Path-deficit-v2 produced action-varying costs but failed its registered bridge with
  winning-action agreement `0.8417629130389278`, maximum EVSI
  `0.048123650158264475`, and no X-only action.

The second result disclosed that a probe can separate predicted exact outcomes while the
global optimal-action coalition remains above the agreement cutoff. That diagnostic
motivates the new factor but cannot admit it. The failed path-deficit scene, its weights,
and any transformed copy are excluded from every v5 acceptance denominator. In
particular, the old result remains below the unchanged synthetic materiality cutoff of
`0.05` EVSI even if a new outcome-concentration diagnostic would be favorable.

This amendment does not change or temper Gibbs weights, AST complexity, EVSI, completion
costs, catastrophe risk, candidate construction, search depth, numeric cutoffs, or budgets.
Representation/typed-IR work is deferred to a separately registered treatment if this
isolated mechanism test fails or later producer grounding remains the bottleneck.

## Frozen predecessor evidence

The following identities remain immutable negative evidence and historical replay inputs:

- Path-deficit amendment:
  `docs/experiment_amendment_2026-07-13_trajectory_deficit_v2.md`, SHA-256
  `72522d43c2069f58cc2478401c02602cfe3db557496268e1aad19bdbf9f5a0b7`.
- Path-deficit config file SHA-256
  `26b02a26a7152597eb40164a3775e23f38750ea7891af9fa20b4c327af7cb090` and
  semantic X-T SHA-256
  `de53f3dffe049ffa3a62eb49622c34f1233a0f86baf6622b42f006b9b1c1982a`.
- Path-deficit zero-run matrix SHA-256
  `949fe7a7455e3637acdeb2ec278ff9822e78a15284854fd730e47a3c84775d5e`.
- Path-deficit Linux result SHA-256
  `0a81a4a9d42bba1a80b747838bb51d06fae86827909c792d2afe5a2d14aa880a`,
  produced from clean implementation commit
  `989c3211044b7d004e43f7a84f8a4b77567568da`.
- Path-deficit cost-policy SHA-256
  `055f52473893709d88beffed0b22fa035c24af7b9da3ce24306e481cf2abc670`;
  historical endpoint-policy SHA-256
  `c12daf008d7ee6792b3ade429dacb8a65a108b9d5eb8ea8d1f5e78552dd2e95a`.
- Frozen v2 audit contract, scene, candidates, and source-manifest SHA-256 values,
  respectively:
  `d01f34cc2835a4a8b7f7257a6fc65e67c455d158356c69db744a6c50203b30ed`,
  `dfa612dbc1215319d3d2de1b8b41c9462a9dcd822ccd3b9793c0e358d216383b`,
  `86e6f48fbe0056f0913b08c1daa1d54fc3147f163e1aece8177d50c02e6a6a69`,
  and `7834f5a116c3d2e6e3b5725d9c17d982d76f8f947ebd6bc2d1ca9f405053d9d4`.
- Topology-v1 blocked report SHA-256
  `546cf508fa36e1d0ddd39b16e79c35f79fc597577609b3350add8f1c146e1033`.
- Candidate policy, compiler contract, compiler code, and canonical overlay identities
  remain the values recorded by the v2 report. They may not be edited in place.
- The public split remains SHA-256
  `0edf4f937be4ed391eb477343fd4fdee32cf6cd255092ae4f1ea617872ab1614`.

Runtime-v4 and its matrix remain permanently rejected. Reusing the exact, byte-identical
path-deficit cost policy as one fixed component of runtime-v5 neither revives nor
reclassifies the failed v2 treatment. Runtime-v5 is a distinct composite treatment and
must pass fresh evidence.

## New factor and mathematical contract

Add a typed, content-addressed planning factor:

```text
probe_disagreement_policy_version = action-conditional-outcome-qbc-v1
implementation_contract_version = crosslevel-voi-runtime-v5
outcome_concentration_threshold = 0.8
```

The policy SHA-256 must be derived from the exact implementation source, signature
contract, strict comparison, tie/order rules, and exact identities or source of weight
normalization, `Prediction.signature`, EVSI, catastrophe mass, and probe utility. It must be
explicit in every v5
configuration. The complete configuration SHA commits the policy pair inside `RunSpec` and
the run ID carries its registered eight-hex prefix. The frozen manifest must check full-
hash and prefix collisions. The policy version, hash, and threshold must also appear
explicitly in every v5 M/X decision trace, direct-fallback/refresh/lifecycle trace, metrics
summary, and audit.
The old `agreement_threshold` field and old global winning-action calculation remain byte-
compatible historical behavior for runtime-v3/v4; v5 must not silently overload that
field.

For candidate action `a`, let nonnegative normalized MDL-Gibbs committee weights be `w_i`,
with positive total mass before normalization. Let `z_i(a)` be exactly the existing EVSI
signature:

```text
z_i(a) = (next_grid, game_state, level_delta).
```

`next_grid` uses the same validated shape, dtype, and canonical bytes as current EVSI.
Program memory is excluded. If any root action fails, the existing planner invalidates that
hypothesis for the whole snapshot, gives it zero mass, and produces one shared filtered and
renormalized snapshot for costs, `A`, EVSI, and risk. No action-specific removal or
disagreement-only renormalization is permitted. The lockbox structural gate requires zero
such removals.

Cluster hypotheses by exact `z_i(a)` and define weighted committee outcome concentration:

```text
A(a) = max_z sum_{i: z_i(a) = z} w_i.
```

This is normalized Gibbs mass, not a calibrated outcome probability. Weights are normalized
with `math.fsum`; each cell mass is computed with `math.fsum`; `A` is the ordinary maximum
of those cell masses. A raw value outside `[-1e-12, 1+1e-12]` is an error; otherwise
floating residue alone is clamped to `[0,1]`. There is no EVSI-style materiality clamp for
`A`. Strict `<0.8` uses that recorded value, and equality blocks.

Hypothesis and outcome-cell permutations must preserve each diagnostic within relative and
absolute tolerance `1e-12` and preserve every threshold disposition and mapped decision.
Candidate permutations must preserve per-action diagnostics, the eligible set, the
utility-maximizer set, and probe/exploit mode. The registered candidate-order tie break is
retained. Positive lockbox rows therefore require unique probe and exploit winners with the
larger acceptance margins specified below; explicit tie controls verify the historical
order dependence rather than claiming a mapped unique action.

For both myopic M and cross-level X, filter candidates by disagreement eligibility before
selecting a probe. Among eligible candidates, select the largest utility with original
candidate order as the deterministic tie break:

```text
J_M(a) = EVSI(a) - 1 - 3 r(a)
J_X(a) = m_l EVSI(a) - 1 - 3 r(a),
r(a) = sum_i w_i 1[z_i(a).game_state = GAME_OVER].
```

`r(a)` is normalized Gibbs catastrophe mass, not a calibrated probability. M probes only
when `max_{a:A(a)<0.8} J_M(a) > 0` and the shared per-level probe cap remains. X uses the
identical rule with `J_X`. Otherwise each exploits with the existing weighted mean cost plus
`0.5` weighted standard deviation. Each v5 M/X candidate row logs `A`, EVSI, risk, both
utilities, eligibility, 1-based `m_rank` and `x_rank` among eligible actions, and Boolean
`m_selected`/`x_selected`; ranks are null for ineligible actions. Global winning-action
agreement and indifference remain diagnostic telemetry only in v5. D/S traces carry the
top-level policy identity but no fabricated QBC candidate rows.

The pure selector's `x_selected`/`m_selected` output defines the synthetic decision. In a
live trace, a refresh wrapper must also log `post_refresh_mode`; an actual probe is the
selected action plus probe post-refresh mode, not merely `Decision.mode == PROBE`.

The live policy does not add the synthetic `EVSI >= 0.05` materiality cutoff. Live
eligibility remains strict outcome concentration, positive variant-specific utility, and
the probe budget. The `0.05` cutoff remains an admission-only safeguard.

The VOI threshold theorem remains conditional on this preregistered admissibility filter:
for an eligible action, `J > 0` is exactly the one-query decision threshold under the
stated finite transfer assumptions. No claim is made that the heuristic concentration
veto is necessary for optimal probing; for example, it can reject a valuable `0.81/0.19`
outcome split. `A` is also not invariant to decision-irrelevant outcome refinement:
splitting one cosmetic exact-grid signature into several cells can lower concentration
without changing EVSI or the conditional optimal decision. It is an exact-signature
identifiability/balance heuristic, not decision consensus or a robust optimality condition.

## Factors held fixed

Treatment attempt 3 holds all of the following fixed:

- `K=4`, configured `eta=5`, `lambda=0.002`, and the exact MDL-Gibbs equation;
- exact path-deficit-v2 completion-cost implementation and hash as a substrate;
- depth `4`, beam width `8`, candidate cap `12`, and candidate ordering;
- exact EVSI clusters/costs, catastrophe coefficient `3`, action cost `1`, initial
  persistence `0.5`, Beta-Bernoulli persistence updates, and probe cap `3`;
- `A < 0.8` as a strict numeric cutoff and `EVSI >= 0.05` as the synthetic materiality
  cutoff;
- 100 ms prediction timeout and 256 MiB worker allocation headroom;
- 256 environment actions, 12,288 generated tokens, and 1,200 seconds per game;
- the frozen public split, seeds, statistical unit, development/confirmation gates, and
  source-aware comparison labels.

At each synthetic comparison, v5 M-T and X-T receive the same shared pre-action snapshot,
compiler/source programs, Gibbs weights, costs, candidate set, budgets, persistence state,
concentration policy, and pure-selector inputs. Only `m_l=1` versus the remaining-level
multiplier differs. Gameplay arms share the registered game/version, seed, initial
conditions, code, source, configuration except variant, and budgets; their realized
histories may and should diverge after X probes while M exploits. A later M-T/X-T comparison
can isolate cross-level weighting within runtime-v5; it cannot establish that v5 is superior
to the historical winning-action gate without a separately registered factorial comparison.

## Open design suite and sealed lockbox

Implementation may iterate only on an explicitly labeled open design suite. Open fixtures,
the v1/v2 failed scenes, the equal-weight hand calculation, bp35, and any transformed copy
of them cannot enter the lockbox denominator or supply a pass.

The compiler-aligned, policy-sealed lockbox contains twelve base scenes: four each from
families `homologue`, `containment`, and `reflection`. A data-only generator must be
implemented and frozen in a separate clean commit before any v5 disagreement-policy or
controller behavior code. It may emit only scenes and transform/action maps: it may not
import or call the compiler, candidate builder, planner, controller, or model, and may not
emit hypotheses, candidate lists, costs, signatures, expected diagnostics, or pass labels.
Generator tests use only disjoint open-design seeds and the same restrictions.

The generator uses a fixed 32 by 32 palette-neutral scene grammar, deterministic SplitMix64
sampling, visible connected components only, no game identifier, no recorded transition,
available actions `{ACTION3, ACTION6}`, level `1`, `win_levels=9`, and initial persistence
`0.5`. These metadata give the inherited pre-v5 bridge multiplier `m_1=23`; they were not
selected after the path-deficit near-miss.
Family construction must be declared in that generator's module-level contract before its
lockbox payloads are generated:

- `homologue`: repeated translated copies of one seeded nontrivial polyomino plus a
  separate visible target component;
- `containment`: a seeded hollow component with a visible contained component plus an
  external topology-relative component;
- `reflection`: seeded components related by one visible horizontal or vertical reflection
  plus a visible incomplete counterpart.

Colours, shapes, orientation, offsets, and legal non-overlapping placements are selected
only by the registered PRNG. No coordinate, colour, or geometry may be manually replaced
after a seed is evaluated. Rejection sampling must have a fixed attempt cap and deterministic
failure result. Every base placement must keep all non-background cells at least six rows
and six columns from the 32 by 32 boundary so every registered translation below is valid.

The finite visual transform list for every base scene is exactly:

1. one seeded bijection of all sixteen palette labels, including the background;
2. object translation by `(row_delta=3, col_delta=5)`;
3. object translation by `(row_delta=-3, col_delta=-5)`; and
4. nearest-neighbor integer scaling by two from 32 by 32 to 64 by 64, used only as a fixed
   mapped-base-action program/planner test: simple actions are unchanged and each base
   ACTION6 cell `(r,c)` maps to the top-left scaled cell `(2r,2c)`.

The generator must emit explicit forward and inverse cell/action maps. Palette and both
translations regenerate the complete frontier through the frozen candidate builder and
exercise the controller selector. Scale instead supplies the mapped base action list
directly to the unchanged programs/planner/selector; it neither calls the candidate builder
nor claims full-frontier or live-controller scale equivariance. The frozen candidate policy
may not be changed to make scaling pass. All four visual transforms are mandatory for all
twelve scenes; there is no post-outcome applicability exception. The finite table-only
order transforms are exactly candidate-list reversal,
candidate-list left rotation by one, hypothesis-list reversal, hypothesis-list left
rotation by one, and reversal of serialized outcome-cell order. Order transforms reuse the
base planning snapshot and may not start workers. Candidate permutations retain the scene's
identity action map; hypothesis permutations emit the corresponding committee-index map;
outcome-cell reversal changes only the serialized order of exact signature clusters. No
other transform enters acceptance.

Seeds are derived from UTF-8 text

```text
<public_split_sha256>|action-conditional-outcome-qbc-v1|<family>|<index>
```

by taking the first eight SHA-256 digest bytes as an unsigned big-endian SplitMix64 seed.
The registered hexadecimal seeds are:

| Family | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| homologue | `a6eecedee22d2645` | `68620ddc81520133` | `e98ab12bef9e01ec` | `3c03b39042f011e4` |
| containment | `550e3657aac91e86` | `7fd12591ea73ce88` | `a957290ff6df8e67` | `9a4897ce5e703365` |
| reflection | `bb2215d4d6f787ec` | `40e8287ce4331712` | `ed9659c3935c6429` | `343710325836c643` |

The generator may be tested on disjoint open-design seeds. After review, generate the
twelve scene payloads without running a planner, commit their hashes and the generator
source hash to the protocol, and prohibit further generator changes. Only then may v5
behavior code be implemented. No lockbox planner diagnostic may be computed before the
behavior/config/matrix freeze described below.

Failure to produce any registered seed within the fixed rejection-attempt cap is a
permanent lockbox failure. It cannot authorize a generator edit, replacement seed, reduced
denominator, or new geometry. The transform manifest must pin every payload, parameter,
forward/inverse map, and order permutation before behavior code.

## Conjunctive acceptance gate

Before lockbox execution, freeze and commit the v5 policy implementation/hash, config file
and semantic hashes, all M/X arm identities, the exact collision-free 180-row v5
development manifest with zero execution counts, audit contract, exact generator and scene
hashes, transform hashes, and every expected resource counter. The manifest's arm/config
hashes and run IDs are immutable regardless of outcome. Runtime-v5 remains hard-disabled.

All twelve base scenes must satisfy the following structural conditions:

1. Exactly four safe valid programs are supplied; four behaviorally distinct programs
   survive; at least two graded roles have action-varying depth-four costs; no selected
   program is invalid during planning.
2. Every grounding and persistent Linux worker enforces exactly 268,435,456 bytes of
   `RLIMIT_DATA` allocation headroom with no error or timeout.
3. Candidate cap, depth, beam width, weights, policy identities, and resource counters
   exactly match registration.

The unchanged compiler, not the data-only generator, supplies the four programs. Ordinary
floating diagnostics must agree across registered transforms within relative and absolute
tolerance `1e-12`. Threshold comparisons always use the raw registered computation. Except
for explicit boundary/tie controls, every scene counted as a positive pass must meet these
exact margins:

- every candidate has `|A(a)-0.8| >= 1e-9`;
- X's selected probe has `EVSI(a)-0.05 >= 1e-9` and `J_X(a) >= 1e-9`;
- on causal-subset rows, the v4 counterfactual's selected probe also has
  `EVSI(a)-0.05 >= 1e-9` and `J_X(a) >= 1e-9`;
- every disagreement-eligible candidate has `J_M(a) <= -1e-9`;
- the unique eligible X-utility maximum is separated from the runner-up by at least
  `1e-9`; and
- the unique M robust-exploitation minimum is separated from the runner-up by at least
  `1e-9`.

Both runner-ups must exist. A scene with fewer than two disagreement-eligible X actions or
fewer than two exploitation candidates fails structurally; no missing runner-up receives an
infinite gap.

Any disposition or maximizer-set change is a failure even if numeric drift is within
tolerance.

At least nine of twelve base scenes, and at least three of four in every family, must show
the actual controller-level contrast:

- X's highest-utility disagreement-eligible action has `A < 0.8`, `EVSI >= 0.05`, and
  `J_X > 0`, so X selects that probe;
- M has no disagreement-eligible action with `J_M > 0`, so M actually exploits; and
- the shared probe cap is available.

Nine of twelve means at most one miss is tolerated in each deliberately different family;
it is a finite capability criterion, not an estimate of the separate 80%-of-decision-points
mechanism gate.

An unused action that is row-wise X-only is insufficient. At least six of the nine-or-more
base scenes satisfying the preceding full admission conjunction, and at least one such
scene per family, must additionally exercise the new factor. The historical v4 global
winning-action function is pinned at source SHA-256
`5e659e6ad3a3f6e50dd4bfe709b901e29999b031ac5565c5469f0d66a216aa8a`.
On the identical raw snapshot, the offline v4 counterfactual's original-order highest-
`J_X` action must have `EVSI>=0.05` and `J_X>0`; structure and the cap must pass, and no
action may have `J_M>0`. The pinned function must return global winning-action agreement at
least `0.8`; disabling only that predicate would make v4 select its probe. This
counterfactual is a pure diagnostic over v5 lockbox snapshots. It neither executes nor
re-admits runtime-v4.

Palette and both translations must preserve the complete regenerated frontier, mapped
predictions, rolewise costs, optimal sets, `A`, EVSI, risk, both utilities, eligibility, and
actual M/X decisions. The scale diagnostic must preserve those quantities and mapped M/X
decisions only on its fixed mapped-base-action list; it supplies no candidate-frontier or
live-controller scale claim. The five table-only order transforms must preserve per-action
diagnostics, eligibility, utility
maximizer sets, and probe/exploit modes. Hypothesis and outcome-cell order must also preserve
the selected mapped action. Candidate-order transforms must preserve selected mapped
actions for positive rows because their winners are unique; an explicit tie fixture instead
verifies the registered input-order tie break and mapped maximizer set. All base scenes and
transforms are reported; no maximum-only or passing-only summary is permitted.

The following fixed negative controls must all block the claimed contrast:

1. identical signatures with `A=1`;
2. dominant outcome mass exactly `A=0.8`;
3. `A<0.8` with EVSI `0`, including fragmented cosmetic outcomes whose conditional
   optimal decision is unchanged;
4. `A<0.8` with EVSI `0.049`;
5. material positive X utility but `A>=0.8`, including the inverse case where global
   winning-action agreement is low;
6. an unused row-wise X-only candidate while X selects a different shared probe;
7. M having any positive eligible probe, including a different action from X;
8. an exhausted probe cap;
9. positive catastrophe cost sufficient to make X utility non-positive;
10. final-level multiplier `1`, which must make M and X decisions identical;
11. invalid/timeout programs, fewer than two eligible graded roles, worker-memory drift,
    or any forbidden resource use;

A separate boundary control fixes `EVSI=0.05` as satisfying the admission materiality
comparison when every other conjunct passes. A refinement diagnostic splits a dominant
cosmetic outcome cell while holding costs, EVSI, and conditional optimal decisions fixed;
it must report the resulting change in `A` and is evidence of the stated limitation, not a
robustness pass. Any registered order transform that violates the metamorphic requirements
above fails acceptance rather than being counted as a negative-control success.

Acceptance is conjunctive. Passing proves only synthetic mechanism capability. Failure of
any structural, aggregate, per-family, causal-exercise, metamorphic, negative-control,
resource, provenance, or determinism condition freezes runtime-v5.

## Execution, resources, and provenance

The sealed audit uses zero model calls, generated tokens, GPU use, environment actions,
reward observations, and RHAE observations. It has a 1,200-second whole-audit wall cap in
addition to the per-prediction and worker-memory limits.

Exactly two clean-commit Linux harness executions are preregistered:

1. the primary execution fixes the scientific disposition and writes outside the repo;
2. the replica uses the identical commit, inputs, dependencies, and canonical command
   template only to verify byte identity and is not a second independent observation.

The two executions run in isolated clean worktrees with the same relative output path. The
deterministic scientific payload excludes destination path, run label, wall-clock UTC,
hostname, and other run-specific fields. It includes a canonical command template without
the destination and deterministic dependency identities. A separate append-only execution
ledger records each actual UTC, hostname, exact command/output path, exit status, and
payload SHA-256. The two scientific payloads, not the ledger rows, must be byte-identical.

After both payload hashes are recorded, the primary bytes may be copied without executing
the harness again to the exclusive-write repository artifact path. A payload mismatch is a
determinism failure and freezes the treatment. Tests may use open fixtures but must never
execute the sealed twelve-scene contract after disposition.

Infrastructure failure is limited to a failure before any program weight, cost,
prediction signature, concentration, EVSI, utility, or decision diagnostic is exposed.
The two registered starts are the complete retry allowance. If either start fails before a
complete payload, positive admission is impossible because no matching completed pair
exists; the other start may preserve a negative or infrastructure disposition but cannot
produce a pass. No third start is allowed. Once any mechanism diagnostic exists, a failed
gate is scientific and cannot be rerun for a different outcome.

The deterministic payload records the preregistration commit/blob SHA, pre-amendment HEAD,
clean status and diff hashes, platform/Python and deterministic dependency identities,
generator/scene/config/matrix/policy/compiler/candidate hashes, all raw per-scene and
transform rows, worker telemetry, and zero resource counters. The per-execution ledger adds
the run-specific fields listed above. Duplicate executions are provenance checks, never
`n=2` evidence.

## Fail-closed implementation and authorization ladder

The first behavior-adjacent implementation change must replace the current runtime-v4
denylist with an explicit live-contract allowlist checked before source admission. The only
generally live tuple is:

```text
(implementation_contract_version = crosslevel-voi-runtime-v3,
 hypothesis_source = qwen,
 completion_cost_policy_version = endpoint-v1,
 completion_cost_policy_sha256 =
   c12daf008d7ee6792b3ade429dacb8a65a108b9d5eb8ea8d1f5e78552dd2e95a,
 probe_disagreement_policy_version = winning-action-agreement-v1,
 probe_disagreement_policy_sha256 =
   5e659e6ad3a3f6e50dd4bfe709b901e29999b031ac5565c5469f0d66a216aa8a)
```

The new policy field is projected away only when reproducing historical semantic hashes.
Runtime-v4 retains its permanent failure message. Runtime-v5, every non-Qwen source, and
every unknown/mismatched tuple remain absent from the general allowlist. All shipped
workflows must reject them before backend/client/session construction, model preflight or
grounding, environment access, agent/scorecard/run construction, matrix-row execution,
offline competition startup, or live run-artifact output. Low-level injected-backend APIs
are not standalone shipped entrypoints and may not be used to bypass this guard.

Data-only generator payloads, zero-run registration manifests, unit-test temporary files,
and the two sealed synthetic outputs are permitted only at their named authorization
stages; they are not live artifacts. The old runtime-admission entrypoint must reject v5
before reading a fixture or grounding artifact and direct callers to a new v5 audit path.
The frozen v2 `audit_source_batch` and its serialized report may not be edited or relabeled.
A new v5 audit must obtain the raw planning snapshot and call the same content-addressed
pure disagreement/selection function used by the live controller; recomputing policy
decisions from report hashes or maintaining a synthetic-only selector is prohibited.

Authorization is sequential:

1. This amendment authorizes a guard-only safety commit, then a data-only generator-source
   commit and one payload/transform-manifest freeze. After that freeze, it authorizes v5
   implementation and open-fixture unit tests only. It authorizes no sealed audit, model,
   GPU, environment, or matrix row.
2. A clean code/config/zero-run-manifest freeze authorizes only the two sealed synthetic
   executions above.
3. A complete synthetic pass may authorize one separately reviewed, artifact-pinned,
   clean-Linux canonical bp35 integration audit with the same policy function and zero
   model/environment resources. It does not automatically change the live allowlist.
4. A canonical integration pass may authorize the previously scoped fixed bp35 seed-11
   S-T/M-T/X-T pilot only through a dedicated capability that checks exact game and version,
   seed `11`, variants, config/policy/compiler/artifact hashes, budgets, and output root.
   Runtime-v5/template remains absent from the general allowlist; arbitrary CLI games and
   scorecards remain blocked.
5. Only a separately reviewed pilot pass may authorize execution of the exact 180-row
   zero-run manifest frozen before the lockbox, through a manifest-hash-scoped capability.
   It may not authorize generation, replacement, or arbitrary v5 rows. No earlier matrix is
   revived.

No stage retroactively rescues an earlier failure. If this third sealed synthetic treatment
fails, the confirmatory template/planner redesign path ends for the current paper. Any
later typed-IR or producer treatment is exploratory, separately identified, and cannot be
used to rewrite this treatment's disposition.

## Claim limits

A synthetic pass would show only that Gibbs-weighted, action-conditional exact-outcome
disagreement can coexist with material decision value and an actual X-probe/M-exploit
contrast on the locked procedural family. It would not establish calibrated weights,
transition or goal accuracy, learned induction, ARC performance, unseen generalization,
or superiority over the historical winning-action policy.

bp35 is open integration evidence. Public development and locked public confirmation games
remain engineering/internal-confirmation evidence. The private Kaggle set is the headline
unseen-generalization check. Only matched runtime-v5 M/X results can support a cross-level-
weighting claim, and only after all existing development and confirmation gates pass.
