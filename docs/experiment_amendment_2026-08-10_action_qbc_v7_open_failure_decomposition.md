# Preregistered action-QBC v7 open failure-decomposition amendment

Date frozen: 10 August 2026 (Australia/Sydney)

Status: adaptive open-fixture protocol written after the complete v6 negative result and
the explicitly disclosed pre-preregistration checks below, but before any v7 source,
registration, full diagnostic payload, compound-selector result, or extension-scene
planner result exists.

## 1. Purpose, identity, and irreversible scope

This amendment defines exactly one open-only diagnostic treatment:

- treatment: `action-qbc-v7-open-failure-decomposition-v1`;
- diagnostic system: `crosslevel-voi-open-diagnostic-v7`;
- comparison semantics: `action-qbc-v7-boundary-compound-selector-decomposition-v1`;
- registration: `action-qbc-v7-open-registration-v1`;
- scientific payload: `action-qbc-v7-open-diagnostic-payload-v1`;
- runtime identity: JSON `null`.

V7 decomposes the already observed v6 visual failures into compiler-role pairing, root
transition, planner-cost, and selector layers. It also measures whether one preregistered
compound counterfactual--integer comparison keys, dense ranks, complete tied sets, and a
canonical-action tie-break--reconciles the observed scale selector disagreements. The
counterfactual is a single treatment; v7 neither attributes an effect to any one component
nor claims that comparison quantization alone caused a reconciliation. It does not repair,
rescore, replace, or reinterpret v6.

V7 is adaptive open engineering. It has no lockbox, sealed phase, success transition,
runtime treatment, gameplay arm, development-matrix authorization, or leaderboard claim.
No result under this amendment can authorize any of them. A later experiment requires a
separately written and frozen v8 preregistration.

The following Boolean members of the top-level `authorization` object are present in every
candidate, accepted, and fallback v7 payload and are permanently `false`:

```text
lockbox_generation_authorized
sealed_execution_authorized
runtime_admission_authorized
runtime_v7_enabled
final_admission_claimed
```

No hidden, sealed, or lockbox generator of any version, freeze wrapper, lockbox artifact,
identity receipt, permit,
exposure
marker, ledger, pair-promotion program, sealed evaluator, sealed runbook, hidden seed
derivation, runtime allowlist entry, or runtime-admission file may be created or invoked
under v7. The already public data-only `generate_open_scene` helper is explicitly allowed
only where this amendment says so. Tests at the open freeze and result commits must assert
the corresponding forbidden v7 paths are absent.

## 2. Frozen prior evidence and complete disclosure

### 2.1 Immutable v6 negative result

V7 is a direct scientific descendant of the recorded v6 negative result:

- v6 result commit:
  `6a7f6fb25b7e676d6aff5aecaaa26de63e436481`;
- v6 result JSON path:
  `artifacts/action_qbc_v6_open_gate_result.json`;
- v6 result JSON SHA-256:
  `853394f0b68bddaac9b5c1840e8afa51ffeba444920b132ad45b8d53740c751d`;
- v6 failure-vector SHA-256:
  `589070b5ba1dbe5c400ec462a41ea0e8098462fc59f041b673e99da823370055`;
- v6 result document SHA-256:
  `a3bf5b20291d1b35f65b7fa20de7b9c6247ba918265eab588c6a34f66ff64c59`.

Only three of twelve v6 visual rows passed, all palette bijections. The exact observed
negative vector was:

| Family | Transform | Overflow cells | Canonical v6 reasons |
|---|---|---:|---|
| homologue | translate `(+3,+5)` | 54 | translation overflow; grid mismatch |
| homologue | translate `(-3,-5)` | 0 | grid mismatch; selector rank; M/X utility sets |
| homologue | scale 2x | 0 | selector rank; M/X utility sets |
| containment | translate `(+3,+5)` | 29 | translation overflow; grid mismatch; selector rank |
| containment | translate `(-3,-5)` | 0 | grid mismatch |
| containment | scale 2x | 0 | selector rank; M/X utility sets |
| reflection | translate `(+3,+5)` | 24 | translation overflow; grid mismatch |
| reflection | translate `(-3,-5)` | 0 | grid mismatch |
| reflection | scale 2x | 0 | M/X utility sets |

The 107 overflow cells are occurrence-weighted non-background prediction cells over ordered
action-by-role pairs, not unique grid blobs. Negative translations had no overflow and still
failed grid equality. Scale root predictions, mapped frontiers, roles, Gibbs weights, costs,
and tolerance-based numeric comparisons passed, while exact ranks or maximizer sets failed.

V7 must independently rederive the v6 comparison from the newly computed index-zero
snapshots and reproduce the exact failure-vector SHA above. It may not copy the v6 serialized
comparison into its result. Failure to reproduce it is an ordinary negative v7 diagnostic,
not permission to change the expected vector.

### 2.2 Pre-preregistration base-scene diagnostic

Before this amendment was written, one artifact-free, open-only compiler/planner snapshot
was evaluated for each of the three already public index-zero scenes. No environment,
reward, RHAE, model, GPU, hidden fixture, or extension-scene planner was accessed. All three
scenes supplied four safe programs and three action-varying roles, but none exercised the
intended X-probe/M-exploit mechanism at multiplier 23:

| Family | Structural | Mechanism | Causal | Maximum EVSI | Maximum X utility | M / X | Exploit action |
|---|---|---|---|---:|---:|---|---|
| homologue | pass | fail | false | `0.03546693328437911` | `-0.18426053445928048` | exploit / exploit | `ACTION6(row=18,col=9)` |
| containment | pass | fail | false | `0.004654031969443473` | `-0.8929572647028001` | exploit / exploit | `ACTION6(row=9,col=6)` |
| reflection | pass | fail | false | `0.01977963587013498` | `-0.5450683749868954` | exploit / exploit | `ACTION6(row=11,col=6)` |

The multiplier was `23`, catastrophe mass was zero, and positive X utility therefore
required `EVSI > 1/23 = 0.043478260869565216`. The respective EVSI shortfalls were
`0.008011327585186107`, `0.03882422890012174`, and `0.023698624999430234`.

The ephemeral compact disclosure vector was observed with canonical SHA-256
`d7028cccff1ec0deb52ead455d4ac2b688fd6e7ed2ba1c1e34c905af9f275f28`.
Because the vector itself was not retained as an artifact, this digest is disclosure only;
it is not an independent integrity gate. The exact decimal strings and actions in the table
are the prospective v7 reproduction requirements. Numeric values must reproduce within
the registered binary64 relation in section 6.1; modes and actions must match exactly. Any
mismatch is reported and cannot be tuned away. For disclosure, the discarded vector was a
family-ordered list whose conceptual fields were `family`, `structural_pass`,
`mechanism_pass`, `causal_exercise`, `max_evsi`, `max_x_utility`, `m_mode`, `x_mode`, and
`exploit_action`; the table, rather than the unrecoverable serialization details, is
authoritative for reproduction.

### 2.3 Pre-preregistration public scene generation

The nine extension scenes were generated and checked for data-only construction success
before this amendment. Their grids and transforms were not passed to a compiler, planner,
selector, controller, or scientific evaluator. They are public adaptive engineering data,
not hidden confirmation and not evidence of unseen generalization.

Index-zero uses the three previously disclosed fixed seeds. For index `1`, `2`, or `3`, the
seed is the first eight SHA-256 bytes, interpreted as an unsigned big-endian integer, of the
UTF-8 text:

```text
action-qbc-v7-open-extension-v1|<family>|<index>
```

The frozen public inventory is:

| Family | Index | Seed hex | Scene `content_sha256` |
|---|---:|---|---|
| homologue | 0 | `1020304050607080` | `a4c6b8f30db80457d4f4491a7afbdcb21fc6e122b70c56359a404346c21142ad` |
| homologue | 1 | `82c9dc349d88e442` | `738028f93692db779b6c4497c6cc5af43bfbfcce1d7062836c1224b5f46e00bb` |
| homologue | 2 | `9bec03c65cbeb80e` | `d38946e2bb1a1e27ff4c907d1b3ebef0de2429d0754c3f206641164e610dd09e` |
| homologue | 3 | `e5105aa7430099e8` | `610856638a35f9bd5f29c6ad04e72239f4bb63751f10cd2651a07619eefc7ccf` |
| containment | 0 | `2233445566778899` | `5b175e279e42d13df3af915a585504e7fe3ccdd152ff6e460731a98f99ed9365` |
| containment | 1 | `94768a51dd5a7928` | `1023edb7164487292196919ca5f97bddb93c025470801bcabfb4e031ebd4591e` |
| containment | 2 | `b416ef2617f85077` | `fab3d56c35ae1ce566b0c86e1724d057e93a5b7e34d2fd95953e44faad07f62d` |
| containment | 3 | `a1af782e839e03cc` | `1a4a02ef0a99163b712accae959707b51ba4437efe38c9dbeea0ad5d8b6b566e` |
| reflection | 0 | `3141592653589793` | `c9c8ce0a18e605e8bfcbb8b87672620238dd7c3b5b8fee5c039b958a99abdc86` |
| reflection | 1 | `cb5c43f7f4f3d98b` | `deb4ddb3ddc7e1910adf416d38ff43fd0b59971b5a296edf8a5d09f3cb5adf2e` |
| reflection | 2 | `c7812a3f9c726d1a` | `05204179a556cf2acdf0579b2a89064c4efcc24de7c25217a61eeb6a2a976fac` |
| reflection | 3 | `cfceb4850da65599` | `944dfc1f7a2d67aac00106284da290a78de78545e5bcc910bac7eda2d0638542` |

All source grids have shape `[32,32]` and expose exactly `ACTION3` and `ACTION6`. The
following data-only values complete the inputs required to reconstruct every transform
without importing the scene helper. `Palette forward` is the destination label at each
source-label index `0..15`; it is a permutation, and its sole inverse is defined by
`inverse[forward[x]]=x` for every label. Only the forward permutation is registered.

| Family | Index | Source background | Palette destination background | Palette forward |
|---|---:|---:|---:|---|
| homologue | 0 | 5 | 8 | `[4,2,3,13,1,8,10,12,5,11,14,6,9,15,0,7]` |
| homologue | 1 | 5 | 4 | `[5,12,11,8,3,4,10,0,14,7,6,1,13,9,15,2]` |
| homologue | 2 | 12 | 0 | `[9,6,12,11,15,2,10,3,5,7,14,13,0,1,8,4]` |
| homologue | 3 | 14 | 11 | `[14,12,1,3,6,13,0,15,7,10,2,4,5,8,11,9]` |
| containment | 0 | 13 | 2 | `[3,12,5,10,15,4,14,0,13,6,11,7,1,2,8,9]` |
| containment | 1 | 0 | 12 | `[12,7,1,4,9,2,0,15,8,14,13,5,11,3,6,10]` |
| containment | 2 | 13 | 3 | `[13,11,6,1,15,9,7,2,4,8,5,14,12,3,0,10]` |
| containment | 3 | 12 | 6 | `[7,1,4,11,0,3,14,2,5,15,9,12,6,13,8,10]` |
| reflection | 0 | 1 | 11 | `[10,11,6,7,8,1,4,9,3,14,2,13,0,12,5,15]` |
| reflection | 1 | 0 | 9 | `[9,2,4,15,7,14,3,6,11,5,12,10,1,13,8,0]` |
| reflection | 2 | 7 | 9 | `[2,6,14,0,8,13,5,9,1,11,4,3,15,12,10,7]` |
| reflection | 3 | 5 | 13 | `[7,6,8,5,4,13,12,1,15,3,9,0,2,10,11,14]` |

The registration producer calls exactly
`arc3_voi.action_qbc_lockbox.generate_open_scene(family, seed)` and verifies all twelve
hashes without invoking compiler, planner, selector, or controller code. Despite its legacy
module name, this is the existing public, data-only scene helper. The independent
reconstructor does not import that helper; it parses and verifies the frozen seed/hash table
and the frozen background/palette table from this document. Each diagnostic process calls the
public helper and refuses any generated
scene whose hash differs from the table. Each table value is the generated object's own
`content_sha256`: SHA-256 of canonical sorted-key compact ASCII JSON for the complete scene
object with only its top-level `content_sha256` field removed, no NaN, and no final line
feed. It is not the hash of the self-containing final JSON object. The data-only verification
on 10 August reproduced all twelve table values without a compiler, planner, or selector.

## 3. Fixed system and row inventory

### 3.1 Frozen substrate

V7 must not modify any source, configuration, lockfile, test, document, or artifact that
exists at the preregistration commit. It may import the existing generator, compiler,
grounding, worker, planner, raw selector, controller-replay, v4 counterfactual, v6 reference,
v6 audit, and canonical-JSON helpers. The open-freeze registration binds the exact preregistration Git
blob and SHA-256 identity of every imported file and every transitive local source.

The only paths that may be added between the preregistration commit `P` and open freeze `O`
are:

```text
artifacts/action_qbc_v7_open_registration.json
docs/action_qbc_v7_open_diagnostic_runbook.md
scripts/build_action_qbc_v7_open_registration.py
scripts/finalize_action_qbc_v7_open_diagnostic.py
scripts/reconstruct_action_qbc_v7_open_registration.py
scripts/run_action_qbc_v7_open_diagnostic.py
src/arc3_voi/action_qbc_v7_audit.py
src/arc3_voi/action_qbc_v7_reference.py
tests/test_action_qbc_v7_audit.py
tests/test_action_qbc_v7_registration.py
```

No existing file may be modified, renamed, or deleted. No other new path is permitted at
`O`. The open-freeze registration and independent reconstruction enforce this diff allowlist.

The raw runtime-v5 mathematics remain fixed: four hypotheses, `eta=5`,
`complexity_lambda=0.002`, depth 4, beam width 8, candidate cap 12, multiplier 23,
concentration threshold 0.8, action cost 1, catastrophe coefficient 3, robust standard
deviation coefficient 0.5, probe cap 3, and zero probes used. V7 adds diagnostic transforms
and a counterfactual comparison rule; it does not alter the raw selector or controller.

Compiler programs are paired by the exact unique role, never by list position or equal
source text. The frozen role order is:

```text
conservative_evidence
topology_contact
homology_alignment
symmetry_completion
```

Every visual row records an ordered four-entry compiler manifest whose entries contain
exactly `role`, `base_source_sha256`, and `transformed_source_sha256`. Source hashes are
evidence and need not equal one another. Missing, duplicate, extra, or unknown roles fail the
role-pairing stratum.

### 3.2 Exact 140-row inventory

All twelve public scenes are evaluated. The final inventory contains exactly 140 real rows
and no untouched scene placeholders:

- rows 0--11: twelve `base_scene` rows, ordered by family `homologue`, `containment`,
  `reflection`, then index 0--3;
- rows 12--59: four `visual_transform` rows per scene in the same scene order;
- rows 60--119: five `order_transform` rows per scene in the same scene order;
- rows 120--139: twenty `control` rows in the order below.

The four visual transform identifiers, in order, are:

```text
palette_bijection
translation_row_plus_3_col_plus_5
translation_row_minus_3_col_minus_5
scale_2_nearest_neighbor
```

The five order transform identifiers, in order, are:

```text
candidate_list_reversal
candidate_list_left_rotation_by_one
hypothesis_list_reversal
hypothesis_list_left_rotation_by_one
serialized_outcome_cell_order_reversal
```

The twenty control identifiers, in order, are:

```text
identical_signatures_A1
dominant_mass_Aeq0_8_positive_JX
A_lt_0_8_evsi0
fragmented_cosmetic_evsi0
evsi_0_049
material_positive_JX_A_ge_0_8
inverse_low_global_agreement_A_ge_0_8
unused_rowwise_x_only_X_selects_other_probe
M_positive_eligible_different_from_X
exhausted_probe_cap
catastrophe_makes_JX_nonpositive
final_multiplier_1_M_equals_X
invalid_program_structural_false
timeout_program_structural_false
fewer_than_two_eligible_graded_roles
worker_memory_drift
forbidden_resource_use
boundary_evsi_eq_0_05
cosmetic_refinement_pair
candidate_tie_pair
```

The raw fixtures and their order are bound by the existing
`arc3_voi.action_qbc_audit.preregistered_control_contract_sha256()` value
`44d08c5867f0c6842151e371263d2e25cdf550da7199c29801ed8c22f4afb9f7`.
The compound treatment reuses each exact selector-input snapshot and replaces only the
called selector function; controls with no selector call reuse the same structural record.
The one registered predicate ID per control, in the same order, has this exact meaning for
both outputs unless a raw/compound distinction is stated:

| Predicate ID | Registered diagnostic gloss |
|---|---|
| `c00_identical_ineligible_exploit` | concentration is exactly 1, M and X are ineligible, and both exploit |
| `c01_strict_cutoff_ineligible_exploit` | concentration is exactly 0.8, X utility is positive, the strict eligibility cutoff is false, and M/X both exploit |
| `c02_zero_evsi_nonpositive_exploit` | the row is eligible, EVSI is exactly zero, X utility is nonpositive, and M/X both exploit |
| `c03_cosmetic_no_decision_value` | the four cosmetic outcome cells have EVSI exactly zero and M/X both exploit |
| `c04_evsi_0049_below_materiality` | EVSI is exactly 0.049, the live X selector may probe, and the separate materiality predicate is false |
| `c05_high_agreement_blocks_probe` | X utility is positive, concentration is at least 0.8, the row is ineligible, and X exploits |
| `c06_row_agreement_blocks_probe` | global agreement is below 0.8, row concentration is at least 0.8, the row is ineligible, and X exploits |
| `c07_unused_x_row_not_selected` | the unused X-only row is not selected and the registered shared-positive M/X row is selected by both selectors |
| `c08_m_positive_breaks_contrast` | M probes `ACTION5`, X probes `ACTION6(row=0,col=0)`, and the M-exploit/X-probe contrast predicate is false |
| `c09_probe_cap_exploit` | M and X both exploit and X gate reason is exactly `level_probe_cap_reached` |
| `c10_catastrophe_nonpositive_exploit` | catastrophe mass is exactly 0.5, X utility is nonpositive, and X exploits |
| `c11_multiplier_one_equal` | multiplier 1 makes the complete M and X utility records and decisions exactly equal |
| `c12_invalid_program_structural_false` | invalid-program resource gate is false and the filtered selector completes |
| `c13_timeout_program_structural_false` | timed-out-program resource gate is false and the filtered selector completes |
| `c14_too_few_roles_structural_false` | structural gate is false for the exact fewer-than-two-eligible-graded-roles condition and selector call count is zero |
| `c15_worker_memory_drift_false` | structural gate is false for the exact worker-memory-drift condition and selector call count is zero |
| `c16_forbidden_resource_false` | structural gate is false, forbidden resources equal exactly `["model_calls"]`, and selector call count is zero |
| `c17_evsi_005_material_boundary` | EVSI is exactly 0.05, materiality is true, M exploits, and X probes `ACTION2` |
| `c18_cosmetic_refinement_invariant` | refinement changes concentration, preserves EVSI exactly zero, and preserves both complete M/X decisions exactly |
| `c19_tie_policy_split` | raw reversal preserves maximizer set/mode but changes selected action; compound reversal preserves complete tied set, dense ranks, mode, and the same canonical selected action |

The table is a human-readable gloss. The executable predicate is frozen as follows. For
every raw row and compound rows 0--18, `predicate_passes` is true exactly when the existing
evaluator returns a mapping whose `name` equals the registered control ID and whose `passes`
member is the JSON Boolean true. The existing source-bound predicate is therefore the sole
authority. Compound row 19 instead ignores that raw-specific `passes` member and requires:
`record["observed"]` has exactly `forward` and `reversed` selection objects; for each variant
key `m_decision` and `x_decision`, the corresponding `["mode"]`, `["action"]`,
`["probe_candidate"]`, `["score"]`, and `["utility_maximizers"]` values are exactly equal;
and the two `["rows"]` lists, joined by canonical JSON of each row's `["action"]`, have
identical `["m_rank"]`, `["x_rank"]`, `["m_selected"]`, and `["x_selected"]`. The action join
must be one-to-one and cover both lists. Numeric equality here means identical binary64 payload. Its raw predicate
remains the existing record's true `passes` member. These predicates, rather than
preregistered output hashes, are the control expectations. The exact fixture construction
and raw records remain content-bound by the control-contract digest and full source manifest,
so implementation cannot replace a fixture while satisfying them.
For registration, rows 0--18 use `<table-predicate-id>:legacy_record_pass` for both
`raw_predicate_id` and `fixed_predicate_id`. Row 19 uses
`c19_tie_policy_split:legacy_record_pass` and
`c19_tie_policy_split:compound_canonical_invariant`, respectively.
Words such as "exactly" in the gloss do not override the source-bound legacy predicate;
controls 1, 4, and 17 retain their immutable `math.isclose`/materiality semantics at `P`.
Only the custom compound-row-19 equation above requires identical binary64 payloads.
`M` and `X` always name their respective complete conditional decision objects.

Base row IDs are `base:<family>:<index>`. Visual row IDs are
`visual:<family>:<index>:<transform>`. Order row IDs are
`order:<family>:<index>:<transform>`. Control row IDs are
`control:<control_id>`. The registration producer assigns contiguous `row_index` values
using only the ordering above. The independent reconstructor regenerates all addresses.

The registration contains all scene hashes, transform contracts, source and destination
shapes, reconstructed action-map digests, order permutations, control fixtures, compiler
role identities, commands, counters, schemas, tolerances, and source hashes. It contains no
scientific output, prediction, cost, EVSI, utility, disposition, or expected extension-scene
result.

## 4. Scientific questions and fixed interpretation

V7 answers three bounded questions.

1. **Boundary decomposition.** Which translation mismatches are algebraically confined to
   expected support outside the known viewport, which remain within the observable window,
   and which contain both patterns?
2. **Compound selector reconciliation.** Do the v6 scale rank/set failures reproduce under
   the raw selector, and does the frozen compound fixed-key/dense-rank/canonical-tie-break
   counterfactual reconcile mapped dense ranks, complete maximizer and minimizer sets,
   gates, and decisions?
3. **Conditional selector conformance.** When actions are bijectively renamed and exact
   outcome signatures are injectively relabeled while weights, costs, and order are
   preserved, does independently recomputed selection commute with the mapping?

These questions are distinct from mechanism viability. Every base scene separately reports
whether X probes while M exploits. A transition or selector relation can pass even when the
scene has no useful probe. No selector result is evidence that hypotheses are correct or that
cross-level exploration improves gameplay.

### 4.1 Layered failure localization

For every visual row, evidence follows this prerequisite graph:

```text
registered snapshot evidence -> pipeline_integrity
(addressable action inventories + validated map) -> frontier_relation
addressable role/weight inventories -> role_weight_relation
(addressable prediction inventories + addressable roles + validated map) -> root_transition
(addressable cost inventories + addressable roles + validated map) -> planner_cost
(pipeline_integrity + frontier_relation + role_weight_relation + full root_transition + planner_cost)
  -> actual transformed-selector relations
valid base snapshot + total lifted map -> isolated_action_relabel relations
valid base snapshot + total lifted map + injective signature transform
  -> isolated_signature_pushforward relations
```

This is a partial order, not a strict linear chain. "Earliest" later in this amendment means
the set of failing nodes with no failing prerequisite ancestor in this exact graph.

`pipeline_integrity` is always evaluated. An unavailable base emits
`base_pipeline_unavailable`, an unavailable transformed snapshot emits
`transformed_pipeline_unavailable`, and an available but invalid base or transformed
inventory emits `pipeline_snapshot_invalid`; every applicable reason is retained in global
vocabulary order, including both availability reasons when both are absent.
`frontier_relation` is evaluated whenever both action
inventories and the validated registered map are addressable; otherwise it is
precondition-failed. A valid partial map missing a required source action is evaluated false
with `required_action_mapping_missing`. `role_weight_relation` is evaluated whenever both
role/weight inventories are addressable and does not require frontier passage.

`root_transition` and `planner_cost` are evaluated for every addressable mapped
action-by-role pair whenever the snapshots, roles, and validated map permit those pairs to
be enumerated. They do not require the complete frontier relation to pass. Missing required
pairs make the corresponding layer evaluated false with
`required_action_mapping_missing`. `actual_raw_selector` and `actual_fixed_selector` are
evaluated only when `pipeline_integrity` passes; frontier set, sequence, completeness, and
canonical-order preservation pass; role/weight passes; every required root pair passes the full relation; and every
required cost pair passes. Otherwise each is precondition-failed with
`not_testable_due_upstream_mismatch`.

Isolated relations have separate prerequisites: a valid base snapshot, the registered total
lifted map, and an injective signature transform. A failed isolated construction is an
evaluated construction defect with its exact construction reason, never an omitted call or
a selector-relation failure. Schema, address, or evaluator defects use the terminal rules.

Each layer has an exact four-key envelope:

```json
{
  "status": "evaluated",
  "passes": false,
  "reasons": ["observable_prediction_grid_mismatch"],
  "details": {}
}
```

`status` is exactly `evaluated` or `precondition_failed`. For either status,
`passes=true` if and only if `status=evaluated` and `reasons` is empty. A false pass always
has at least one canonical reason. Reasons are unique and use the global order in section
7.3. Scientific inequality is an evaluated non-pass. Schema, table, inventory, or evaluator
failures use the terminal rules in section 8 rather than this envelope.

An ordinary scientific mismatch is an evaluated non-pass. A downstream
precondition-failed layer is not labeled as failure of that layer. Every named detail schema
permits one canonical default form for a precondition-failed or failed-construction envelope:
the exact key set is retained; every string, hash, grid reference, numeric scalar, action,
decision, nested record, or other object value is JSON null; every count is integer zero;
every list is `[]`; and every Boolean is false. No partial detail is retained. The sole
downstream-precondition reason is `not_testable_due_upstream_mismatch`; an evaluated isolated
construction defect instead uses its named construction reason with the same default detail
object. Completed evaluated scientific relations always contain their full nondefault detail
records.

### 4.2 Registered outcome categories

Each ordered visual-transform action-by-role prediction pair is classified by the first
applicable rule into exactly one of the four categories below. Palette and scale pairs always
have zero exterior support, so `boundary_consistent_censored` can occur only for translation:

- `invalid_prediction`: either registered root prediction is null or structurally invalid;
- `invalid_prediction`: the expected relation cannot be formed because a base palette label
  is outside `0..15`, the expected scale shape is outside the registered prediction domain,
  or a structurally valid transformed prediction has the wrong registered destination
  shape;
- `fully_equivariant`: observable grid, state, and level delta match, with zero exterior
  non-background support;
- `boundary_consistent_censored`: observable grid, state, and level delta match, with
  positive expected exterior non-background support. This says only that the v6 padded
  mismatch is algebraically confined to expected cells outside the known transformed
  viewport; it does not observe the transformed hypothesis or environment outside that
  viewport;
- `interior_or_metadata_mismatch`: observable grid, state, or level delta differs, whether
  or not exterior support is also positive.

For the second invalid rule, `expected_prediction_ref` and
`observable_mismatch_mask_ref` are null, mismatch-cell count is zero, the applicable
domain/shape reason is emitted, and `passes=false`. For every evaluated
`invalid_prediction` pair, `game_state_equal` and `level_delta_equal` are the exact
comparisons only when both root predictions are structurally valid and are false otherwise.
Both expected-origin fields are non-null exactly when `expected_prediction_ref` is non-null;
they then use the registered translation origin or zero for palette and scale, and otherwise
both are null. A null mismatch-mask reference always has mismatch-cell count zero.

A root prediction is structurally valid exactly when it is constructible under the immutable
`Prediction` contract at `P`: its grid is a nonempty two-dimensional integer grid with each
dimension in `1..64`, every cell in `[-32768,255]`, and canonical signed-int16 C-order bytes;
its game state is exactly `NOT_FINISHED`, `WIN`, or `GAME_OVER`; and its level delta is a
non-Boolean JSON integer. A structurally valid base prediction with shape other than the
registered source shape is nevertheless `invalid_prediction` with
`invalid_root_prediction`. Memory is not part of the observable root relation. Structurally
valid state or level-delta values that differ from their counterpart are metadata mismatches,
not structural invalidity.

V7 reports both pair counts and expected-exterior-cell counts for all categories. The number
of expected exterior cells belonging to `boundary_consistent_censored` pairs is the only
numerator that may be described as algebraically confined outside the known viewport. For
the three index-zero positive translations, its denominator is the frozen v6 total of 107.
Exterior cells in mixed pairs are reported but cannot be called an explanation of the entire
pair failure or evidence about an unobserved exterior.

A scale row has `compound_selector_reconciled=true` exactly when all of the following are
true:

1. v6 raw failure reasons reproduce;
2. frontier, roles, weights, root predictions, and costs pass their own relations;
3. every corresponding raw `outcome_concentration`, `evsi`, `catastrophe_mass`, `m_utility`,
   `x_utility`, `exploit_mean_cost`, `exploit_standard_deviation`, and `exploit_score` is
   finite and passes the exact tolerance relation in section 6.1;
4. corresponding compound-selector integer comparison keys are exactly equal; and
5. mapped dense ranks, complete tied-maximizer sets, robust exploit minimizer sets, gate
   dispositions, and M/X decisions agree exactly under the compound counterfactual.

This Boolean is descriptive conformance under a joint counterfactual, not evidence that
fixed-point quantization caused or removed the raw mismatch. Primary compound reconciliation
is true only if all three index-zero scale rows satisfy this conjunction. Those index-zero
rows are adaptive resubstitution on the observations that motivated the rule. Extension
results are reported by row and as an open engineering replication rate; they are not an
unseen-generalization estimate. Failure of any conjunct is a negative or mixed result,
never an implementation exception.

`compound_selector_reconciled` is a derived row predicate and is not an additional serialized
visual-row field. For any scale row it is recomputed solely from the registered
`v6_reproduction`, `pipeline_integrity`, `frontier_relation`, `role_weight_relation`,
`root_transition`, `planner_cost`, and `actual_fixed_selector` envelopes using the five
conditions above. For extension scales condition 1 is omitted. "Reported by row" means that
these complete source envelopes are present and the aggregate counts apply this exact
derivation; no producer-supplied Boolean is accepted.

## 5. Authoritative transform and grid semantics

### 5.1 Canonical grid evidence

V7 uses a complete authoritative grid-evidence table with exactly `schema_version` and
`blobs`; its schema is `action-qbc-v7-grid-evidence-table-v1`. Every blob has exactly
`reference`, `encoding`, `shape`, `byte_count`, `data_base64`, and `sha256`. It retains v6's
canonical signed little-endian
16-bit, C-order representation, shape range `[1,64]`, standard padded base64, exact
`<sha256>:<rows>:<columns>:int16-le-c-v1` references, sorted unique blobs, and exact
reference-set validation. Every non-null base/transformed prediction occurrence appearing in
a root `pair_records` entry, and every expected prediction and mismatch mask that section 7.5
declares derivable, has one reference; repeated occurrences share blobs.
Null or non-derivable occurrences have JSON null references and do not create blobs.

Predictions that are present in a pipeline snapshot but excluded from root pairs because an
action is unmapped are bound by the complete snapshot digest and prediction inventory counts,
not copied into the blob table. This is the only unpaired-prediction rule and prevents both
orphan blobs and silent omission from pipeline integrity.

The validator independently decodes all referenced grids, re-encodes them canonically,
checks hashes, shapes, byte counts, reference names, occurrence identities, and the exact
absence of dangling, duplicate, or orphan blobs. The pipeline producer supplies only primitive
grid occurrences; the sole authoritative finalizer in section 7.6 derives all comparisons.

### 5.2 Canonical expected-exterior-support evidence

Translation expected exterior support uses a second table with exactly `schema_version` and
`blobs`; its schema is `action-qbc-v7-expected-exterior-support-table-v1`. Each decoded blob
is the canonical
UTF-8 JSON byte
sequence for a lexicographically sorted list of distinct signed triples
`[row, column, label]`, using sorted keys and compact separators where applicable, no NaN,
and no final line feed. Rows and columns are signed JSON integers; labels are signed 16-bit
integers. The encoding name is `signed-coordinate-label-json-utf8-v1`.

Each expected-exterior blob entry has exactly `reference`, `encoding`, `entry_count`,
`byte_count`,
`data_base64`, and `sha256`. The reference is exactly
`<sha256>:<entry_count>:signed-coordinate-label-json-utf8-v1`. Empty manifests are encoded as
the two bytes `[]` and are referenced normally. Entries are sorted by reference, unique, and
must exactly cover all row references. The validator independently decodes, parses,
canonicalizes, sorts, checks uniqueness, re-encodes, hashes, and validates the reference set.

### 5.3 Palette and scale

For palette bijection, the validator applies the registered bijection of all labels `0..15`
to every base prediction cell. A label outside that domain is an evaluated non-pass. Expected
and actual shapes, canonical grid bytes, game state, and level delta must match exactly.

For scale 2x, the validator repeats every base row and column exactly twice. The expected
shape is `(2H,2W)` and must remain in the registered 64-by-64 prediction domain. Simple
actions are unchanged and each base `ACTION6(row=r,col=c)` maps to
`ACTION6(row=2r,col=2c)`, the top-left cell of its 2-by-2 block. Scale uses the mapped base
frontier and makes no complete candidate-builder equivariance claim.

### 5.4 Translation without inventing unobserved cells

For an `H x W` base prediction `G`, background label `b`, and registered translation
`(dr,dc)`, use the augmented coordinate plane with origin
`(-abs(dr), -abs(dc))` and shape
`(H + 2*abs(dr), W + 2*abs(dc))`. Coordinates are expressed in the original grid frame.
The full expected transform places each base cell `(r,c)` at `(r+dr,c+dc)` and fills every
other augmented coordinate with `b`.

The transformed pipeline must predict exactly the original `H x W` viewport; any other shape
is an evaluated `transformed_prediction_shape_mismatch`. For the valid-shape case it predicts
only the known original viewport
`[0,H) x [0,W)`. V7 does not clip, wrap, drop, or assume background for any unknown exterior
cell. It compares expected and actual canonical values only inside that known viewport and
stores the exact 0/1 mismatch mask in the grid table. It stores every expected exterior
non-background cell as a signed `(row,column,label)` triple in the
expected-exterior-support table.

For each pair:

- `observable_transition_pass` is true exactly when the known-window grid has no mismatch
  and game state and level delta match exactly;
- `exterior_nonbackground_count` is the expected-support manifest entry count;
- `full_transition_pass` is true exactly when `observable_transition_pass` is true and the
  exterior count is zero.

A row with positive expected-exterior count may pass the observable relation but never the full
finite-grid relation. It is described as boundary-consistent and censored, never as full
equivariance. A row with zero exterior count and a known-window mismatch is genuine
observable non-equivariance.

### 5.5 Action maps and frontiers

Every visual transform has an exact contract object with exactly `schema_version`, `family`,
`scene_index`, `transform_name`, `source_shape`, `actual_destination_shape`,
`isolated_destination_shape`, `source_background_label`,
`destination_background_label`, and `parameters`. `schema_version` is
`action-qbc-v7-transform-contract-v1`. The source shape is always `[32,32]`. Palette has
actual and isolated shape `[32,32]` and parameters exactly
`{"forward_palette":[<16 registered integers>]}`. Translation has actual shape `[32,32]`,
isolated shape `[38,42]`, unchanged destination background, and parameters exactly
`{"delta_row":3,"delta_col":5}` or `{"delta_row":-3,"delta_col":-5}`. Scale has actual
and isolated shape `[64,64]`, unchanged destination background, and parameters exactly
`{"factor":2}`. `contract_sha256` is SHA-256 of the canonical sorted-key compact ASCII JSON
bytes of this object, with no NaN and no final line feed.

One action-map hash preimage is an object with exactly:

```text
schema_version, map_kind, transform_contract_sha256, source_shape,
destination_shape, simple_actions, action6_forward
```

Its schema is `action-qbc-v7-action-map-v1`; `map_kind` is `actual` or `isolated`;
`simple_actions` is exactly `["ACTION3"]` and every listed simple action maps identically to
itself; `action6_forward` is a list of exact entries
`[[source_row,source_col],[destination_row,destination_col]]`. Entries are ordered by
ascending source row then source column. The digest is SHA-256 of canonical sorted-key
compact ASCII JSON for that object with no final line feed. These are array-index
coordinates in their named destination shape, not augmented-plane world coordinates.

The complete maps are reconstructed as follows:

- palette actual and isolated: all 1,024 source coordinates map identically to themselves;
- translation actual: include source `(r,c)` exactly when `(r+dr,c+dc)` is in
  `[0,32) x [0,32)`, and map it to that destination coordinate;
- translation isolated: include all 1,024 sources and map `(r,c)` to augmented-array index
  `(r+abs(dr)+dr,c+abs(dc)+dc)`. The array's world-coordinate origin is
  `(-abs(dr),-abs(dc))`;
- scale actual and isolated: include all 1,024 sources and map `(r,c)` to `(2r,2c)`.

The validator reconstructs these lists; it never trusts a supplied map. A malformed,
noncanonical, duplicate-source, duplicate-destination, out-of-range, extra, or
reconstruction-unequal map is the global `transform_action_map_invalid` failure. Total maps
must cover all 1,024 source coordinates. The actual translation map is intentionally the
registered partial injection above; a realized base-frontier action absent from it makes
`frontier_relation` evaluated false with `required_action_mapping_missing` and makes the
actual selector layers precondition-failed. It is not a global map defect. Isolated tests
require the total lifted map to be bijective over their exact candidate frontier.

## 6. Planner and selector diagnostics

### 6.1 Root predictions and costs

All predictions are paired by compiler role. Root-transition comparisons are per mapped
action and role and separately retain grid, game-state, and level-delta results. No list
index can silently substitute for role identity.

Rolewise depth-four costs are compared over the exact mapped frontier. For finite binary64
values `x` and `y`, the relation passes exactly when
`abs(x-y) <= max(1e-12, 1e-12 * max(abs(x), abs(y)))`. The boundary is inclusive. Raw values,
absolute differences, and the computed bound are retained. A tolerance pass is a
planner-cost relation only; it does not make raw exact ties or ranks equal. Every other
numeric-tolerance statement in v7 uses this same formula.

Gibbs weights are paired by role. Their raw values must be finite, normalized, and agree
within the same `1e-12` tolerances. Weight, cost, and prediction failures are reported in
their own layers.

### 6.2 Frozen raw selector

The existing raw selector is called without modification. It computes raw binary64 EVSI,
costs, utilities, and robust exploit scores; ranks eligible utilities with exact binary64
ordering and candidate index as the exact-tie break; and identifies maximizers with exact
binary64 equality. V7 preserves its raw rows, ranks, sets, gates, and M/X decisions.

Actual raw selector comparison reports numeric tolerance relations and exact relations
separately. A numeric tolerance pass can coexist with a rank or maximizer-set failure; v7
must not collapse those facts into one Boolean.

### 6.3 Frozen compound selector counterfactual

The counterfactual is compound. Predictions, normalized weights, outcome partitions, EVSI
values, catastrophe masses, eligibility values, costs, and unquantized utilities come from
the frozen raw path. It then jointly changes four comparison-policy elements: binary64
values are compared through fixed integer keys; ranks are dense; all key-tied minimizers and
maximizers are retained; and a required singleton is selected by canonical action order
instead of candidate index. Any difference is attributable only to this complete compound
rule.

The quantum is exactly `q = 2^-40`. It was selected after inspection of the completed v6
index-zero failures because it is smaller than the inherited `1e-12` diagnostic tolerance
and more than three orders of magnitude below the inherited `1e-9` mechanism margins, but
before any v7 extension result. The scale target, quantum, dense-rank rule, complete tied
sets, and canonical-action tie-break are therefore adaptive; index-zero results are
resubstitution and indices 1--3 are open synthetic engineering replications. For each finite
binary64 value `x`, its fixed key is the
nearest integer to `x / q`, with exact ties rounded to the even integer. The implementation
must derive the key from `x.as_integer_ratio()` using integer arithmetic; binary floating
multiplication, decimal text rounding, platform rounding mode, and epsilon adjustment are
forbidden.

Fixed keys are used only for:

- ascending robust exploit-score comparison;
- descending M-utility and X-utility comparison;
- complete minimizer and maximizer membership;
- dense rank assignment; and
- the positive-utility gate against integer key zero.

Eligibility remains the raw strict comparison `outcome_concentration < 0.8`. Dense rank 1
contains every eligible action with the largest utility key; the next distinct key has rank
2. The exploit minimizer and both utility maximizer sets contain all actions tied by key.
When a single action is required, choose the first member under canonical action order:
official action-kind order `ACTION1` through `ACTION7`, followed for `ACTION6` by ascending
row then column; non-`ACTION6` actions never carry coordinates. `RESET` is excluded. The
registered public scenes themselves expose only `ACTION3` and `ACTION6`.

A fixed decision has exactly `action`, `mode`, `score`, `gate_reason`, and `probe_candidate`.
If no action is eligible, it exploits with the raw robust exploit score and reason
`no_disagreement_eligible_action` and `probe_candidate=null`. If the cap is exhausted, it exploits with reason
`level_probe_cap_reached` and retains the canonical first top-key action as
`probe_candidate`. If the largest utility key is at most zero, it exploits with reason
`nonpositive_fixed_utility` and retains that same probe candidate. Otherwise it probes with
reason `selected`. A probed decision's score is the selected action's unquantized raw utility;
every exploit decision's `action` is the canonical first member of the complete minimum
exploit-key set and its `score` is that action's unquantized raw robust exploit score. Tied sets are
serialized in canonical action order.

The counterfactual is identified as
`action-qbc-v7-compound-selector-2^-40-dense-canonical-v1`. It is diagnostic only and must never be called
by a controller or runtime entrypoint.

For compatibility with already drafted schema names, JSON fields and counters beginning
`fixed_` denote this complete compound selector, not an isolated fixed-point ablation.

### 6.4 Isolated selector relations

For every visual transform, two transported snapshots are constructed from the base
snapshot and evaluated by independently calling both raw and compound selectors:

1. `action_relabel`: bijectively rename every action and every action-keyed prediction and
   cost row through the isolated lifted map; preserve candidate order, roles, weights,
   predictions, and costs exactly.
2. `signature_pushforward`: start from `action_relabel`, then apply the registered injective
   grid transform to every base prediction. Palette uses the label bijection, scale uses
   nearest-neighbor repetition, and translation uses the complete augmented-plane shift, not
   a viewport crop. Preserve state, level delta, roles, weights, and costs.

For palette and scale, the isolated lifted map equals the registered map. For translation,
it is deliberately total on the finite base frontier: simple actions remain fixed and
`ACTION6(r,c)` maps to augmented-plane coordinate
`(r + abs(dr) + dr, c + abs(dc) + dc)`. Its destination shape is the augmented shape in
section 5.4. This is distinct from the actual finite-viewport partial map and is labeled
accordingly. All four lifted maps are bijective over the exact base candidate sequence and
preserve canonical action order.

Each grid transform must be proven injective over the exact prediction-signature domain
before the pushforward selector is called. These tests ask whether selection commutes with
an action bijection and an injective relabeling of exact outcome cells. They do not compare
to the actual transformed compiler or establish spatial equivariance.

The complete augmented translation signature has origin `(-abs(dr),-abs(dc))`, registered
shape, canonical `int16-le-c-v1` bytes, unchanged game state, and unchanged level delta.
Palette and scale use their canonical grid encodings with unchanged state and level delta.
The base raw and compound selection computed for the base row may be reused as the left member;
each transported snapshot is independently selected once. With a valid base pipeline these
maps and signature transforms are total and injective by construction, so all 96 raw and 96
compound isolated calls occur. Isolated relations use exact equality, not the `1e-12`
relation. Every corresponding finite scalar must have the identical IEEE-754 binary64
64-bit payload; integer keys, eligibility, ranks, tied sets, gates, probe candidates,
actions, modes, and decisions must agree exactly after mapping. Candidate sequence order is
unchanged. The `1e-12` relation applies only to actual transformed-pipeline comparisons. A
failed construction is an evaluated construction defect with its exact reason, not an
outcome-dependent call omission.

### 6.5 Order and control rows

The five order transforms are evaluated under both raw and compound selectors. Candidate-order
changes retain exact action identity, hypothesis-order changes carry the exact role map, and
outcome-cell reversal changes serialization only. Every per-action diagnostic, tied set,
dense rank, gate, and mapped decision required by the relevant selector must be reported.

The twenty controls preserve their frozen raw meanings and exact fixture contract. Execution
must reproduce
`arc3_voi.action_qbc_audit.preregistered_control_contract_sha256()` as
`44d08c5867f0c6842151e371263d2e25cdf550da7199c29801ed8c22f4afb9f7` and obtains the raw
records through the existing `evaluate_preregistered_controls` with
`continue_after_failure=false`. Compound checks run that same function and exact internal
fixture builders while holding a v7 process-wide lock, temporarily replacing only the module
global `ACTION_QBC_AUDIT_SELECTOR` with the registered compound callable, and restoring it in
a `finally` block. The raw run uses the main borrowed legacy counter state. The compound run
uses a fresh compound-only legacy counter state; it must end with
`pure_selector_calls=pure_selector_control_calls=19`,
`pure_selector_scene_order_calls=0`, and every other legacy field zero. Its control-call
value is copied once to v7 `fixed_selector_control_calls` and no other field is merged into
the main adapter. Thus compound injection cannot inflate raw counters. No fixture is
serialized, copied, or reconstructed separately. They
additionally verify exact tie-to-even boundaries, dense ties,
complete minimizer/maximizer sets, canonical action choice, and the zero-key utility gate.
Controls with no selector invocation remain resource/schema controls under both treatments.
The qualitative predicates are exactly the table in section 3.2; no output hash chosen after
execution is an expectation.

The substitution sequence is exact: acquire the sole lock
`action-qbc-v7-control-selector-substitution-lock-v1`; assert the module global is the
registered raw callable; run raw controls once on the main legacy state; create the fresh
compound-only counter state; assign the compound callable; run compound controls once; in a
`finally` block restore the saved raw callable and assert object identity; then release the
lock. The compound-only state is never passed to the main field map and only its validated
control count enters the derived destination in section 10. Any lock, identity, restoration,
or counter-routing failure is global `evaluator_internal_error`.

## 7. Exact output boundary

### 7.1 Top-level payload

The canonical scientific payload is a JSON object with exactly these nineteen keys:

```text
schema_version
treatment_id
diagnostic_system_id
comparison_semantics_id
runtime_id
preregistration_identity
v6_negative_identity
registration_identity
execution_identity
resource_counters
grid_evidence
expected_exterior_support
rows
aggregates
diagnostic_complete
scientific_capability_passes
authorization
terminal_fallback_stage
candidate_payload_size_bytes
```

`runtime_id` is null. `authorization` has exactly the five permanently false keys in section
1. The identity objects bind the exact preregistration commit/blob, v6 anchors, registration
content/file hashes, open-freeze commit/tag, complete source manifest, Python/platform,
`uv.lock`, and canonical command template. Process label, output path, clone path, virtual
environment path, PID, hostname, UTC, and elapsed time are excluded.

`scientific_capability_passes` is permanently false because v7 defines no capability or
admission gate. Scientific outcomes live in `aggregates`, including exact v6 reproduction,
boundary categories, compound-selector reconciliation, isolated theorem conformance, and
base mechanism. `diagnostic_complete` is true exactly when all 140 registered addresses are
present; all rows and evidence tables validate; every required scientific stratum is either
evaluated or explicitly precondition-failed; all counters match; all forbidden-resource
counters are zero; no terminal exists; and none of these construction-defect reasons occurs:
`base_pipeline_unavailable`, `transformed_pipeline_unavailable`, `pipeline_snapshot_invalid`,
`isolated_action_map_not_bijective`,
`isolated_action_map_not_canonical_order_preserving`,
`isolated_signature_transform_not_injective`, `resource_counter_mismatch`, or
`forbidden_resource_use`. Ordinary registered scientific non-passes--including grid,
metadata, cost, selector, frontier, and `required_action_mapping_missing` results--and their
downstream `not_testable_due_upstream_mismatch` envelopes do not by themselves make the
diagnostic incomplete. A complete scientific negative is a successful diagnostic.

Canonical JSON is UTF-8 with sorted object keys, compact separators, no NaN or infinity, and
no final line feed.

### 7.2 Uniform final row

Every final row has exactly five keys:

```json
{
  "address": {
    "row_index": 0,
    "row_id": "base:homologue:0",
    "kind": "base_scene"
  },
  "registered_row": {},
  "disposition": "completed",
  "evidence": {},
  "terminal": null
}
```

Allowed dispositions are exactly:

```text
completed
terminal_addressable_negative
terminal_global_negative
```

`registered_placeholder` exists only in the registration's zero-result inventory and is not
a valid final-row disposition. A terminal object has exactly `status` and `stage`; evidence
is the empty object for terminal rows. A completed row has a null terminal. The authoritative
validator injects `registered_row` from the registration. A producer is forbidden to supply
that field; presence at a valid address is a localized scientific-record schema failure.

Addressability is decided before scientific evidence is inspected. An address is valid only
when its exact three fields jointly equal one frozen registration row. A valid address with
malformed evidence becomes an identity-bound `terminal_addressable_negative`, with status
`authoritative_derivation_error` and stage `scientific_record_schema_invalid`; valid siblings
are retained. A missing, malformed, conflicting, duplicated, unregistered, or omitted
address invokes the global inventory fallback.

### 7.3 Exact identities, actions, selections, and reason order

The four identity objects have these exact keys:

```text
preregistration_identity:
  commit_sha, tag, document_path, document_git_blob_sha1, document_sha256
v6_negative_identity:
  result_commit_sha, result_json_path, result_json_sha256,
  failure_vector_sha256, result_document_sha256
registration_identity:
  schema_version, path, content_sha256, file_sha256
execution_identity:
  open_freeze_commit_sha, open_freeze_tag, source_manifest_sha256,
  python_version, python_implementation, platform_system, platform_machine,
  uv_version, uv_lock_sha256, canonical_command_sha256
```

All SHA-256 values are lowercase 64-hex strings and Git SHA-1 values are lowercase 40-hex
strings. The exact environment values are `python_version="3.12.13"`,
`python_implementation="CPython"`, `platform_system="Linux"`,
`platform_machine="x86_64"`, and `uv_version="0.11.28"`.

An action object has exactly `kind`, `row`, and `col`. `kind` is an official uppercase action
name. `ACTION6` has integer row and column in its registered grid domain; every other action
has null row and column. A decision object has exactly `action`, `mode`, `score`,
`gate_reason`, and `probe_candidate`; its two action-valued fields use that action schema or
are null where permitted. A selection's action sets are duplicate-free lists sorted by the
canonical action order in section 6.3.

The sole exception is `raw_control.details.observed` and
`fixed_control.details.observed`, which preserve the source-bound legacy control record as an
opaque canonical JSON value. Its nested immutable `_action_json` objects use integer action
kinds and are not interpreted under the v7 uppercase action-object schema. Only the exact
control predicates in sections 3.2 and 6.5 inspect those opaque paths.

The global scientific reason vocabulary and order are exactly:

```text
no_prepreregistered_observation
base_pipeline_unavailable
transformed_pipeline_unavailable
pipeline_snapshot_invalid
required_action_mapping_missing
mapped_frontier_set_mismatch
mapped_frontier_sequence_mismatch
action_map_not_canonical_order_preserving
compiler_role_mismatch
gibbs_weight_nonfinite
gibbs_weight_mismatch
invalid_root_prediction
prediction_label_outside_palette_domain
scale_output_shape_outside_prediction_domain
transformed_prediction_shape_mismatch
observable_prediction_grid_mismatch
expected_exterior_support_present
prediction_game_state_mismatch
prediction_level_delta_mismatch
rolewise_cost_nonfinite
rolewise_cost_mismatch
raw_selector_numeric_mismatch
raw_selector_eligibility_mismatch
raw_selector_rank_mismatch
raw_selector_set_mismatch
raw_selector_gate_mismatch
raw_selector_decision_mismatch
fixed_selector_key_mismatch
fixed_selector_numeric_mismatch
fixed_selector_eligibility_mismatch
fixed_selector_dense_rank_mismatch
fixed_selector_set_mismatch
fixed_selector_gate_mismatch
fixed_selector_decision_mismatch
isolated_action_map_not_bijective
isolated_action_map_not_canonical_order_preserving
isolated_signature_transform_not_injective
v6_failure_vector_mismatch
prepreregistered_base_observation_mismatch
structural_gate_failed
mechanism_gate_failed
causal_diagnostic_false
order_relation_mismatch
control_expectation_mismatch
resource_counter_mismatch
forbidden_resource_use
not_testable_due_upstream_mismatch
```

No other reason string is valid. An evaluated layer lists every applicable failed reason in
this order. A downstream precondition-failed layer uses exactly
`["not_testable_due_upstream_mismatch"]`; an index 1--3 base
`prepreregistered_reproduction` layer uses exactly
`["no_prepreregistered_observation"]`. The visual-row v6 extension no-op follows section
7.4 and is reason-free. A reason-free evaluated layer passes. There is no
maximum-only, first-reason-only, or exception-message reason.

Reason emission is mechanical. Pipeline availability/schema predicates emit their named
pipeline reasons. Frontier missing/set/sequence/order predicates emit the corresponding four
frontier reasons. Role identity, nonfinite weight, and tolerance failures emit the three
role/weight reasons. Root records emit `required_action_mapping_missing` when applicable and
each applicable invalid/domain/shape/grid/exterior/state/delta reason in vocabulary order.
Planner records emit the missing-map, nonfinite, and tolerance reasons. An actual or isolated
raw selector relation maps its nonzero numeric, eligibility, rank, set-or-selected-membership,
gate, and decision counts to the corresponding `raw_selector_*` reasons; a compound relation maps nonzero key,
numeric, eligibility, dense-rank, set-or-selected-membership, gate, and decision counts to the corresponding
`fixed_selector_*` reasons. Failed isolated premises emit their named isolated reason and do
not additionally emit selector mismatch reasons. V6, preobserved-base, structural,
mechanism, causal, order, control, and resource predicates emit their same-named reasons.
An order relation uses only `order_relation_mismatch`, and a control uses only
`control_expectation_mismatch`, even though its detail object retains the lower-level counts.

The selector scalar record has exactly these seventeen keys:

```text
outcome_concentration, outcome_cell_count, evsi, catastrophe_mass,
m_utility, x_utility, eligible, m_rank, x_rank, m_selected, x_selected,
exploit_mean_cost, exploit_standard_deviation, exploit_score,
m_key, x_key, exploit_key
```

The three key fields are null for raw selection and signed JSON integers for fixed selection.
Ranks are positive integers or null. Every other numeric field is a finite JSON number.

A base selection candidate record has exactly `action` and `scalars`; `scalars` is the
seventeen-key record above. One selector candidate comparison has exactly `action`,
`mapped_action`, `left`, `right`, `numeric_relation`, `numeric_failures`, and
`exact_failures`. `left` and `right` are selector scalar records. `numeric_relation` is
`tolerance` for actual transformed-pipeline relations and `exact_binary64` for isolated and
order relations. `numeric_failures` contains only the nine numeric/count fields enumerated in
section 7.4; `outcome_cell_count` uses exact integer equality. `exact_failures` contains only
`eligible`, `m_rank`, `x_rank`, `m_selected`, `x_selected`, `m_key`, `x_key`, and
`exploit_key`. The failure lists contain unique names in scalar-record order, and no field
appears in both.

For an evaluated successful snapshot, `source_roles` is a four-entry list in the registered
role order. Each item has
exactly `role` and `source_sha256`. A snapshot digest is SHA-256 of canonical JSON for an
object with exactly `schema_version`, `candidate_sequence`, `source_roles`,
`normalized_weights`, `root_predictions`, and `rolewise_costs`; its schema is
`action-qbc-v7-snapshot-digest-v1`. `normalized_weights` has exact records `role,value` in
role order. `root_predictions` has records with exactly `action`, `role`, `grid_sha256`,
`grid_shape`, `game_state`, and `level_delta`, in candidate-then-role order.
For a null prediction or one rejected by the structural contract, the record remains present
and addressable with the exact action/role while `grid_sha256`, `grid_shape`, `game_state`,
and `level_delta` are all JSON null. No partial prediction fields are retained. This all-null
encoding produces `invalid_root_prediction` rather than an inventory failure.
`rolewise_costs` has records with exactly `action`, `role`, and `cost`, in the same order. A
selection digest is SHA-256 of canonical JSON for an
object with exactly `schema_version`, `selector_identity`, `candidate_records`, `exploit_set`,
`m_maximizer_set`, `x_maximizer_set`, `m_decision`, and `x_decision`; its schema is
`action-qbc-v7-selection-digest-v1`. `selector_identity` is the complete registered raw or
compound identity from section 10. Both use sorted-key compact ASCII JSON, no NaN, and no
final line feed.

Where a primitive pre-selector weight or cost is nonfinite, the snapshot and relation record
uses exactly the JSON string `"nan"`, `"+inf"`, or `"-inf"` according to its IEEE-754 value;
its delta/bound fields are null and its record pass is false. This is the only non-number
encoding for those fields and prevents invalid JSON. Selector scalar outputs themselves must
be finite and never use a sentinel.

### 7.4 Exact per-kind evidence and pass equations

A completed base row's `evidence` has exactly:

```text
pipeline, raw_selector, fixed_selector, structural, mechanism,
v4_counterfactual, prepreregistered_reproduction
```

All seven values are layer envelopes. Their `details` keys are exact:

- `pipeline`: `snapshot_sha256`, `source_roles`, `action_count`, `role_count`,
  `worker_count`;
- `raw_selector` and `fixed_selector`: `selection_sha256`, `candidate_records`,
  `exploit_set`, `m_maximizer_set`, `x_maximizer_set`, `m_decision`, `x_decision`;
- `structural`: `safe_valid_program_count`, `behaviorally_distinct_program_count`,
  `graded_action_varying_role_count`, `worker_limit_pass_count`, `worker_count`;
- `mechanism`: `max_evsi`, `max_x_utility`, `required_evsi`, `evsi_shortfall`, `m_mode`,
  `x_mode`, `m_action`, `x_action`, `exploit_action`;
- `v4_counterfactual`: `causal_exercise`, `selected_action`, `selected_evsi`,
  `selected_x_utility`, `historical_agreement`;
- `prepreregistered_reproduction`: `expected`, `observed`, `comparison_passes`.

The base-layer equations are exact. `pipeline` is always evaluated. It passes exactly when
one schema-valid complete planning snapshot exists; its digest recomputes; it contains the
exact four unique registered roles, four workers, and one duplicate-free candidate sequence
of 1--12 registered actions; and every prediction/cost occurrence required by that Cartesian
inventory is addressable. An absent snapshot emits `base_pipeline_unavailable`; any other
failure emits `pipeline_snapshot_invalid`.

`raw_selector` and `fixed_selector` are precondition-failed only when `pipeline` fails.
Otherwise each is evaluated and passes exactly when the authoritative finalizer independently
recomputes a finite selection under its registered selector identity, the selection digest
matches, candidate records occur once in candidate order, all three sets are complete and
canonically ordered, and both decisions are internally consistent with those records. A
failure of selector execution or authoritative recomputation from an otherwise schema-valid
snapshot is global `evaluator_internal_error`, not a producer-chosen scientific reason;
therefore an evaluated base selector layer is reason-free.

`structural` is evaluated only when `pipeline` passes and otherwise uses the canonical
precondition-failed default. When evaluated it uses `structural_gate_failed` exactly when its
already stated conjunction fails. `mechanism` is
evaluated when the raw selection is available and uses `mechanism_gate_failed` exactly when
its already stated conjunction fails; otherwise it is precondition-failed. `v4_counterfactual`
is evaluated when its registered call completes and passes exactly when
`causal_exercise=true`, using `causal_diagnostic_false` otherwise; inability to address its
base snapshot is precondition-failed. `prepreregistered_reproduction.comparison_passes` is a
JSON Boolean. On index zero the layer is evaluated and passes exactly when finite
`max_evsi`/`max_x_utility` fields satisfy section 6.1 tolerance and every Boolean, mode, and
action field equals the disclosed object exactly. On indices 1--3 it is precondition-failed
with `no_prepreregistered_observation`, both objects are null, and
`comparison_passes=false`. Index zero is evaluated only when both `pipeline` and
`raw_selector` pass; otherwise it is precondition-failed with the canonical default details.
A failed evaluated index-zero comparison emits
`prepreregistered_base_observation_mismatch`.

`expected` and `observed` are either null or exact nine-key objects with `family`,
`structural_pass`, `mechanism_pass`, `causal_exercise`, `max_evsi`, `max_x_utility`,
`m_mode`, `x_mode`, and `exploit_action`. On indices 1--3 both are null and the layer is
precondition-failed with `no_prepreregistered_observation`. Structural pass requires exactly
four safe valid programs, four distinct behaviors, at least two action-varying roles, and all
workers passing their limits. Mechanism pass requires M exploit, X probe, positive X utility,
and the inherited concentration and probe-cap gates. `causal_exercise` is reported, not
required for diagnostic completeness.

A completed visual row's `evidence` has exactly:

```text
pipeline_integrity
frontier_relation
role_weight_relation
root_transition
planner_cost
actual_raw_selector
actual_fixed_selector
isolated_action_relabel_raw
isolated_action_relabel_fixed
isolated_signature_pushforward_raw
isolated_signature_pushforward_fixed
v6_reproduction
```

The exact detail schemas and pass equations are:

- `pipeline_integrity`: details are `base_snapshot_sha256`,
  `transformed_snapshot_sha256`, `base_available`, `transformed_available`,
  `base_prediction_occurrence_count`, `transformed_prediction_occurrence_count`, and
  `compiler_manifest`. The manifest is the ordered four-entry exact schema in section 3.1.
  It
  passes exactly when both snapshots exist and have exact registered action/role/prediction
  inventories.
- `frontier_relation`: details are `action_map_sha256`, `base_action_count`,
  `transformed_action_count`, `mapped_action_count`, `unmapped_base_action_count`,
  `extra_transformed_action_count`, `set_equal`, `sequence_equal`, and
  `canonical_order_preserving`. It passes exactly when the actual map covers both frontier
  sets bijectively, the mapped sequence equals the transformed sequence, and canonical order
  is preserved.
- `role_weight_relation`: details are `role_records`, `role_count`, `nonfinite_count`,
  `tolerance_mismatch_count`, and `max_abs_delta`. A role record has exactly `role`,
  `base_source_sha256`, `transformed_source_sha256`, `base_weight`, `transformed_weight`,
  `abs_delta`, `tolerance_bound`, and `passes`. The layer passes exactly when all four unique
  roles exist, all weights are finite, and every weight record passes the tolerance relation.
- `root_transition`: details are `pair_records`, `prediction_pair_count`,
  `valid_prediction_pair_count`, `fully_equivariant_pair_count`,
  `boundary_consistent_censored_pair_count`,
  `interior_or_metadata_mismatch_pair_count`, `invalid_prediction_pair_count`,
  `expected_exterior_nonbackground_count`, `observable_mismatch_cell_count`,
  `state_mismatch_count`, and `level_delta_mismatch_count`. The layer's `passes` means the
  full relation: every pair is valid and fully equivariant.
- `planner_cost`: details are `pair_records`, `cost_pair_count`, `nonfinite_count`,
  `tolerance_mismatch_count`, and `max_abs_delta`. A cost record has exactly `action`,
  `mapped_action`, `role`, `base_cost`, `transformed_cost`, `abs_delta`,
  `tolerance_bound`, and `passes`. The layer passes exactly when every required mapped
  action/role pair exists, is finite, and passes the tolerance relation.
- each of the six selector-relation layers has details `candidate_records`,
  `compared_candidate_count`, `numeric_mismatch_count`,
  `eligibility_mismatch_count`, `rank_mismatch_count`,
  `selected_membership_mismatch_count`, `set_mismatch_count`,
  `gate_mismatch_count`, `decision_mismatch_count`, `key_mismatch_count`,
  `left_exploit_set`,
  `right_exploit_set`, `left_m_maximizer_set`, `right_m_maximizer_set`,
  `left_x_maximizer_set`, `right_x_maximizer_set`, `left_m_decision`,
  `right_m_decision`, `left_x_decision`, and `right_x_decision`.
  For actual transformed-selector relations, unquantized scalar fields use the registered
  tolerance and structural fields, keys, eligibility, ranks, sets, gates, and decisions use
  exact equality. For isolated and order relations every scalar requires identical
  IEEE-754 binary64 bytes and every structural field agrees exactly after mapping. A
  relation passes exactly when `status=evaluated`, every construction/premise required by
  that named relation succeeds, its eight mismatch counts (`numeric`, `eligibility`, `rank`,
  `selected_membership`, `set`, `gate`, `decision`, and `key`) are zero, and its reason list is empty.
  `key_mismatch_count` is zero for raw relations. Zero-filled details in a
  precondition-failed envelope or an evaluated isolated-construction defect never imply
  passage.
- `v6_reproduction`: details are `applicable`, `expected_comparison`,
  `observed_comparison`, `expected_comparison_sha256`, `observed_comparison_sha256`,
  `comparison_reproduced`, `expected_failure_vector_sha256`, and
  `observed_failure_vector_sha256`. It is applicable only to the twelve index-zero visual
  rows. Each comparison is an exact nine-key v6 object with `status`,
  `semantics_id`, `mapped_action_count`, `unmapped_action_count`,
  `prediction_pair_count`, `overflow_nonbackground_count`, `reasons`, `passes`, and
  `parity`; each comparison hash covers its canonical JSON. The expected object is loaded
  from the content-addressed v6 result while the observed object is independently derived
  from fresh v7 snapshots. Extension rows have an evaluated, reason-free no-op with
  `applicable=false`; all four comparison/object-hash fields and both vector hashes are null;
  and `comparison_reproduced=true`. This is not counted as v6 reproduction evidence.

All mismatch-count units are fixed. Role-weight and planner-cost mismatch counts count
failed records. Root category and metadata counts count ordered action-by-role prediction
occurrences; `observable_mismatch_cell_count` counts unequal grid cells summed over those
occurrences. In a selector relation, `compared_candidate_count` counts candidate pairs,
`numeric_mismatch_count` counts failures among exactly `outcome_concentration`,
`outcome_cell_count`, `evsi`,
`catastrophe_mass`, `m_utility`, `x_utility`, `exploit_mean_cost`,
`exploit_standard_deviation`, and `exploit_score`; `outcome_cell_count` always uses exact
integer equality while the other fields use the relation's numeric rule. `eligibility_mismatch_count`
counts unequal `eligible` fields; `rank_mismatch_count` counts unequal `m_rank` and `x_rank`
fields; `selected_membership_mismatch_count` counts unequal `m_selected` and `x_selected`
fields; and `key_mismatch_count` counts unequal `m_key`, `x_key`, and `exploit_key` fields.
`set_mismatch_count` counts unequal named sets among exploit, M maximizers, and X maximizers.
`gate_mismatch_count` counts unequal M/X `gate_reason` strings. `decision_mismatch_count`
counts M and X once each when action, mode, or probe candidate differs exactly or the
decision score fails that relation's numeric rule. No scalar field contributes to more than
one of these counts.

The root `pair_records` are ordered by base candidate sequence then compiler-role order. A
pair record has exactly:

```text
action, mapped_action, role, base_prediction_ref, transformed_prediction_ref,
expected_prediction_ref, expected_origin_row, expected_origin_col,
observable_mismatch_mask_ref, expected_exterior_support_ref,
game_state_equal, level_delta_equal, observable_mismatch_cell_count,
expected_exterior_nonbackground_count, category, passes
```

`category` is exactly `fully_equivariant`, `boundary_consistent_censored`,
`interior_or_metadata_mismatch`, or `invalid_prediction`; `passes` is the full-transition
Boolean. Category counts are occurrence counts and their sum equals
`prediction_pair_count`.

A completed order row has exactly `order_transform`, `raw_selector_relation`, and
`fixed_selector_relation` in `evidence`; the selector layers use the relation schema above.
`order_transform` is a layer whose details have exactly `order_contract_sha256`,
`target`, and `permutation_records`. Each permutation record has exactly `action`,
`sequence_length`, and `output_to_input_permutation`, with
`output[k]=input[output_to_input_permutation[k]]`. Candidate- and hypothesis-sequence rows
contain one record with null action. Serialized-outcome-cell reversal contains one record per
candidate action in candidate order because cell counts may differ. Every permutation is a
complete rearrangement of `0..sequence_length-1`; empty sequences use `[]`. The layer passes
exactly when `status=evaluated`, target and record inventory match the registered contract,
every permutation equals the registered rule, and reasons are empty; otherwise it emits
`order_relation_mismatch`. A completed control row has
exactly `raw_control` and `fixed_control`; their details have exactly `control_id`,
`control_contract_sha256`, `predicate_id`, `selector_call_count`,
`observed`, `observed_sha256`, and `predicate_passes`. `observed` is the exact canonical
control record returned for that treatment; its SHA hashes its canonical JSON. A control
layer passes exactly when its contract hash matches, its call count matches, and
its registered predicate passes.

For an order row, all three layers are precondition-failed when the corresponding base
pipeline is unavailable. Otherwise `order_transform` is evaluated. The raw and compound
selector-relation layers are evaluated only when `order_transform` passes; a failed transform
makes both precondition-failed. A selector relation then passes only under the exact equation
above. Authoritative selector execution failure from a schema-valid transformed snapshot is
global `evaluator_internal_error`. Control layers are always evaluated; a borrowed evaluator
exception is likewise global rather than converted into an invented control observation.

### 7.5 Exact mismatch-mask and support-reference rules

Every valid base or transformed prediction in a root pair has its own grid reference. `expected_prediction_ref`
is non-null whenever the base prediction and transform relation are valid, except for the
explicit palette-domain, scale-domain, or transformed-destination-shape invalid cases in
section 4.2. For translation it references the complete augmented
expected grid and the signed origin fields are non-null; for palette and scale it references
the ordinary expected grid and both origins are zero.

`observable_mismatch_mask_ref` is non-null exactly when expected and transformed grids have
the same known comparison shape. Its decoded grid has that shape, label 1 exactly at unequal
cells and 0 elsewhere. It is null for a null/invalid prediction or shape mismatch.

`expected_exterior_support_ref` is non-null exactly for a translation pair with a valid base
prediction. A valid zero-support translation references the canonical empty `[]` blob. It is
null for palette, scale, or an invalid base prediction. `expected_exterior_nonbackground_count`
is zero when the reference is null and otherwise equals its decoded entry count. Grid and
support tables must contain exactly the distinct non-null references in root pair records
and the expected/mask/support occurrences scoped in section 5.1; pipeline integrity records
have no grid-reference fields. Invalid or shape-mismatched occurrences never manufacture a
mismatch mask.

### 7.6 Exact v6 preimage and authority boundary

The v6 failure-vector preimage is exactly the `failing_visuals` list in the content-addressed
v6 result JSON identified in section 2.1. It is the visual-row-order projection

```text
{family, transform_name, comparison}
```

of every index-zero visual row whose v6 comparison does not pass. Each `comparison` is the
exact nine-key v6 object frozen by the v6 amendment; family, transform, comparison-reason,
and list orders are therefore fixed by that artifact. Canonicalization uses sorted keys,
compact separators, ASCII escaping, no NaN, and no final line feed. V7 independently derives
the same projection from its fresh snapshots and hashes those bytes.

The pipeline producer emits only addresses and primitive snapshots, grids, costs, roles,
weights, actions, counters, and transform observations. It is forbidden to submit
`registered_row`, final layer envelopes, pass Booleans, reasons, aggregates, or terminal
dispositions. The authoritative v7 reference finalizer alone constructs every comparison,
row, aggregate, and fallback from those primitives. A forbidden producer field at an already
valid address is `scientific_record_schema_invalid` and localizes to that row; a malformed
address is the global inventory failure. There is therefore no producer/authority comparison
claim or parity object that can disagree. An exception or inconsistency inside the sole
authoritative finalizer uses global `evaluator_internal_error`.

### 7.7 Exact aggregate object

`aggregates` has exactly these keys, in canonical sorted-key serialization:

```text
v6_failure_vector_reproduced
v6_failure_vector_observed_sha256
prepreregistered_base_reproduced_count
prepreregistered_base_denominator
base_structural_pass_count
base_structural_denominator
base_mechanism_pass_count
base_mechanism_denominator
base_causal_true_count
base_causal_denominator
translation_prediction_pair_count
translation_fully_equivariant_pair_count
translation_boundary_consistent_censored_pair_count
translation_interior_or_metadata_mismatch_pair_count
translation_invalid_prediction_pair_count
translation_expected_exterior_cell_count
translation_boundary_consistent_exterior_cell_count
translation_mixed_exterior_cell_count
translation_invalid_prediction_exterior_cell_count
frozen_positive_translation_exterior_cell_denominator
frozen_positive_translation_observed_exterior_cell_count
frozen_positive_translation_boundary_consistent_exterior_cell_count
frozen_positive_translation_support_reproduced
primary_compound_scale_reconciliation_count
primary_compound_scale_denominator
primary_compound_scale_reconciliation
extension_compound_scale_reconciliation_count
extension_compound_scale_denominator
isolated_action_relabel_required_count
isolated_action_relabel_pass_count
isolated_signature_pushforward_required_count
isolated_signature_pushforward_pass_count
actual_raw_selector_evaluated_count
actual_raw_selector_pass_count
actual_raw_selector_precondition_failed_count
actual_fixed_selector_evaluated_count
actual_fixed_selector_pass_count
actual_fixed_selector_precondition_failed_count
order_raw_pass_count
order_raw_denominator
order_fixed_pass_count
order_fixed_denominator
control_raw_pass_count
control_raw_denominator
control_fixed_pass_count
control_fixed_denominator
resource_contract_passes
reason_counts
```

The fixed denominators are respectively 3 preobserved bases, 12 bases, 107 frozen positive-
translation exterior cells, 3 primary scales, 9 extension scales, 48 action-relabel tests,
48 signature-pushforward tests, 60 order rows, and 20 controls. Translation pair denominator
is the sum of mapped action-by-four-role occurrences in the 24 translation rows; its four
category counts must sum exactly to it. Mixed exterior cells belong to
`interior_or_metadata_mismatch`; boundary-consistent exterior cells belong to
`boundary_consistent_censored`; invalid-prediction exterior cells arise only when the base
prediction is valid but the transformed prediction is invalid. These three exterior counts
sum exactly to total expected exterior cells; fully equivariant pairs contribute zero.

`frozen_positive_translation_observed_exterior_cell_count` is the freshly derived total over
the three index-zero positive translations. `frozen_positive_translation_support_reproduced`
is true exactly when the v6 failure vector reproduces and that total is exactly 107.
`frozen_positive_translation_boundary_consistent_exterior_cell_count` is the subset numerator
for the fixed denominator 107 and includes only boundary-consistent-censored exterior cells
from those same rows. The numerator/107 fraction is claimable only when
`frozen_positive_translation_support_reproduced=true`. Primary compound reconciliation is true
exactly when all three applicable index-zero scale rows reproduce v6, satisfy all upstream
relations, and pass their compound selector relation under section 4.2. Extension compound
reconciliation count applies the same row rule without v6 reproduction. Actual-selector
precondition-failed rows are excluded from evaluated/pass counts and reported in the
corresponding precondition count; they never pass. Isolated pass counts require both raw and
compound variants of the named isolated relation to pass.

`reason_counts` has every reason in section 7.3 as an exact key and a non-negative integer
count over layer occurrences, plus one aggregate occurrence for `resource_counter_mismatch`
or `forbidden_resource_use` when applicable. `resource_contract_passes` is true exactly when
all 31 counters equal the registered vector and all nine forbidden-resource counters are
zero. All other aggregate values are Booleans, lowercase SHA-256 or null, or non-negative
integers. A normal global fallback uses the same object with fixed
denominators retained, every count zero, every Boolean other than
`resource_contract_passes` false, and the observed v6 hash null. All scientific reason counts
are zero; `resource_counter_mismatch` is one exactly when any observed counter differs from
registration, and `forbidden_resource_use` is one exactly when any forbidden counter is
nonzero. These two derived resource occurrences are retained in every fallback.

In every normal, addressable-terminal, size-fallback, and global-fallback branch,
`resource_contract_passes` retains its defining equivalence to the observed counters and
forbidden-resource values. Thus it may be true in a fallback reached after a complete exact
counter vector; it is the sole aggregate Boolean not forcibly false by fallback. This field
never makes `diagnostic_complete` true in a terminal or fallback branch.

For an addressable-terminal normal payload, aggregates are derived from completed siblings in
registered order. The terminal row contributes zero to every pass/evaluated/category count,
contributes one to the applicable fixed denominator, and contributes no scientific reason;
its terminal stage remains solely in the row. Any aggregate whose required preimage includes
that row is false, while hashes not derivable from the surviving complete inventory are null.
This rule is applied before `diagnostic_complete=false` and prevents a malformed row from
silently shrinking a denominator.

## 8. Fail-closed finalization and payload cap

Global failure stages have this exact precedence:

1. `transform_action_map_invalid`;
2. `scientific_record_inventory_invalid`;
3. `grid_evidence_table_invalid`;
4. `expected_exterior_support_table_invalid`;
5. `evaluator_internal_error`;
6. `payload_size_limit_exceeded`.

A global fallback contains all 140 registration-derived rows, in registered order, as
`terminal_global_negative`; uses canonical empty grid and expected-exterior-support tables;
sets
`diagnostic_complete=false` and `scientific_capability_passes=false`; retains the exact
observed resource counters; retains all false authorization flags; exits zero; and remains
eligible for the second registered process. For stages 1--5,
`candidate_payload_size_bytes` is null. For the size fallback it is the exact oversized
candidate byte count. `terminal_fallback_stage` is the selected stage.

In a normal non-size payload, `terminal_fallback_stage` and
`candidate_payload_size_bytes` are both null. An addressable terminal has status
`authoritative_derivation_error`, stage `scientific_record_schema_invalid`, empty evidence,
and leaves both top-level fields null. Global rows use status
`authoritative_derivation_error` for stages 1--4, `evaluator_internal_error` for stage 5,
and `payload_size_limit_exceeded` for stage 6; their stage is the exact top-level stage. All
normal and fallback identity objects retain their exact validated values. A fallback uses the
zero/false aggregate object in section 7.7 with its stated resource-contract exception and
the observed resource-counter object.

The canonical empty tables are exactly
`{"schema_version":"action-qbc-v7-grid-evidence-table-v1","blobs":[]}` and
`{"schema_version":"action-qbc-v7-expected-exterior-support-table-v1","blobs":[]}` before
top-level sorted-key serialization. A monotonic scientific deadline reached inside the CLI
uses `evaluator_internal_error`; a shell hard timeout that prevents finalization is instead
the administrative outcome in section 11.

The cap is exactly 67,108,864 canonical bytes. It is measured after authoritative
rederivation and construction of the complete candidate payload. Equality passes. No
compression, evidence removal, schema relaxation, threshold change, or cap increase is
allowed. The production finalizer is tested at exactly 67,108,863, 67,108,864, and
67,108,865 bytes. The fixed fallback must independently validate and fit the cap; inability
to construct that fallback produces no final output and terminates v7.

A valid partial action map missing a required selector-frontier action is not a global map
defect. It remains an addressable completed row with the relevant scientific layer
precondition-failed.

Expected scientific mismatches, missing required action mappings, null/invalid/wrong-shape
root predictions, known pipeline failures, and selector precondition failures are completed
scientific rows when their primitive evidence conforms to the frozen schema. A malformed
primitive or evidence object at a valid address is addressably terminal. A missing,
duplicate, conflicting, malformed, or unregistered address invokes the global inventory
fallback. An unexpected exception escaping the authoritative assembler invokes global
`evaluator_internal_error`. Thus row completion and diagnostic completeness are distinct:
the exact construction/resource defects in section 7.1 can make a schema-valid completed
negative payload incomplete, while ordinary fully represented scientific non-passes remain
complete.

## 9. Resources, counters, and no-live-work proof

Each process evaluates twelve base, forty-eight visual, sixty order, and twenty control rows.
It computes each of the sixty base/visual compiler-planner pipelines once. The exact call
ledger is:

- each scene is generated once;
- each base, palette, positive-translation, and negative-translation pipeline (48 total)
  calls the candidate builder once, compiler once, constructs one four-program pool, starts
  four persistent and four transient workers, performs four grounding evaluations, calls the
  planner once, computes one raw and one compound snapshot selection, and performs exactly
  two registered raw-controller calls/replays, each of which calls the raw selector once;
- each scale pipeline (12 total) reuses the mapped base candidate sequence, so it has no
  candidate-builder or controller call/replay, but otherwise has the same compiler, pool,
  worker, grounding, planner, and one-raw/one-compound selection calls;
- each of the 60 order rows starts from its scene's base snapshot and calls raw once and
  compound once; it never recompiles, replans, or calls a controller;
- each of the 48 visual rows calls raw once and compound once for each of its two isolated
  transported snapshots, yielding 96 calls of each isolated category; and
- controls use the exact 19-call per-treatment ledger below.

Thus raw scene/order calls are `48*(1+2)+12+60=216`, compound scene/order calls are
`60+60=120`, and all categories are disjoint. The expected resource counters are:

| Counter | Exact value |
|---|---:|
| `public_scene_generations` | 12 |
| `registered_scene_file_reads` | 0 |
| `candidate_builder_calls` | 48 |
| `compiler_calls` | 60 |
| `compiled_programs` | 240 |
| `grounding_evaluations` | 240 |
| `hypothesis_pool_constructions` | 60 |
| `persistent_worker_starts` | 240 |
| `transient_worker_starts` | 240 |
| `total_worker_starts` | 480 |
| `planner_calls` | 60 |
| `completed_planning_snapshots` | 60 |
| `controller_calls` | 96 |
| `controller_snapshot_replays` | 96 |
| `v4_counterfactual_calls` | 12 |
| `raw_selector_scene_order_calls` | 216 |
| `raw_selector_control_calls` | 19 |
| `fixed_selector_scene_order_calls` | 120 |
| `fixed_selector_control_calls` | 19 |
| `isolated_raw_selector_calls` | 96 |
| `isolated_fixed_selector_calls` | 96 |
| `pure_selector_calls` | 566 |
| `model_calls` | 0 |
| `generated_tokens` | 0 |
| `gpu_operations` | 0 |
| `network_calls` | 0 |
| `environment_actions` | 0 |
| `reward_observations` | 0 |
| `rhae_observations` | 0 |
| `lockbox_path_operations` | 0 |
| `lockbox_bytes_read` | 0 |

The registration independently reconstructs these counts from the row plan and call graph.
Increment points and legacy ownership are the exact registered arrays and map in section 10.
Fallbacks retain observed counts rather than substituting expected counts.

`resource_counters` has exactly the thirty-one snake-case keys in this table and no others;
all values are non-negative JSON integers. `pure_selector_calls` equals the sum of the six
raw, fixed, and isolated selector categories, not the inherited raw-only counter.

The v7 adapter around the unmodified v5 evaluator uses the complete registered field map in
section 10. It owns one fresh legacy counter state, lets every borrowed v5 path update only
that state, rejects negative deltas or unexpected keys, and copies each mapped final value
once. In particular, legacy scene/order and control selector fields become the corresponding
raw v7 fields, legacy `registered_scenes_read` becomes `registered_scene_file_reads`, and
legacy raw-only `pure_selector_calls` is validated then discarded. V7 directly owns only the
four counters registered as `v7_owned`; the two final derived counters are recomputed. Direct
public generation leaves registered scene-file reads at zero.

Raw and fixed control-selector call counts use the same exact per-control ledger in section
3.2: controls 0--13 each call once, controls 14--16 call zero times, control 17 calls once,
and controls 18 and 19 call twice each. Thus each treatment totals 19. A valid complete
pipeline executes all fixed and lifted-isolated calls. A pipeline/construction failure may
emit a terminal or diagnostic-incomplete result with lower observed counters; it may not
forge the expected vector. A valid partial actual translation frontier affects scientific
preconditions but not these call counts because the raw/fixed transformed selections were
already computed and the isolated relation uses the total lifted map.

Both processes must record exactly zero model calls, generated tokens, GPU operations,
network calls, environment actions, reward observations, RHAE observations, lockbox path
operations, and lockbox bytes read. The whole diagnostic wall limit is 2,400 seconds per
process. Each CLI stops initiating scientific computation at 2,100 seconds and reserves the
remaining 300 seconds for authoritative assembly, fallback construction, serialization,
validation, and output publication before its 2,400-second CLI deadline. The outer shell
hard bound is 2,700 seconds with a 15-second kill-after. Every worker retains the frozen
100 ms prediction limit and 268,435,456-byte allocation-headroom contract. A resource
mismatch makes `diagnostic_complete=false` and is scientifically negative; it never
authorizes a retry.

## 10. Independent registration and implementation gates

The registration producer and reconstructor are separate programs. The reconstructor must
not import the producer, v7 evaluator, v7 reference implementation, diagnostic CLI, v6 audit
evaluator, or any generated registration module. It rebuilds with independent standard-
library logic and byte-compares:

- preregistration and v6 anchors;
- exact existing-source and added-source inventories and hashes;
- `uv.lock`, Python, platform, command, and clean-tree identities;
- all twelve public scene seeds and hashes without scientific execution;
- all 140 row addresses and registered metadata;
- transform contracts, source/destination shapes, and reconstructed action-map digests;
- role-pairing contract, compound-selector constants, tolerances, schemas, controls, counters,
  cap, and authorization boundary.

The registration JSON has exactly these nineteen top-level keys:

```text
schema_version
status
treatment_id
diagnostic_system_id
comparison_semantics_id
runtime_id
preregistration
v6_negative
platform
dependencies
source_manifest
scene_inventory
row_inventory
transform_contracts
scientific_contract
resource_contract
execution_contract
authorization
content_sha256
```

Its status is `registered_zero_result`, runtime identity is null, and authorization is the
five-key false object from section 1. `content_sha256` is SHA-256 of canonical JSON for the
other eighteen keys; it is excluded from its own preimage. The final registration file is
canonical sorted-key compact UTF-8 JSON with no final line feed. Its independent file hash is
not stored inside itself; it is computed at execution and recorded in
`registration_identity`.

`source_manifest` has exactly `preregistration_tree`, `open_freeze_added_files`, and
`manifest_sha256`. Each inventory is a path-sorted list of objects with exactly `path`,
`git_blob_sha1`, `sha256`, and `byte_count`. `preregistration_tree` includes every blob at
`P`, as enumerated by `git ls-tree -r P`, including this document. Every field is computed
from the raw bytes returned by `git cat-file blob P:<path>`: byte count is byte length,
SHA-256 hashes those bytes, and Git blob SHA-1 is the Git blob-object identity of those same
bytes.

`open_freeze_added_files` includes the nine non-registration paths in the section 3.1
allowlist. Its fields are computed over exact pre-`O` worktree bytes; Git identity is obtained
with `git hash-object --no-filters <path>`, and both the staged blob and later `O:<path>` blob
must equal those bytes. The registration JSON is excluded from the manifest to avoid
self-reference: its path is bound by the exact ten-path `P..O` delta, its bytes by
`content_sha256`, and its final Git blob by immutable commit/tag `O`. No ignored file,
virtual environment, cache, Git administrative file, or result path is included.
`manifest_sha256` hashes canonical JSON of the first two fields.

Cleanliness is byte-defined. At committed `P`, and again at committed `O`, raw output from
`git status --porcelain=v1 -z --untracked-files=all` is empty; the SHA-256 of that empty byte
string is `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Immediately before `O`, the ten allowlisted additions are staged, the worktree-to-index diff
is empty, and `git diff --cached --name-status -z P` contains exactly ten path-sorted `A`
entries. `git diff --name-status --no-renames P O` later contains those same additions and no
modification, deletion, rename, or extra path.

`preregistration` uses the exact five-key preregistration identity schema in section 7.3;
`v6_negative` uses its exact five-key v6 schema. `platform` has exactly
`python_version`, `python_implementation`, `platform_system`, `platform_machine`, and
`uv_version`, with the fixed values in section 7.3. `dependencies` is the exact ordered list:

```json
[
  {"name":"arc3-crosslevel-voi","version":"0.1.0","editable":true},
  {"name":"numpy","version":"2.5.1","editable":false},
  {"name":"PyYAML","version":"6.0.3","editable":false}
]
```

`scene_inventory` has exactly `count` and `scenes`; its twelve scene objects have exactly
`family`, `scene_index`, `seed_hex`, `scene_sha256`, `background_label`, `source_shape`,
`available_actions`, and `palette_forward` and use section 2.3 order. The inverse palette and
palette destination background are derived and checked against the table and generated
scene. `row_inventory` has exactly `count`, `order`, and `rows`; `order` is the literal
`base-all-scenes_then-visual-all-scenes_then-order-all-scenes_then-controls-v1`. Every
registered row begins with
exactly `row_index`, `row_id`, `kind`, and `registered_placeholder=true`, then has these exact
kind-specific fields:

- base: `family`, `scene_index`, `seed_hex`, `scene_sha256`;
- visual: `family`, `scene_index`, `seed_hex`, `scene_sha256`, `transform_name`,
  `transform_contract_sha256`, `actual_action_map_sha256`,
  `isolated_action_map_sha256`;
- order: `family`, `scene_index`, `seed_hex`, `scene_sha256`, `transform_name`,
  `order_contract_sha256`;
- control: `control_id`, `control_index`, `raw_selector_call_count`,
  `fixed_selector_call_count`, `control_contract_sha256`, `raw_predicate_id`,
  `fixed_predicate_id`.

`transform_contracts` is a scene/transform-ordered list. Each object has exactly `family`,
`scene_index`, `transform_name`, `source_shape`, `actual_destination_shape`,
`isolated_destination_shape`, `source_background_label`,
`destination_background_label`, `parameters`, `contract_sha256`,
`actual_action_map_sha256`, and `isolated_action_map_sha256`. Values and hashes follow
section 5.5 exactly.

`order_contracts` is an additional exact field inside `scientific_contract`. It is the five
objects below in section 3.2 order; `order_contract_sha256` hashes the applicable canonical
object. These objects do not depend on a runtime sequence length:

```json
[
  {"schema_version":"action-qbc-v7-order-transform-contract-v1","name":"candidate_list_reversal","target":"candidate_sequence","rule":"reverse"},
  {"schema_version":"action-qbc-v7-order-transform-contract-v1","name":"candidate_list_left_rotation_by_one","target":"candidate_sequence","rule":"left_rotate_one"},
  {"schema_version":"action-qbc-v7-order-transform-contract-v1","name":"hypothesis_list_reversal","target":"hypothesis_sequence","rule":"reverse"},
  {"schema_version":"action-qbc-v7-order-transform-contract-v1","name":"hypothesis_list_left_rotation_by_one","target":"hypothesis_sequence","rule":"left_rotate_one"},
  {"schema_version":"action-qbc-v7-order-transform-contract-v1","name":"serialized_outcome_cell_order_reversal","target":"per_action_serialized_outcome_cell_sequence","rule":"reverse"}
]
```

At execution, `reverse(n)` is `[n-1,...,0]`; `left_rotate_one(0)` is `[]`; and
`left_rotate_one(n)` for positive `n` is `[1,...,n-1,0]`. Each order-row evidence records the
realized permutation records described in section 7.4. No result-dependent permutation is
registered.

`scientific_contract` has exactly `role_order`, `raw_selector_identity`,
`fixed_selector_identity`, `absolute_tolerance`, `relative_tolerance`,
`fixed_quantum_numerator`, `fixed_quantum_denominator`, `reason_order`,
`grid_evidence_schema`, `expected_exterior_support_schema`, `aggregate_keys`,
`global_fallback_stage_order`, `payload_cap_bytes`, and `order_contracts`. Values are exactly those in this
amendment; the quantum pair is `1` and `1099511627776`.

The value types are fixed: `role_order`, `reason_order`, `aggregate_keys`, and
`global_fallback_stage_order` are ordered JSON string lists copied from their displayed
blocks; selector identities are the exact objects below; both tolerance values are the JSON
number `1e-12`; quantum values and `payload_cap_bytes=67108864` are JSON integers; the two
evidence-schema values are their exact schema-version strings; and `order_contracts` is the
ordered object list above. No set-to-list conversion or alternate numeric spelling is
permitted in registration bytes.

`raw_selector_identity` is exactly:

```json
{"module":"arc3_voi.action_qbc_policy","callable":"select_action_conditional_qbc","policy_version":"action-conditional-outcome-qbc-v1","runtime_version":"crosslevel-voi-runtime-v5","source_bundle_sha256":"a2d36168936f433157052e07d7eafca4f8a65fb49c0bb61800fe53744f2d5a9d"}
```

The producer and each scientific process call `action_qbc_policy_sha256()` and require that
digest before selector use. The reconstructor binds the literal object and source manifest
without importing the module. `fixed_selector_identity` has exactly `version`,
`raw_selector_identity`, `quantum_numerator`, `quantum_denominator`, `rank_policy`,
`tie_set_policy`, `singleton_tie_break`, and `positive_utility_gate`. Its values are the
compound version in section 6.3, the complete raw identity above, `1`, `1099511627776`,
`dense_by_integer_key`, `complete_integer_key_ties`, `canonical_action_order`, and
`integer_key_strictly_greater_than_zero`, respectively.

`resource_contract` has exactly `expected_counts`, `control_call_ledger`,
`control_contract_sha256`, and `increment_contract`. Expected counts are the exact 31-key
object in section 9. `control_call_ledger` is the twenty-row raw/compound ledger in section
9, and `control_contract_sha256` is the frozen digest in section 3.2.

`control_call_ledger` is exactly this ordered list; every object has exactly the three shown
keys:

```json
[
  {"control_id":"identical_signatures_A1","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"dominant_mass_Aeq0_8_positive_JX","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"A_lt_0_8_evsi0","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"fragmented_cosmetic_evsi0","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"evsi_0_049","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"material_positive_JX_A_ge_0_8","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"inverse_low_global_agreement_A_ge_0_8","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"unused_rowwise_x_only_X_selects_other_probe","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"M_positive_eligible_different_from_X","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"exhausted_probe_cap","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"catastrophe_makes_JX_nonpositive","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"final_multiplier_1_M_equals_X","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"invalid_program_structural_false","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"timeout_program_structural_false","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"fewer_than_two_eligible_graded_roles","raw_selector_call_count":0,"fixed_selector_call_count":0},
  {"control_id":"worker_memory_drift","raw_selector_call_count":0,"fixed_selector_call_count":0},
  {"control_id":"forbidden_resource_use","raw_selector_call_count":0,"fixed_selector_call_count":0},
  {"control_id":"boundary_evsi_eq_0_05","raw_selector_call_count":1,"fixed_selector_call_count":1},
  {"control_id":"cosmetic_refinement_pair","raw_selector_call_count":2,"fixed_selector_call_count":2},
  {"control_id":"candidate_tie_pair","raw_selector_call_count":2,"fixed_selector_call_count":2}
]
```

`increment_contract` has exactly `before_attempt`, `after_success`, `on_observation`,
`derived`, `legacy_adapter`, and `zero_forbidden`. Each of the first three is a sorted list of counter names:
operation-attempt counters increment immediately before their named immutable call;
after-success counters update only at the immutable successful-return point; and observation
counters update at receipt. The literal arrays below, rather than this gloss, are
authoritative. `derived` contains exactly the three displayed formulas. `legacy_adapter` is the exact mapping and
consistency rule in section 9. Every one of the 31 counters occurs in exactly one listed,
or derived increment class among `before_attempt`, `after_success`, `on_observation`, and
`derived`, and registration reconstruction enforces that partition. `zero_forbidden` is an
additional constraint list and intentionally overlaps those increment classes.

The exact increment members are:

```json
{
  "before_attempt":["candidate_builder_calls","compiler_calls","controller_calls","environment_actions","fixed_selector_scene_order_calls","gpu_operations","grounding_evaluations","isolated_fixed_selector_calls","isolated_raw_selector_calls","lockbox_path_operations","model_calls","network_calls","planner_calls","public_scene_generations","raw_selector_control_calls","raw_selector_scene_order_calls","transient_worker_starts","v4_counterfactual_calls"],
  "after_success":["compiled_programs","completed_planning_snapshots","controller_snapshot_replays","hypothesis_pool_constructions","persistent_worker_starts","registered_scene_file_reads"],
  "on_observation":["generated_tokens","lockbox_bytes_read","reward_observations","rhae_observations"],
  "derived":{"fixed_selector_control_calls":"compound_control_legacy.pure_selector_control_calls","pure_selector_calls":"raw_selector_scene_order_calls+raw_selector_control_calls+fixed_selector_scene_order_calls+fixed_selector_control_calls+isolated_raw_selector_calls+isolated_fixed_selector_calls","total_worker_starts":"persistent_worker_starts+transient_worker_starts"},
  "zero_forbidden":["environment_actions","generated_tokens","gpu_operations","lockbox_bytes_read","lockbox_path_operations","model_calls","network_calls","reward_observations","rhae_observations"]
}
```

`legacy_adapter` has exactly `field_map`, `ignored_fields`, `required_equations`,
`copy_policy`, `v7_owned`, and `compound_control_adapter`. `field_map` maps legacy names to final v7 names and is exactly:

```json
{
  "candidate_builder_calls":"candidate_builder_calls",
  "compiler_calls":"compiler_calls",
  "compiled_programs":"compiled_programs",
  "completed_planning_snapshots":"completed_planning_snapshots",
  "controller_calls":"controller_calls",
  "controller_snapshot_replays":"controller_snapshot_replays",
  "environment_actions":"environment_actions",
  "generated_tokens":"generated_tokens",
  "grounding_evaluations":"grounding_evaluations",
  "gpu_operations":"gpu_operations",
  "hypothesis_pool_constructions":"hypothesis_pool_constructions",
  "lockbox_bytes_read":"lockbox_bytes_read",
  "lockbox_path_operations":"lockbox_path_operations",
  "model_calls":"model_calls",
  "network_calls":"network_calls",
  "persistent_worker_starts":"persistent_worker_starts",
  "planner_calls":"planner_calls",
  "pure_selector_control_calls":"raw_selector_control_calls",
  "pure_selector_scene_order_calls":"raw_selector_scene_order_calls",
  "registered_scenes_read":"registered_scene_file_reads",
  "reward_observations":"reward_observations",
  "rhae_observations":"rhae_observations",
  "transient_worker_starts":"transient_worker_starts",
  "v4_counterfactual_calls":"v4_counterfactual_calls"
}
```

`ignored_fields` is exactly `["pure_selector_calls","total_worker_starts"]`. `required_equations` is exactly
`["legacy.pure_selector_calls=legacy.pure_selector_scene_order_calls+legacy.pure_selector_control_calls","legacy.total_worker_starts=legacy.persistent_worker_starts+legacy.transient_worker_starts"]`.
`copy_policy` is exactly `copy_each_mapped_legacy_final_value_once_after_all_borrowed_calls`.
`v7_owned` is exactly
`["fixed_selector_scene_order_calls","isolated_fixed_selector_calls","isolated_raw_selector_calls","public_scene_generations"]`.
`compound_control_adapter` is exactly
`{"counter_state":"fresh_isolated","required_equal":{"pure_selector_calls":19,"pure_selector_control_calls":19,"pure_selector_scene_order_calls":0},"required_zero":"all_other_AUDIT_RESOURCE_COUNTER_FIELDS","destination":"fixed_selector_control_calls","copy_policy":"copy_once"}`.
The wrapper never directly increments a mapped v7 field for a borrowed call, so copied legacy
deltas cannot be double-counted. The two derived final values are recomputed after that copy.

`execution_contract` has exactly `compute_deadline_seconds`, `wall_time_seconds`,
`hard_timeout_seconds`, `registered_start_count`, `process_labels`, `execution_root`,
`process_a_root`, `process_b_root`, `process_a_output`, `process_b_output`,
`producer_argv`, `reconstructor_argv`, `tag_verification_step`, `setup_steps`,
`environment_build_argv`, `preflight_argvs`,
`scientific_argv_template`, `test_argvs`, `finalizer_argv_template`, `finalizer_cwd`,
`argv_hashes`, `administrative_stage_order`, and `third_start_allowed`. The time values are
2100, 2400, and 2700; starts are 2; labels are
`["A","B"]`; paths are fixed in section 11; and third-start authorization is false.
`administrative_stage_order` is the exact displayed precedence list in section 11.

Every command identity is a JSON list of strings, never shell text. For any argv,
`argv_sha256` is SHA-256 of canonical sorted-key-compatible compact ASCII JSON for that list,
with no final line feed. `test_argvs` and `preflight_argvs` are ordered lists of argv lists;
their aggregate hash covers canonical JSON for the complete outer list. `argv_hashes` has
exactly `producer`, `reconstructor`, `tag_verification`, `setup`, `environment_build`,
`preflight`, `scientific`, `tests`, and `finalizer`. Literal placeholders such as
`<OUTPUT_PATH>` remain literal strings in the
hashed template. The human-readable command blocks below are renderings of those arrays and
backslash-newline pairs are not bytes in any hash.

Hash preimages are exact: `producer`, `reconstructor`, `environment_build`, `scientific`,
and `finalizer` hash their single argv list; `preflight` and `tests` hash their complete
ordered outer list; `tag_verification` hashes the complete four-key step object; and `setup`
hashes the complete ordered step-object list, including cwd and expectations. All use the
same canonical JSON bytes. `execution_identity.canonical_command_sha256` is exactly
`execution_contract.argv_hashes.scientific`, whose `<OUTPUT_PATH>` placeholder remains
unsubstituted, so A and B have identical execution identity.

The producer and independent reconstructor commands are exactly:

```text
uv run --frozen --extra dev python3 -I -B \
  scripts/build_action_qbc_v7_open_registration.py \
  --repository-root . \
  --preregistration-tag prereg-action-qbc-v7-open-failure-decomposition-v1 \
  --output artifacts/action_qbc_v7_open_registration.json

uv run --frozen --extra dev python3 -I -B \
  scripts/reconstruct_action_qbc_v7_open_registration.py \
  --repository-root . \
  --registration artifacts/action_qbc_v7_open_registration.json
```

Their canonical argv values are exactly:

```json
[
  ["uv","run","--frozen","--extra","dev","python3","-I","-B","scripts/build_action_qbc_v7_open_registration.py","--repository-root",".","--preregistration-tag","prereg-action-qbc-v7-open-failure-decomposition-v1","--output","artifacts/action_qbc_v7_open_registration.json"],
  ["uv","run","--frozen","--extra","dev","python3","-I","-B","scripts/reconstruct_action_qbc_v7_open_registration.py","--repository-root",".","--registration","artifacts/action_qbc_v7_open_registration.json"]
]
```

The reconstructor may execute Git plumbing and parse this document using the Python standard
library. It may not import any project module. It independently computes canonical JSON,
hashes, P-tree and added-file inventories, row addresses, transform/map formulas, constants,
counters, and all registration fields. It verifies the preregistered scene seed/hash table
without regenerating scenes. Producer and reconstructed bytes must match exactly both before
`O` is committed and again from the clean `O` checkout.

The exact pre-freeze Linux test command list, in order, is:

```text
uv run --frozen --extra dev pytest -q \
  tests/test_action_qbc_v7_audit.py \
  tests/test_action_qbc_v7_registration.py

uv run --frozen --extra dev ruff check \
  src/arc3_voi/action_qbc_v7_reference.py \
  src/arc3_voi/action_qbc_v7_audit.py \
  scripts/build_action_qbc_v7_open_registration.py \
  scripts/finalize_action_qbc_v7_open_diagnostic.py \
  scripts/reconstruct_action_qbc_v7_open_registration.py \
  scripts/run_action_qbc_v7_open_diagnostic.py \
  tests/test_action_qbc_v7_audit.py \
  tests/test_action_qbc_v7_registration.py

uv run --frozen --extra dev mypy \
  src/arc3_voi/action_qbc_v7_reference.py \
  src/arc3_voi/action_qbc_v7_audit.py
```

The registered `test_argvs` value is exactly:

```json
[
  ["uv","run","--frozen","--extra","dev","pytest","-q","tests/test_action_qbc_v7_audit.py","tests/test_action_qbc_v7_registration.py"],
  ["uv","run","--frozen","--extra","dev","ruff","check","src/arc3_voi/action_qbc_v7_reference.py","src/arc3_voi/action_qbc_v7_audit.py","scripts/build_action_qbc_v7_open_registration.py","scripts/finalize_action_qbc_v7_open_diagnostic.py","scripts/reconstruct_action_qbc_v7_open_registration.py","scripts/run_action_qbc_v7_open_diagnostic.py","tests/test_action_qbc_v7_audit.py","tests/test_action_qbc_v7_registration.py"],
  ["uv","run","--frozen","--extra","dev","mypy","src/arc3_voi/action_qbc_v7_reference.py","src/arc3_voi/action_qbc_v7_audit.py"]
]
```

All three commands must exit zero in that order. The full v7 diagnostic command is forbidden
as a test.

The open freeze is forbidden until all implementation tests pass, including:

1. exact action coordinate conversion and complete/partial action-map reconstruction;
2. role pairing by unique role under source-text and list-order changes;
3. palette, scale, positive/negative translation, augmented-plane, known-window, exterior
   manifest, boundary-consistent-censored, mixed, and zero-overflow cases;
4. grid and expected-exterior-support table canonicalization, sharing,
   missing/dangling/duplicate/orphan blobs,
   base64, shape, byte count, digest, and reference tampering;
5. planner cost and Gibbs-weight exact/tolerance separation;
6. fixed key derivation with exact ratios, positive and negative half-quantum ties,
   tie-to-even, dense ranks, complete sets, zero gate, canonical action choice, non-finite
   rejection, and material-separation preservation;
7. isolated action relabeling and injective signature pushforward, including a deliberately
   non-injective rejection;
8. actual-selector upstream gating and exact
   `not_testable_due_upstream_mismatch` attribution;
9. v6 failure-vector and base-observation reproduction logic on frozen miniature evidence,
   without running extension-scene planners;
10. exact row schema, addressable sibling retention, every global fallback and precedence;
11. production cap finalization at 67,108,863, 67,108,864, and 67,108,865 bytes;
12. exact counters, forbidden-resource detection, timeout and worker-memory drift;
13. independent registration reconstruction and import-boundary checks;
14. deterministic canonical replay and offline startup; and
15. absence of every forbidden v7 lockbox, sealed, permit, and runtime path.

Before `O`, no compiler, planner, selector, controller, or v7 evaluator may consume any of
the nine extension scenes. Tests use hand-built fixtures and the already disclosed index-zero
facts only. Data-only scene regeneration for registration is permitted.

## 11. Two-process open diagnostic

The sole execution root is:

```text
/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open
```

Its fixed children and outputs are:

```text
process A clone: /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a
process B clone: /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b
process A output: /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a-output/open/action_qbc_v7_open_diagnostic.json
process B output: /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b-output/open/action_qbc_v7_open_diagnostic.json
repository URL: file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi
```

After independently verifying that GitHub advertises the lightweight freeze tag at one
40-hex commit, the runbook substitutes that value for `<O_COMMIT>` and executes exactly:

```text
umask 077
test ! -e /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open
install -d -m 700 /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open
git clone --branch action-qbc-v7-open-diagnostic-freeze-v1 --single-branch \
  file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi \
  /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a
git clone --branch action-qbc-v7-open-diagnostic-freeze-v1 --single-branch \
  file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi \
  /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b
git -C /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a rev-parse HEAD
git -C /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b rev-parse HEAD
install -d -m 700 /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a-output/open
install -d -m 700 /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b-output/open
```

`tag_verification_step` and every `setup_steps` item have exactly `argv`, `cwd`,
`expected_exit_code`, and `expected_stdout`; null stdout means it is not compared. The tag
step uses cwd `/var/tmp`, exit 0, expected stdout
`<O_COMMIT>\trefs/tags/action-qbc-v7-open-diagnostic-freeze-v1\n`, and argv
`["git","ls-remote","--tags","https://github.com/bansarinejad/arc3-crosslevel-voi.git","refs/tags/action-qbc-v7-open-diagnostic-freeze-v1"]`. Exactly one line and absence of a
peeled `^{}` ref prove a lightweight tag.

`setup_steps` is exactly the following canonical JSON; it replaces the shell-substitution
rendering above. All stderr is retained administratively but is not an identity input.

```json
[
  {"argv":["/usr/bin/test","!","-e","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open"],"cwd":"/var/tmp","expected_exit_code":0,"expected_stdout":""},
  {"argv":["install","-d","-m","700","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open"],"cwd":"/var/tmp","expected_exit_code":0,"expected_stdout":""},
  {"argv":["git","clone","--branch","action-qbc-v7-open-diagnostic-freeze-v1","--single-branch","file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a"],"cwd":"/var/tmp","expected_exit_code":0,"expected_stdout":""},
  {"argv":["git","clone","--branch","action-qbc-v7-open-diagnostic-freeze-v1","--single-branch","file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b"],"cwd":"/var/tmp","expected_exit_code":0,"expected_stdout":""},
  {"argv":["git","-C","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a","rev-parse","HEAD"],"cwd":"/var/tmp","expected_exit_code":0,"expected_stdout":"<O_COMMIT>\n"},
  {"argv":["git","-C","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b","rev-parse","HEAD"],"cwd":"/var/tmp","expected_exit_code":0,"expected_stdout":"<O_COMMIT>\n"},
  {"argv":["install","-d","-m","700","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a-output/open"],"cwd":"/var/tmp","expected_exit_code":0,"expected_stdout":""},
  {"argv":["install","-d","-m","700","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b-output/open"],"cwd":"/var/tmp","expected_exit_code":0,"expected_stdout":""}
]
```

The setup hash covers this complete list, including working directories and expected output.
`<O_COMMIT>` is a registered literal placeholder substituted only after tag verification.

Every fixed target must be absent before this block. The roots, clones, environments, and
outputs remain on the Linux filesystem; only the credential-free read-only `file://` clone
source is under `/mnt`. No test or project import runs in either execution clone before its
registered scientific process.

After `O` is clean, tagged, pushed, and independently verified, run exactly two sequential
fresh Linux scientific processes, `A` then `B`, from two separate clones and two separately
synchronized virtual environments. Each clone checks out the exact lightweight `O` tag.
Both environments are created, in clone order, with exactly:

```text
/usr/bin/env UV_OFFLINE=1 uv sync --python 3.12.13 --frozen --no-dev --offline
```

`environment_build_argv` is exactly
`["/usr/bin/env","UV_OFFLINE=1","uv","sync","--python","3.12.13","--frozen","--no-dev","--offline"]`.

The trimmed output of `.venv/bin/python3 --version` must equal `Python 3.12.13`. The
resolved environment must contain exactly the three distributions and exact versions in
section 10. In each clone the exact preflight argv list, in order, runs `git status
--porcelain=v1 -z --untracked-files=all`, `git rev-parse HEAD`, `.venv/bin/python3
--version`, `uv --version`, and the reconstructor using `.venv/bin/python3 -I -B`. Expected
results are an empty status byte string, `<O_COMMIT>`, `Python 3.12.13`, `uv 0.11.28`, and
byte equality with the registered JSON. The reconstructor also verifies the fixed platform
and three-distribution inventory through `importlib.metadata`: normalized names and versions
must be exactly `arc3-crosslevel-voi==0.1.0`, `numpy==2.5.1`, and `pyyaml==6.0.3`, with no
fourth distribution; the project's `direct_url.json` must contain
`{"dir_info":{"editable":true}}`, while the other two must not be editable. The registered
reconstructor argv is the enforcement command and exits nonzero on any mismatch. No compiler, planner,
selector, controller, or scientific evaluator is invoked by preflight.

`preflight_argvs` is exactly:

```json
[
  ["git","status","--porcelain=v1","-z","--untracked-files=all"],
  ["git","rev-parse","HEAD"],
  [".venv/bin/python3","--version"],
  ["uv","--version"],
  [".venv/bin/python3","-I","-B","scripts/reconstruct_action_qbc_v7_open_registration.py","--repository-root",".","--registration","artifacts/action_qbc_v7_open_registration.json"]
]
```

The registered canonical scientific command template is:

```text
/usr/bin/timeout --foreground --signal=TERM --kill-after=15s 2700s \
.venv/bin/python3 -I -B \
  scripts/run_action_qbc_v7_open_diagnostic.py \
  --repository-root . \
  --registration artifacts/action_qbc_v7_open_registration.json \
  --compute-deadline-seconds 2100 \
  --wall-time-seconds 2400 \
  --output <OUTPUT_PATH>
```

`scientific_argv_template` is exactly:

```json
["/usr/bin/timeout","--foreground","--signal=TERM","--kill-after=15s","2700s",".venv/bin/python3","-I","-B","scripts/run_action_qbc_v7_open_diagnostic.py","--repository-root",".","--registration","artifacts/action_qbc_v7_open_registration.json","--compute-deadline-seconds","2100","--wall-time-seconds","2400","--output","<OUTPUT_PATH>"]
```

`<OUTPUT_PATH>` is replaced only by the corresponding absolute fixed output above. The CLI's
monotonic 2,100-second compute deadline stops new scientific work and initiates authoritative
finalization. If the complete normal candidate is unavailable, it finalizes global
`evaluator_internal_error`. Assembly and output publication must finish before the
2,400-second CLI deadline, leaving 300 seconds before the shell's 2,700-second hard bound.
Failure to publish by the CLI deadline, a hard timeout, signal, or missing output is
administrative failure, not a scientific fallback.

The runbook fixes exact clone, environment, preflight, and command text before either
scientific process. Process B starts only after A exits zero with a bounded, canonical,
schema-valid normal or fallback payload, regardless of scientific outcome. If A does not,
B is not started and the registered administrative terminal is published. There is no third
scientific process, rerun, repair, changed command, alternate environment, or post-freeze
source/schema fix.

Both payloads must independently validate and be byte-identical. Pair byte identity is
reproducibility and integrity evidence, not a second scientific observation. No scientific
row may be omitted because it failed.

The frozen finalizer is invoked once with cwd exactly
`/mnt/d/kaggle competitions/arc3-crosslevel-voi`, the original clean `O` checkout, after the
registered lifecycle, including a lifecycle that failed before a scientific start. It
independently validates registration and available payloads, byte-compares a valid pair, and uses the
transaction below for repository publication. It never executes scientific code. Its
module/import graph is standard-library-only and tests reject any project or third-party
import. The runbook requires `/usr/bin/python3` to report CPython 3.12 before setup; this
administrative interpreter is not the registered scientific environment. Its canonical
command is:

```text
/usr/bin/python3 -I -B \
  scripts/finalize_action_qbc_v7_open_diagnostic.py \
  --repository-root . \
  --registration artifacts/action_qbc_v7_open_registration.json \
  --process-a /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a-output/open/action_qbc_v7_open_diagnostic.json \
  --process-b /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b-output/open/action_qbc_v7_open_diagnostic.json \
  --process-a-exit-code <A_EXIT_CODE> \
  --process-b-exit-code <B_EXIT_CODE_OR_NULL> \
  --lifecycle-stage <STAGE_OR_NULL> \
  --publish artifacts/action_qbc_v7_open_diagnostic.json \
  --receipt artifacts/action_qbc_v7_open_diagnostic_receipt.json \
  --administrative-terminal artifacts/action_qbc_v7_open_diagnostic_administrative_terminal.json
```

`<A_EXIT_CODE>` is a decimal non-negative integer or the literal CLI string `null` when A
was not started. `<B_EXIT_CODE_OR_NULL>` has the same grammar; `null` is passed as those four
ASCII letters, without quotes. `<STAGE_OR_NULL>` is either one registered administrative
stage or the literal `null`. `finalizer_argv_template` is exactly the flattened JSON argv
list represented by this block, including all literal placeholders.

```json
["/usr/bin/python3","-I","-B","scripts/finalize_action_qbc_v7_open_diagnostic.py","--repository-root",".","--registration","artifacts/action_qbc_v7_open_registration.json","--process-a","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a-output/open/action_qbc_v7_open_diagnostic.json","--process-b","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b-output/open/action_qbc_v7_open_diagnostic.json","--process-a-exit-code","<A_EXIT_CODE>","--process-b-exit-code","<B_EXIT_CODE_OR_NULL>","--lifecycle-stage","<STAGE_OR_NULL>","--publish","artifacts/action_qbc_v7_open_diagnostic.json","--receipt","artifacts/action_qbc_v7_open_diagnostic_receipt.json","--administrative-terminal","artifacts/action_qbc_v7_open_diagnostic_administrative_terminal.json"]
```

`finalizer_cwd` is exactly `/mnt/d/kaggle competitions/arc3-crosslevel-voi`. The finalizer
therefore resolves `--repository-root .` and every relative publication path only in the
original mounted checkout; neither process clone is an eligible finalizer working directory.
The field is part of the canonical `execution_contract` registration preimage and therefore
is covered by the registration content hash.

The receipt has exactly `schema_version`, `treatment_id`, `open_freeze_commit_sha`,
`open_freeze_tag`, `registration_content_sha256`, `process_a`, `process_b`,
`payloads_byte_identical`, `published_payload_path`, `published_payload_sha256`, and
`authorization`. Each process object has exactly `label`, `output_path`, `exit_code`,
`payload_exists`, `payload_valid`, `payload_sha256`, and `payload_size_bytes`.
`authorization` is the permanent five-false object.
The receipt schema literal is `action-qbc-v7-open-diagnostic-receipt-v1`; the administrative
terminal schema literal is
`action-qbc-v7-open-diagnostic-administrative-terminal-v1`. Exit code is null if and only if
that process was not started. Hashes and sizes are null exactly when the corresponding
payload is absent or invalid. `payloads_byte_identical` is null unless both payloads validate,
false for two valid unequal payloads, and true for a valid byte-identical pair.

Instead of a receipt, any administrative failure creates the mutually exclusive
administrative-terminal artifact with exactly `schema_version`, `treatment_id`,
`open_freeze_commit_sha`, `open_freeze_tag`, `registration_content_sha256`, `stage`,
`process_a`, `process_b`, `payloads_byte_identical`, and `authorization`. Its exact stage
precedence is:

```text
tag_verification_failed
execution_root_setup_failed
clone_a_failed
clone_b_failed
environment_a_failed
environment_b_failed
preflight_a_failed
preflight_b_failed
registration_invalid
process_a_nonzero
process_a_output_missing
process_a_payload_invalid
process_b_nonzero
process_b_output_missing
process_b_payload_invalid
payload_byte_mismatch
receipt_finalization_failed
exclusive_publication_failed
publication_rollback_failed
```

Unavailable process fields are null except fixed label/path and false existence/validity.
`registration_content_sha256` is null whenever registration was not successfully validated;
otherwise it is the validated content hash. For `tag_verification_failed`,
`open_freeze_commit_sha` may be null while the tag name remains fixed.

Stage selection is one-to-one under the precedence list. A nonzero/incorrect result from the
tag step maps to `tag_verification_failed`; setup steps 1, 2, 7, or 8 map to
`execution_root_setup_failed`; clone or clone-HEAD steps map to the corresponding A/B clone
stage; and either environment build or preflight maps to its named stage. Registration validation maps to `registration_invalid`; process exit, absence, and
payload validation map to their named A/B stages; and two valid unequal bytes map to
`payload_byte_mismatch`. Failure to construct, canonicalize, validate, flush, or fsync either
staging file before any final link is `receipt_finalization_failed`. A pre-existing payload
or receipt destination while the administrative destination is absent, a payload
exclusive-link failure, or a receipt exclusive-link failure followed by a proven successful
rollback is `exclusive_publication_failed` and creates the administrative artifact. A
pre-existing administrative-terminal destination is never overwritten or adopted; it takes
the result-document-only `exclusive_publication_failed` branch regardless of the other two
destinations. A receipt-link failure is
`publication_rollback_failed` only when ownership cannot be proved or the owned payload
cannot be removed. Failure to create a previously absent administrative artifact takes the
result-document-only `receipt_finalization_failed` branch. No other condition-to-stage map is
valid.

Publication is transactional and identity-checked. The finalizer first confirms that all
three final paths are absent. In the targets' filesystem directory it exclusively creates
payload and receipt staging files, flushes and `fsync`s each, reopens, hashes, and validates
both. It then publishes the payload using an exclusive atomic hard-link/create operation and
publishes the receipt the same way. It removes only staging paths it created. It never
overwrites or removes a pre-existing path.

If receipt publication fails after payload publication, the finalizer removes the published
payload only after proving that its device, inode, and SHA-256 still match the finalizer-owned
staged payload. Successful rollback yields only an administrative terminal. If ownership
cannot be proved or removal fails, stage is `publication_rollback_failed`; the exceptional
allowed path set is the noncanonical orphan payload, administrative terminal, and result
document, with no receipt. The artifact explicitly marks the payload noncanonical. Tests
fault-inject receipt-link failure with successful rollback, rollback failure, pre-existing
destinations, and administrative-terminal creation failure.

The finalizer catches its own validation/publication exceptions and exclusively creates the
administrative artifact when the transaction rules permit. Failure of the host filesystem to
create even that artifact permits only the result-document-only terminal branch in section
12; it never permits another scientific start.

## 12. Commit, tag, and publication boundary

V7 has exactly three irreversible Git boundaries:

1. `P` is a direct child of
   `6a7f6fb25b7e676d6aff5aecaaa26de63e436481` and contains only this document. Its
   lightweight tag is
   `prereg-action-qbc-v7-open-failure-decomposition-v1`.
2. `O` descends from `P` and contains only the ten allowlisted implementation, test,
   runbook, and registration paths in section 3.1. Its lightweight tag is
   `action-qbc-v7-open-diagnostic-freeze-v1`.
3. `R` is a direct child of `O` and uses exactly one mutually exclusive path set.

   A byte-identical valid pair adds only:

   ```text
   artifacts/action_qbc_v7_open_diagnostic.json
   artifacts/action_qbc_v7_open_diagnostic_receipt.json
   docs/action_qbc_v7_open_diagnostic_result.md
   ```

   An administrative terminal adds only:

   ```text
   artifacts/action_qbc_v7_open_diagnostic_administrative_terminal.json
   docs/action_qbc_v7_open_diagnostic_result.md
   ```

   A `publication_rollback_failed` terminal exceptionally adds only:

   ```text
   artifacts/action_qbc_v7_open_diagnostic.json
   artifacts/action_qbc_v7_open_diagnostic_administrative_terminal.json
   docs/action_qbc_v7_open_diagnostic_result.md
   ```

   In that branch the payload is an explicitly noncanonical orphan and no receipt exists.

   If the host filesystem could not create even the administrative artifact, `R` adds only
   `docs/action_qbc_v7_open_diagnostic_result.md`, whose disposition is exactly
   `administrative_terminal`, whose stage is `receipt_finalization_failed`, and which records
   that no machine-readable result exists. A pre-existing administrative destination instead
   uses the same result-only path with stage `exclusive_publication_failed` and records that
   the foreign path was neither overwritten nor adopted. Except for the exact rollback-failure branch, no
   payload or receipt path may coexist with an administrative-terminal path.

   Its lightweight tag is `action-qbc-v7-open-diagnostic-result-v1`.

Every tag is pushed and independently verified as lightweight before its associated next
stage. Tags are never moved, replaced, or deleted. The canonical result is published whether
the scientific evidence is positive, mixed, negative, addressably terminal, or globally
terminal.

## 13. Theory and permissible claims

The paper may prove the following conditional selector lemma:

> Given a finite candidate sequence, a canonical-order-preserving action bijection, an
> injective relabeling of exact grid signatures that leaves game state and level delta
> unchanged, identical role-paired binary64 weight and cost payloads, and unchanged candidate
> sequence order, independently recomputed raw and compound selectors commute with the
> mapping exactly.

The isolated tests are implementation checks of that lemma's premises and conclusion. They
are not evidence that the compiler or planner satisfies those premises under a spatial
transform.

The paper may also state the finite-viewport proposition:

> Equality on the known viewport with nonzero expected exterior support cannot establish
> full finite-grid transition equality; the result must retain a censoring disposition.

Permissible empirical claims are limited to exact descriptive results such as:

- expected exterior support is boundary-consistent and censored for `X` of the 107 frozen
  overflow-cell occurrences only when the v6 failure vector and fresh index-zero positive-
  translation support total both reproduce, and if and only if the corresponding observable
  residual and metadata comparisons pass;
- the compound selector reconciles all three registered index-zero scale relations, if and
  only if the conjunction in section 4.2 passes; this is an adaptive descriptive result, not
  attribution to fixed-point arithmetic alone; and
- the isolated selector conforms or fails to conform under its explicit conditional
  premises.

No `first`, calibrated-posterior, unrestricted hidden-state, public-generalization,
runtime-readiness, active-exploration-benefit, ARC-gameplay, RHAE, private-Kaggle, admission,
or leaderboard claim may be made from v7. A complete negative diagnostic identifies the set
of earliest observed failing nodes under the frozen prerequisite DAG in section 4.1. It does not establish
that the layer is causally responsible, that changing it is necessary or sufficient, or that
any later treatment will improve gameplay.
