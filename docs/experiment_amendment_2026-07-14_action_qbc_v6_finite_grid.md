# Preregistered action-QBC v6 finite-grid evidence amendment

Date frozen: 14 July 2026 (Australia/Sydney)

Status: protocol amendment written before any v6 implementation, v2 lockbox generation,
v6 registration, permit issuance, or v6 sealed evaluation.

## 1. Purpose and disclosure

This amendment defines a new audit treatment,
`action-qbc-v6-finite-grid-evidence-v1`, and a new downstream identity,
`crosslevel-voi-runtime-v6`. Runtime-v6 initially preserves the runtime-v5 controller
mathematics byte-for-byte, but it is a distinct admission identity because its scientific
evidence contract changes. It does not modify or reinterpret the completed action-QBC v5
audit.

The v5 two-start audit is immutable negative evidence. Its frozen anchors are:

- freeze commit `c7c9c9bc4475a54fc325ce9c9104c4188889221f`;
- source-manifest SHA-256
  `421b618c0ddedfdd0187cb8927bd20c8ddfe554cf636ff5f6467e0fad0b74328`;
- registration-content SHA-256
  `978e3ed2e2eecda623a03b21792ba67af280a4573ebbafbb43a53b666e523c89`;
- registration-file SHA-256
  `1d13a85df3a49a8eb4805b6ad2ee8d1b285148b33f4e1e1b681b33605609f4ff`;
- promoted scientific-payload SHA-256
  `7bc157bd820449f09e81fbf33926e21d6be09056cdf8c729d50eb60e51b1040c`.

All twelve v5 scene batches were rejected with a redacted `ValueError` at
`scientific_record_finalization_failed`. Open-fixture diagnosis performed only after that
result reproduced this contract gap:

1. runtime comparison inspected prediction pixels and raised when a translated
   non-background cell left the finite frame;
2. the producer converted the exception to a fail-closed comparison while retaining a
   completed transformed pipeline;
3. the authoritative validator had only hashes, shapes, state, level delta, and outcome
   partitions, so it attempted a normal comparison and rejected the row;
4. atomic ten-row staging then rolled back the whole scene block.

The copied v5 payload intentionally redacts the inner exception message. The diagnosis is
therefore high-confidence engineering evidence, not proof of which hidden row first failed.
This disclosure is the reason v6 is an adaptive, post-v5 audit revision.

## 2. Claim boundary

V6 can establish only that the frozen runtime-v5 action-conditional QBC mechanism satisfies
the corrected synthetic capability audit. It cannot:

- retroactively pass or repair v5;
- turn a repeated v5 scene set into independent hidden confirmation;
- establish ARC-AGI-3 learning, gameplay performance, RHAE improvement, universality, or
  private-Kaggle generalization;
- enable model calls, generated tokens, GPU use, environment actions, reward observations,
  RHAE observations, a gameplay pilot, or the development matrix;
- automatically enable runtime-v5.

`runtime_v5_enabled`, `runtime_v6_enabled`, and `final_admission_claimed` remain false in
every single-start and pair payload. Runtime-v5 remains permanently closed. A positive v6
pair could only become an input to a later, separately preregistered runtime-v6 live admission
and development protocol; no such protocol is authorized here.

The controller mathematics, policy, compiler roles, candidate builder, planner, costs, Gibbs
weights, QBC selector, thresholds, controls, scene-family grammar, order transforms, resource
counters, and 1,200-second whole-audit wall limit are not tuned by this amendment.

V6 is a completeness-correcting audit that may remain scientifically negative. Before any
v2 lockbox is generated, every visual row in the fixed three-scene open gate must complete,
pass authoritative rederivation, and report zero translation overflow. Failure freezes v6 as
negative open engineering evidence and permanently cancels v2 generation and sealed v6
execution. This gate is not relaxed or replaced.

## 3. Finite-grid visual relation

### 3.1 Canonical grid evidence

The payload field `grid_evidence` is an object with exactly the keys `schema_version` and
`blobs`; `schema_version` is `action-qbc-v6-grid-evidence-table-v1`. `blobs` is a list sorted
lexicographically by reference key. The reference key is exactly
`<sha256>:<rows>:<columns>:int16-le-c-v1`. There is exactly one blob entry for every unique
`(sha256, rows, columns, encoding)` tuple referenced by a non-null prediction. Repeated
action-by-hypothesis prediction occurrences may and must share the same reference. Duplicate
blob entries and unreferenced blob entries are forbidden. A null prediction has a JSON null
reference and no blob. SHA-256 text is lowercase hexadecimal; dimensions are canonical ASCII
decimal without a sign or leading zero.

Every blob entry contains exactly the six JSON keys `reference`, `encoding`, `shape`,
`byte_count`, `data_base64`, and `sha256`, with these values:

- encoding `int16-le-c-v1`;
- two-dimensional shape, with each dimension in `[1,64]`;
- byte count equal to `2 * rows * columns`;
- its reference key;
- standard padded base64 with no whitespace or alternate spelling;
- SHA-256 of the decoded bytes.

Decoded bytes are signed little-endian 16-bit cells in C row-major order. Re-encoding must
reproduce the supplied base64 exactly. The evidence SHA-256 must equal the existing
`Prediction.signature()` grid-byte SHA-256 on the registered little-endian Linux platform.
V6 must not redefine prediction signatures, outcome cells, EVSI, costs, or controller
behavior.

Every non-null serialized pipeline prediction contains exactly one `grid_evidence_ref` in
addition to its existing signature digest and shape; occurrence order remains registered
action order followed by hypothesis order. The validator independently decodes every unique
referenced grid, checks its shape, byte count, canonical spelling, digest, reference key, and
corresponding pipeline prediction identity, and then checks the exact referenced set. Mapped
and unmapped action counts are over ordered base-action occurrences. Prediction-pair counts
are over ordered mapped-action-by-hypothesis occurrences. Overflow is the sum of
out-of-original-frame non-background cells over those ordered prediction-pair occurrences,
even when several occurrences share one grid blob. No comparison count is over unique blobs.

The payload cap is exactly 67,108,864 bytes. It passes when
`len(canonical_json_bytes(payload)) <= 67_108_864`; the canonical representation has no final
line feed. Measurement occurs after authoritative rederivation, acceptance construction, and
all table/set checks but before exclusive publication. If the candidate exceeds the cap, the
evaluator emits a smaller exact-schema terminal-negative payload: the grid table is empty;
all 140 rows are replaced by their registered identity-bound negative placeholders with stage
`payload_size_limit_exceeded`; `finalization_complete`, `acceptance_passes`,
`final_admission_claimed`, `runtime_v5_enabled`, and `runtime_v6_enabled` are false; and exact
top-level field `candidate_payload_size_bytes` records the observed candidate byte count as an
integer. This fallback must itself validate,
contain exactly 140 rows, and fit the same cap. Boundary tests cover cap minus one, equality,
and cap plus one. The limit is never raised after sealed exposure.

Any top-level grid-table schema failure, missing prediction reference field, dangling
reference, duplicate blob entry, orphan blob, noncanonical blob, digest mismatch, or global
reference-set mismatch uses the bounded 140-placeholder fallback with an empty grid table.
Every placeholder row has stage `grid_evidence_table_invalid`; the exact top-level fields are
`terminal_fallback_stage=grid_evidence_table_invalid` and
`candidate_payload_size_bytes=null`. There is no row-level grid-reference disposition. The
size fallback instead gives every placeholder row stage `payload_size_limit_exceeded` and has
`terminal_fallback_stage=payload_size_limit_exceeded` and the integer candidate size specified
above. Both fallbacks are schema-valid, command-successful, output-complete negative results:
the evaluator exits zero, the durable primary row authorizes the replica, and a byte-identical
pair is promoted and published regardless of scientific acceptance.

### 3.2 Palette and scale

For `palette_bijection`, the validator applies the exact registered sixteen-label forward
bijection to every cell and compares the resulting grid bytes, game state, and level delta
with the transformed prediction. A prediction cell outside `[0,15]` is a completed evaluated
non-pass with reason `prediction_label_outside_palette_domain`; it is not an exception.
The transformed palette prediction must have exactly the base prediction shape; otherwise it
is a completed evaluated non-pass with `transformed_prediction_shape_mismatch`.

For `scale_2_nearest_neighbor`, the validator repeats every row and column exactly twice and
compares the resulting grid bytes, game state, and level delta. The mapped base-action list
remains the only scale frontier; no complete-frontier claim is introduced. If `2H > 64` or
`2W > 64`, the pair is a completed evaluated non-pass with reason
`scale_output_shape_outside_prediction_domain`. A transformed shape other than exactly
`(2H,2W)` is a completed evaluated non-pass with reason
`transformed_prediction_shape_mismatch`.

### 3.3 Translation on a padded comparison canvas

Translations remain the registered deltas `(+3,+5)` and `(-3,-5)`. They do not clip, wrap,
drop, or declare any prediction inapplicable.

For an `H x W` prediction grid `G`, delta `(dr,dc)`, and registered background label `b`, let:

- `p = (abs(dr), abs(dc))`;
- padded shape `P = (H + 2*abs(dr), W + 2*abs(dc))`;
- `embed(G)` be a `b`-filled `P` canvas with `G` placed at
  `[p_row:p_row+H, p_col:p_col+W]`;
- `expected` be `embed(G_base)` shifted by `(dr,dc)` inside `P`, with `b` filling vacated
  cells and no clipping;
- `actual` be `embed(G_transformed)` on the same `P` canvas.

The prediction pair matches only when `expected` and `actual` have identical canonical bytes,
game state, and level delta. The validator also independently derives
`overflow_nonbackground_count`, the number of non-background base cells whose translated
coordinates fall outside the original `H x W` frame. A translation comparison can pass only
when this count is zero.

This is a conservative extension of v5. On v5's strict in-bounds domain it produces the same
expected grid. Outside that domain it produces a completed non-pass and cannot create a new
pass. Boundary overflow is scientific evidence, not an evaluator exception.

Base and transformed translation predictions must both have the same `H x W` shape. A shape
mismatch is a completed evaluated non-pass with reason
`transformed_prediction_shape_mismatch`. Padded internal comparison canvases may exceed
`64 x 64`; only serialized `Prediction` grids are restricted to that domain.

### 3.4 Actions and exact comparison result

Every visual row carries a compact `transform_contract` with exactly `name`,
`background_label`, `parameters`, and `contract_sha256`. The digest is over canonical JSON of
the first three fields and must equal the transform-contract digest frozen in that row's v6
registration identity. Palette parameters contain exactly a sixteen-entry forward permutation
of labels `0..15`; translation parameters contain exactly the registered signed row/column
deltas; scale parameters contain exactly factor two and
`action6_destination_cell=top_left_of_scaled_2x2_block`. Any other field, type, value, hash,
or registration mismatch is `authoritative_derivation_error` with
`transform_contract_invalid`.

The validator reconstructs the action map rather than trusting an unchecked serialized map:
palette is identity on every source coordinate, translation contains exactly the source
coordinates whose delta destination is in bounds, and scale maps every source coordinate to
the top-left cell of its doubled block. Before emitting the compact contract, the producer
must prove the manifest's full action map is byte-for-byte equal to that reconstruction. A
missing, duplicate-source, duplicate-destination, malformed/out-of-range, non-bijective, extra,
or otherwise unequal manifest map is a pre-row ingestion failure. It produces the bounded
140-placeholder payload with per-row and top-level stage `transform_action_map_invalid`, an
empty grid table, null candidate-payload size, false acceptance/admission/runtime flags, exit
zero, and the same replica/promotion semantics as the other terminal fallbacks. Such a defect
is not represented as a row-level comparison reason.

Simple actions retain the registered identity mapping. Every `ACTION6` mapping is derived
from the registered action map; unchecked arithmetic is forbidden. Bijection means one-to-one
between the exact registered partial source domain and its exact registered image, not the
whole `32 x 32` frame. A required base action absent from an otherwise valid partial map is a
completed evaluated non-pass with reason `required_action_mapping_missing`. Duplicate source,
duplicate destination, malformed/out-of-range coordinate, or a map that is not bijective over
its declared partial domain is handled by the manifest-ingestion fallback above.

The finalized `comparison` object has exactly nine JSON keys: `status`, `semantics_id`,
`mapped_action_count`, `unmapped_action_count`, `prediction_pair_count`,
`overflow_nonbackground_count`, `reasons`, `passes`, and `parity`. The semantics ID is
`action-qbc-v6-padded-finite-grid-v1`. Counts are non-negative JSON integers, reasons are a
canonical ordered de-duplicated JSON string list, and passes is a JSON Boolean.

`parity` is normally null. On producer/authority mismatch it is an object with exactly
`claimed`, `authoritative`, `claimed_sha256`, and `authoritative_sha256`. Each comparison core
has exactly six keys: the four count fields, `reasons`, and `passes`. Each SHA is the lowercase
SHA-256 of that core's canonical JSON bytes.

Status precedence is `pipeline_error`, then `authoritative_derivation_error`, then
`evaluated`. Within a status, reasons are emitted at most once in this exact order:

1. `base_pipeline_unavailable`;
2. `visual_pipeline_failed`;
3. `scientific_record_schema_invalid`;
4. `claimed_comparison_schema_invalid`;
5. `transform_contract_invalid`;
6. `required_action_mapping_missing`;
7. `mapped_action_frontier_mismatch`;
8. `compiler_role_mismatch`;
9. `gibbs_weight_mismatch`;
10. `rolewise_cost_mismatch`;
11. `invalid_root_prediction`;
12. `prediction_label_outside_palette_domain`;
13. `scale_output_shape_outside_prediction_domain`;
14. `transformed_prediction_shape_mismatch`;
15. `translation_prediction_overflow`;
16. `mapped_prediction_grid_mismatch`;
17. `mapped_prediction_state_mismatch`;
18. `mapped_prediction_level_delta_mismatch`;
19. `selector_numeric_diagnostic_mismatch`;
20. `selector_disposition_or_rank_mismatch`;
21. `mapped_controller_decision_mismatch`;
22. `mapped_robust_exploitation_set_mismatch`;
23. `mapped_myopic_utility_set_mismatch`;
24. `mapped_cross_level_utility_set_mismatch`;
25. `mapped_robust_exploitation_result_mismatch`;
26. `comparison_parity_mismatch`.

The per-status values are exact:

- `pipeline_error`: all four counts are zero, parity is null, passes is false, and reasons is
  exactly one of `["base_pipeline_unavailable"]` or `["visual_pipeline_failed"]`;
- `authoritative_derivation_error` without parity mismatch: all four counts are zero, parity
  is null, passes is false, and reasons contains only items 3 through 5 above in their fixed
  order;
- `evaluated`: parity is null, all counts are authoritative observed counts, reasons contains
  only items 6 through 25 above in fixed order, and passes is true exactly when reasons is
  empty;
- producer/authority mismatch: status is `authoritative_derivation_error`, all four outer
  counts are zero, passes is false, reasons is exactly `["comparison_parity_mismatch"]`, and
  parity preserves both six-key cores and their canonical hashes. Scientific reasons and
  counts remain only inside the preserved authoritative core.

Pipeline failure short-circuits comparison. Otherwise contract, evidence, and map validation
complete before evaluated scientific comparison. Producer parity is checked last. These
short-circuit rules make every simultaneous-failure disposition unique.

A row whose registered address remains valid but whose remaining scientific schema is
malformed becomes `scientific_record_schema_invalid`. A malformed six-key producer claim
becomes `claimed_comparison_schema_invalid`; neither defect needs to preserve the invalid
input. A row with an invalid/missing/duplicate registered address cannot be localized and uses
the 140-placeholder payload fallback with per-row/top-level stage
`scientific_record_inventory_invalid`, an empty grid table, null candidate size, and the same
complete-negative replica/promotion semantics. A null base or transformed prediction is an
`evaluated` non-pass with `invalid_root_prediction`. Transform-contract corruption uses
`authoritative_derivation_error`; grid-table corruption uses the payload fallback in section
3.1; ordinary scientific inequality uses `evaluated`.

The producer submits a six-key claimed comparison core using the frozen v6 reference
implementation. The
validator independently decodes the evidence and rederives the authoritative comparison.
Exact equality is mandatory. A mismatch produces a terminal negative row with
`comparison_parity_mismatch`; it never leaves an authoritative pass beside an ignored runtime
failure and never rolls back sibling rows. The authoritative comparison is the sole
scientific truth. All 48 registered visual rows remain mandatory; there is no `N/A`,
applicability exclusion, row drop, or generic acceptance of a caught comparison failure.

## 4. Completion and failure semantics

A scientifically negative comparison is a completed registered row. It must not roll back
its base row, sibling visual rows, or order rows. A pipeline error or authoritative derivation
error is materialized under its exact terminal negative schema and forces the relevant row
and aggregate acceptance to fail.

The accumulator still contains exactly 140 uniquely registered rows in the frozen order:
12 base, 48 visual, 60 order, and 20 control rows. Every retained row is independently schema
validated, bound to its registered identity, and then the complete inventory is revalidated.
Invalid, missing, duplicated, or noncanonical evidence fails closed. A malformed submitted
row is replaced at its registered address by an identity-bound terminal
`authoritative_derivation_error` row; already validated siblings remain retained. Completeness
never turns an invalid row into a pass.

Scientific acceptance retains the v5 minima and conjunctions. Pair byte identity is only
reproducibility/integrity evidence and is not a second scientific sample.

## 5. Open-fixture implementation gates

No sealed fixture may be generated or read until all of the following pass:

1. table tests for both deltas at the exact valid and invalid row/column boundaries, including
   background-only grids, null predictions, simple-action identity, and missing, duplicate,
   out-of-range, and non-bijective partial action maps, plus transform-contract field, value,
   digest, and registration-binding tampering; full-map defects must produce the exact
   `transform_action_map_invalid` 140-row fallback, while compact-contract defects must
   produce the exact addressable terminal row;
2. no-wrap, no-clip, padded-shift, overflow-count, palette, and scale reference tests;
3. canonical grid evidence tests for dtype, byte order, shape, byte count, base64 spelling,
   digest, repeated many-to-one references, duplicate blob entries, orphan blobs, missing
   and dangling references, and tampering; every table/reference defect must produce the exact
   `grid_evidence_table_invalid` 140-row fallback;
4. palette boundary labels `-1`, `0`, `15`, and `16`; scale outputs immediately below, at,
   and above the `64 x 64` serialized-prediction boundary; translation and scale shape
   mismatches; and the exact multi-failure status/reason precedence;
5. exact producer-versus-authoritative comparison equality for completed positive and
   completed negative visual rows;
6. one mutated claimed comparison replaced by a terminal `comparison_parity_mismatch` row
   without rolling back valid siblings, while the untouched batch completes normally;
   malformed claimed cores and addressable/unaddressable scientific-row schemas must exercise
   their separately frozen terminal dispositions;
7. a worker-free cross-platform `evaluate_scene_record -> accumulator` failed-pipeline seam;
8. a sequential Linux/WSL completed-batch matrix over the three established open families
   using seeds:
   - homologue `0x1020304050607080`;
   - containment `0x2233445566778899`;
   - reflection `0x3141592653589793`;
9. for each open family, five completed compiler/planner snapshots, ten finalized scene rows,
   ten newly completed accumulator indices, unchanged remaining placeholders, and successful
   full-inventory authoritative revalidation;
10. every one of the twelve visual rows in that three-scene matrix passes, all translation
    overflow counts are zero, and no terminal error row exists; otherwise v6 freezes negative
    and v2 generation is permanently cancelled;
11. payload-cap tests at exactly 67,108,863, 67,108,864, and 67,108,865 candidate bytes,
    including validation and size of the 140-row terminal fallback;
12. two fresh sequential Linux processes build the same open diagnostic payload containing
    exactly those three completed scene blocks, nine registered negative placeholder scene
    blocks, and twenty completed controls; both canonical payloads must be byte-identical;
13. unchanged offline/resource prohibitions and the exact open diagnostic counter vector:
    candidate-builder 12, compiler 15, compiled programs 60, completed planning snapshots 15,
    controller calls/replays 24 each, grounding evaluations 60, pool constructions 15,
    persistent/transient worker starts 60 each, total worker starts 120, planner calls 15,
    pure selector calls 73 (54 scene/order and 19 control), registered scenes read 3,
    v4 counterfactuals 3, and zero model/token/GPU/environment/network/reward/RHAE/lockbox
    operations.

The real three-family matrix runs sequentially on Linux, with pytest-xdist and all third-party
pytest plugin autoload disabled, and with an exact test-only per-scene deadline of 300 seconds.
No wall-clock performance assertion is made. The production 1,200-second cap and all sealed
scientific counters remain unchanged.

The canonical Linux gate preparation and execution commands are, in order:

```text
uv sync --frozen --extra dev
env PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --frozen --no-sync python -B -m pytest -q -p no:cacheprovider tests/test_action_qbc_v6_audit.py tests/test_action_qbc_v6_registration.py
```

The two-process diagnostic uses a separately registered CLI command and fresh exclusive
temporary output directories. The registration freezes that exact command after its CLI path
exists; changing it after the mechanism-freeze tag requires v7.

## 6. Fresh v2 evidence and preregistration

V6 will not read or reuse the v1 lockbox. A new data-only namespace will be implemented for:

- generator `action_qbc_lockbox_v2`;
- exclusive freeze wrapper `freeze_action_qbc_v2_lockbox`;
- artifact `artifacts/action_conditional_qbc_v2_lockbox.json`;
- safe identity receipt `artifacts/action_conditional_qbc_v2_lockbox_identity.json`, containing
  only schema/version, byte size, artifact/content hashes, source/gate identities, and
  registered scene identities/hashes.

The v2 generator retains the three families, four scenes per family, visual transforms, order
controls, and grammar constraints. Registered family order is exactly `homologue`,
`containment`, `reflection`; family index is the single ASCII decimal digit `0` through `3`.
After the implementation is frozen, `C` is the full lowercase forty-hex commit named by the
lightweight tag `action-qbc-v6-mechanism-freeze-v1`. For family `F` and index `I`, the seed is
the first eight bytes, interpreted as an unsigned big-endian integer, of:

```text
SHA-256(UTF-8("arc3-action-qbc-v2-seed-v1|" + C + "|" + F + "|" + I))
```

There is no salt, newline, normalization, retry, replacement, or alternate extraction. The
wrapper proves the twelve values are unique and disjoint from all v1 registered seeds. A seed
collision, generator rejection-cap exhaustion, artifact-size failure, gate-identity failure,
partial-publication failure, or any other post-freeze generation failure permanently cancels
v6 and requires v7; it never chooses another seed or runs generation again.

The generator is data-only. It may import only Python standard-library modules and its new
data-only schema helpers. It must not import, call, inspect, or serialize compiler, candidate,
planner, controller, policy, model, reward, RHAE, action-selection, cost, outcome-cell, EVSI,
or utility behavior. Rejection is limited to the preregistered geometry/schema taxonomy and
cannot depend on mechanism behavior.

The registered seeds and scenes are never evaluated outside the exclusive wrapper and the
later two permit-bound audit starts. The deterministic seed formula is not described as
secret. The artifact is generated exactly once, after v6 source and open tests are frozen, by
the reviewed exclusive wrapper. The old generator and v1 artifact are never invoked.

Before seed derivation, the wrapper requires clean HEAD at
`action-qbc-v6-mechanism-freeze-v1`, checks the exact commit, generator/wrapper/reference/audit
source hashes recorded by that commit, and validates
`artifacts/action_qbc_v6_open_gate.json`. That gate attestation binds the canonical Linux
command, exit status, exact test-file/source hashes, exact counter vector, both fresh-process
diagnostic payload hashes, and the required all-visual-pass/zero-overflow conclusion. Any
mismatch occurs before seed evaluation.

Artifact and identity receipt use exclusive final paths and same-directory staging files with
mode `0600`, file and directory fsync, canonical bytes, and no overwrite. Neither final path
may exist before generation. The artifact is published first and the receipt second. If the
process stops after either final publication or leaves any staging path, the run is terminal:
the operator preserves every path and does not invoke the wrapper again.

The v6 registration, evaluator, permit, exposure, ledger, issuance, pair-attestation,
promotion, receipt, command, output, and result schemas all receive new v6 identities. Every
v6 administrative boundary rejects v5 roots, permits, schemas, registrations, outputs, and
commands before any sealed-artifact operation.

V6 uses a wholly disjoint Linux namespace rooted at:

`/var/tmp/arc3-crosslevel-voi-action-qbc-v6`

No v6 command may create, list, stat, resolve, search, hash, or otherwise inspect the preserved
v5 root `/var/tmp/arc3-crosslevel-voi`. V5-root/schema/path rejection uses lexical normalized
token comparison before any filesystem resolution or metadata operation. Git searches and
clean checks must exclude both the v1 and v2 lockbox artifact paths.

## 7. Irreversible-run protocol

After implementation and independent source/registration reconstruction:

1. freeze and push a lightweight v6 audit tag;
2. verify local and remote tag/commit identity and the unchanged v5 tag;
3. create two fresh clones, environments, output roots, and one singleton v6 permit set under
   the disjoint v6 root;
4. run primary exactly once;
5. require one command-successful, output-complete, schema-valid, durable primary ledger row;
   scientific acceptance is not required to authorize the replica;
6. run replica exactly once;
7. require exactly two ordered ledger rows and byte-identical canonical payloads;
8. promote and publish every command-complete, schema-valid, byte-identical pair regardless of
   scientific acceptance or disposition, then commit exactly the v6 payload, receipt, and
   result document as a direct child of the v6 freeze commit;
9. preserve all v6 state permanently.

There is no third start, cleanup, permit reissue, repair, or rerun. An irreversible failure
requires a new v7 treatment. The replica verifies bytes only.

## 8. Fixed implementation boundary

All v5 frozen source files, protocol, runbook, registration, lockbox, promoted artifacts,
tag, and bound state remain byte-untouched. V6 is implemented copy-on-write in newly named
files. The intended new targets are:

- `src/arc3_voi/action_qbc_v6_reference.py`;
- `src/arc3_voi/action_qbc_v6_audit.py`;
- `tests/test_action_qbc_v6_audit.py`;
- `tests/test_action_qbc_v6_registration.py`;
- `scripts/build_action_qbc_v6_audit_registration.py`;
- `scripts/audit_action_qbc_v6_lockbox.py`;
- `docs/action_qbc_v6_sealed_audit_runbook.md`;
- newly namespaced v2 generator/wrapper, registration, payload, receipt, and result paths.

This amendment itself must be committed and tagged before any of those implementation files
are created. Its preregistration tag is exactly
`prereg-action-qbc-v6-finite-grid-evidence-v1`; the later implementation tag is exactly
`action-qbc-v6-mechanism-freeze-v1`, and the still-later sealed-audit tag receives a distinct
identity fixed by the v6 registration before permit issuance.
