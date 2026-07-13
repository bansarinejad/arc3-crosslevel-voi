# Trajectory-deficit planner amendment — 13 July 2026

Status: frozen at commit `9805e9e04f0e9d1a1fb7b6f0704697b1022bb736` before any
planner implementation change, replacement admission report, model call, or environment
action.

## Reason for the amendment

The canonical template-v1 admission report is valid negative evidence. Root predictions
were behaviorally distinct and the three graded programs had action-specific depth-one goal
values, but all depth-four cost vectors were flat. The endpoint-only unresolved-path rule
discarded earlier progress: after each root action, the beam could take the same high-goal
second action and only the final goal value affected cost. This produced agreement and
indifference `1.0`, maximum EVSI `0.0`, and maximum myopic and cross-level utilities `-1.0`.

This is a planner-policy amendment, not a compiler repair. It does not alter the
scene-topology compiler, candidate frontier, runtime-admission-v2 thresholds, VOI equations,
budgets, or any historical result. The read-only counterfactual numbers observed during
diagnosis are not admission evidence and supply no acceptance threshold.

## Frozen prior evidence

The following remain byte-frozen and must continue to pass their exact digest tests:

- Template-v1 blocked report:
  `artifacts/template_v1_runtime_admission_v2_bp35_seed11.json`, SHA-256
  `546cf508fa36e1d0ddd39b16e79c35f79fc597577609b3350add8f1c146e1033`.
- Template-v1 matrix: `artifacts/development_matrix_template_v1.json`, SHA-256
  `6878b39d2379d6ffc11d45953db046883a8622ac529e3702efb679b3d9f6978b`.
- Template-v1 config: `configs/template_v1_x.yaml`, SHA-256
  `0ec730e8bd56752da905070e56d4c36dea062db4b126ca9a97e897d1f98a215a`.
- Qwen matrix: `artifacts/development_matrix.json`, SHA-256
  `ea2dbc2eec0159e63452ab805545021d5101a17882402dd3bc9869fc39241147`.
- Frozen bp35 fixture and canonical history:
  `ecb67dbe088efcc79c7b786447bf81796a42a08417d64972042571d128258d75`
  and `de73a63399b6618b7a127d69f2ea75c1b83cea4f597c1993a0267e1da17c3fb4`.
- Candidate, compiler, and template-v1 admission-overlay identities:
  `a9220009c5fd4b6da602580db439e25f9acaef74799de050a7a56e6c64bba82c`,
  `eeccd86db3346fd15d2e3dbc8e82ee2bb60e23bc30c0490750a7a0fbaa9e14e5`,
  and `2992fa00f5e688bba4cef6f5be4f101528c25896d0bb74a28346fb1685822a12`.

Runtime-v3 and the existing `endpoint-v1` policy remain available for exact historical
replay. No existing artifact, configuration hash, matrix row, or claim is reclassified.

## New planner factor

Add an explicit, content-addressed unresolved-cost policy to planning configuration:

- `endpoint-v1`: the current frozen behavior. Rank by current goal and map only the best
  depth-horizon goal with `8 - 4g`.
- `path-deficit-v2`: the treatment. Retain the same depth, beam width, action frontier, and
  predicted-completion handling, but accumulate progress deficit along unresolved paths.

For a simulated path with normalized goal values `g_1, ..., g_d`, define

```text
D_1 = 1 - g_1
D_t = D_(t-1) + 1 - g_t
```

At each expansion, rank nodes by ascending cumulative deficit, then descending current goal,
then stable insertion order. Predicted completion still returns its exact step count and a
catastrophic prediction is still pruned. If no valid node remains, cost is `8`. At the full
unresolved horizon, return

```text
c = 4 + 4 * min(D_d) / d.
```

Because each deficit term is in `[0,1]`, unresolved cost remains in `[4,8]`. At depth one,
the formula is exactly `8 - 4g_1`, so the existing one-step contract is preserved. The new
quantity is an area-under-unresolved-progress estimate: it charges delayed progress while
remaining in the preregistered unresolved-cost range.

The treatment uses implementation contract `crosslevel-voi-runtime-v4`. The old policy must
remain the default for old configurations. A new zero-run source-aware development matrix
will be generated only after code and identities are frozen and before the replacement
canonical audit. Its run IDs must remain distinct through the new configuration hashes.

## Acceptance tests frozen before implementation

All conditions below are required; none may be weakened after seeing the replacement audit:

1. **Compatibility:** `endpoint-v1` reproduces the checked-in template-v1 artifact's exact
   depth-four costs and all historical configuration/matrix hashes.
2. **Range and terminal semantics:** both policies keep unresolved costs in `[4,8]`;
   depth-one values are identical; predicted completion still costs its step number;
   catastrophe and invalid-program behavior remain fail-closed.
3. **Hand calculation:** for two equally weighted hypotheses with exploitation costs
   `A=(0,0.1)` and `B=(0.1,0)`, a two-outcome probe has EVSI `0.05`, agreement `0.5`,
   myopic utility `-0.95`, and level-1 cross-level utility `0.15` when the multiplier is
   `23`. Hypothesis and action ordering must not change the result.
4. **Delayed-progress regression:** a good-first path and a wasted-first path that reach the
   same final goal must have equal endpoint-v1 cost and strictly ordered path-deficit-v2
   cost, with the good-first path cheaper.
5. **Generic synthetic bridge:** on a palette-neutral scene containing homologous objects
   and an enclosed object, the unchanged compiler must produce four valid programs and at
   least two graded action-varying depth-four cost vectors under `path-deficit-v2`. The
   resulting snapshot must have agreement below `0.8`, EVSI at least `0.05`, and an X-only
   action under the unchanged runtime-admission-v2 rule. This is capability evidence only.
6. **Metamorphic behavior:** applicable palette permutation, unclipped translation, and
   topology-preserving integer scaling must preserve rolewise costs, optimal-set incidence,
   agreement, EVSI, and the existence of an X-only action after the corresponding action
   mapping. Candidate and hypothesis order permutations must preserve numeric diagnostics.
7. **Negative controls:** identical costs, identical outcome signatures, EVSI below `0.05`,
   agreement exactly `0.8`, final-level multiplier `1`, positive catastrophe cost, invalid
   programs, and fewer than two eligible graded roles must continue to block.
8. **Resource isolation:** synthetic and canonical audits use no model, generated token,
   GPU, environment action, reward, or RHAE observation. Canonical Linux evidence still
   requires exact `RLIMIT_DATA` allocation headroom for every selected persistent worker.

The bp35 fixture is open engineering evidence and contributes no unseen-generalization
claim. No coordinate, palette value, game ID, fixture digest, or artifact-specific branch may
enter planner behavior. The fixed runtime-admission thresholds remain unchanged.

## Authorization limits

A replacement report can authorize only separately reviewed artifact-pinned live template
producer wiring and the fixed bp35 seed-11 pilot. It cannot unlock the 180-row development
matrix. The existing non-Qwen execution guard remains hard-coded throughout this amendment.
A complete scientific failure is preserved and freezes this treatment; only infrastructure
failure before report completion may be rerun unchanged.
