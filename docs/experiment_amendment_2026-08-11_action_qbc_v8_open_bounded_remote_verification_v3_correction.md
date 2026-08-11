# Action-QBC v8 P8v3 minimal-honest administrative correction

Correction freeze: 11 August 2026 (Australia/Sydney)

Status: preregistration-only administrative correction. No O8 registration, O8 commit or
tag, execution root, remote-verification artifact, lifecycle claim, arm receipt, scientific
start, payload, finalization bundle, R8 object, or v8 scientific observation existed when
this document was written.

## 1. Authority, ancestry, and scope

This document corrects and otherwise incorporates the complete protocol in
`docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification.md`.
The incorporated document is the sole file modified by the binding P8v2 commit
`91c5ba1862fc7701ed2276ddd64b99fdb8b7ad1d`, whose parent is the superseded P8v1 commit
`ebf6031a284ecbffb53ba1582124b7e4c9eb3e56`. P8v2 is tagged with the immutable lightweight
tag `prereg-action-qbc-v8-open-bounded-remote-verification-v2`.

The commit made from this new document alone is `P8v3`. It must be a direct child of P8v2,
add exactly this one path, and modify, delete, or rename no P8v2 path. Its immutable
lightweight tag is:

```text
prereg-action-qbc-v8-open-bounded-remote-verification-v3
```

`P8v3_COMMIT`, `P8v3_DOCUMENT_GIT_BLOB_SHA1`, `P8v3_DOCUMENT_SHA256`, and
`P8v3_DOCUMENT_BYTE_COUNT` below mean the values obtained from the committed bytes of this
path after P8v3 exists. They are identities, not choices. O8 must be a direct child of P8v3
and add exactly the same fifteen O8 paths listed in section 5 of the incorporated protocol.
No path present at P8v3 may change at O8. The O8 and R8 lightweight tag names remain:

```text
action-qbc-v8-open-diagnostic-freeze-v1
action-qbc-v8-open-diagnostic-result-v1
```

All executable v8 identities use P8v3, the v3 preregistration tag, and this document path.
The section-4.1 deterministic v7-to-v8 source transformation is unchanged except for these
administrative outputs:

```text
preregistration tag  = prereg-action-qbc-v8-open-bounded-remote-verification-v3
preregistration SHA  = P8v3_COMMIT
document path        = docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification_v3_correction.md
document Git blob    = P8v3_DOCUMENT_GIT_BLOB_SHA1
document SHA-256     = P8v3_DOCUMENT_SHA256
document byte count  = P8v3_DOCUMENT_BYTE_COUNT
```

The pre-O8 registration producer substitutes the v3 tag in its exact argv. The
reconstructor verifies the complete ancestry R7 -> P8v1 -> P8v2 -> P8v3 -> O8, the exact
one-file diffs at each preregistration boundary, both superseded lightweight tags, the v3
lightweight tag, and this document's object identities. P8v1 and P8v2 remain immutable
audit history and are not described as executed protocols.

This correction changes administrative evidence, filesystem checks, command binding,
timing evidence, and failure handling only. The treatment ID, diagnostic ID, comparison
semantics, all 140 scientific rows, all twelve public scenes, every transform and control,
every scientific function body, every datum, selector, tolerance, reason, fallback,
scientific resource counter, scientific analysis rule, frozen dependency, scientific
payload field, scientific payload limit, and the
2,100/2,400/2,700-second scientific limits remain exactly as incorporated. The flat
nineteen-key payload schema remains `action-qbc-v8-open-diagnostic-payload-v1`. A and B
remain two deterministic observations of that single unchanged treatment. Any scientific
change requires a new v9 preregistration.

## 2. Complete pre-O8 disclosure and claim boundary

Before P8v3, fourteen intended non-registration O8 additions had been authored as untracked
files. Static inspection, lint/type checks, unit tests, and synthetic temporary-directory
tests were used to find administrative design defects. The intended registration file had
not been generated or staged. No O8 commit/tag, v8 execution root, real preparation or
preparation-verification receipt, Windows remote claim/receipt, arm receipt, lifecycle
claim/ledger, scientific start claim, complete scientific producer call, extension-scene
snapshot, payload, result bundle, R8 object/ref, or v8 scientific result existed. The only
live host fact newly relevant to P8v2 remained the already disclosed exact
`/usr/local/bin/uv --version` stdout. No private or extension-scene scientific outcome was
observed.

The review found that P8v2's preparation receipt retained only a digest of an insufficiently
specified command history, its independent preparation check was not required to persist a
receipt, later runners were not required to recompute their own complete venv materialization
identity, several duration validators could confuse a configured deadline with actual
elapsed cleanup time, and filesystem language could be read as stronger than the supported
threat model. These are pre-execution administrative defects. Correcting them before O8 is
not result-dependent repair.

No source file, test, synthetic transcript, shell history, Git reflog, or statement in this
document is historical proof that a command ran. The post-O8 receipts specified below are
contemporaneous process-produced records whose bytes and consistency are checked; they are
not cryptographic attestation and do not prove facts against a malicious actor with the same
OS authority.

## 3. Explicit threat model

The protocol addresses deterministic implementation mistakes, accidental duplicate starts,
ordinary crashes, bounded child hangs, stale owned scratch from an interrupted publication,
path confusion, unintended inherited configuration, non-malicious concurrent activity by
the same interactive user, and symlink or inode substitution detectable at the required
check points. It assumes:

- the Windows and Linux kernels, local storage, CPython, frozen executable bytes, Git object
  hashing, and GitHub's returned ref bytes behave as specified;
- the operator follows the registered argv without editing it;
- no process with the same Windows account or Linux UID maliciously races, replaces,
  truncates, ptraces, debugs, or rewrites protocol processes, open files, directories, Git
  objects, refs, claims, receipts, or environment state;
- no administrator, root process, kernel component, storage controller, or hardware fault
  acts adversarially.

Linux owner/mode checks, `O_NOFOLLOW`, directory file descriptors, exclusive creation,
reopen/hash checks, fsync, and inode revalidation are fail-closed engineering controls under
that non-malicious-same-UID model. They are not tamper-proofing: the owning UID can normally
modify owned files and can attack another same-UID process in ways this protocol cannot
exclude.

Windows provides no claim here equivalent to POSIX directory fsync, stable Linux inode
semantics, or a complete reparse-point-race exclusion. The Windows supervisor uses fixed
absolute paths, an empty explicit child environment, exclusive destination creation,
flush/`os.fsync`, reopen/hash/canonical checks, a private Job Object, and the same interactive
account. These establish bounded consistency checks against mistakes and ordinary failure,
not durability across every power-loss pattern and not resistance to a malicious same-user
process. The final paper and runbook must repeat these limitations and may not use
`tamper-proof`, `secure enclave`, `attested`, or an equivalent claim.

## 4. Canonical preparation receipt v2

The preparation receipt schema changes from
`action-qbc-v8-preparation-receipt-v1` to:

```text
action-qbc-v8-preparation-receipt-v2
```

It has exactly these top-level keys:

```text
schema_version
treatment_id
open_freeze_commit_sha
open_freeze_tag
registration_content_sha256
attempts
authority
process_a
process_b
command_ledger
commands_sha256
command_environment_sha256
status
```

Canonical JSON throughout this correction means sorted-key, compact, ASCII JSON with no
NaN and no final line feed. `command_ledger` is an ordered array. `commands_sha256` is
SHA-256 of the canonical bytes of that entire array; it is never a digest of a reconstructed
or intended command list. `command_environment_sha256` is SHA-256 of the exact registered
`preparation_command_environment` object and is never null. `status` is exactly `prepared`
or `failed`. Attempt records retain
the exact P8v2 keys and process-stage order. A second attempt remains allowed only after the
first attempt's verified-owned cleanup passes. A `prepared` receipt has one passing attempt
and both promoted process objects. Atomic promotion is the irreversible preparation commit
point. A canonical `failed` receipt may be published only before promotion and has
`process_a=null`, `process_b=null`, no promoted `processes` parent, and complete records for
all actions actually attempted. If an error, crash, or fsync/publication failure occurs after
promotion but before a canonical prepared receipt is durable, preparation exits or is
aborted with the promoted parent left intact and no failed receipt invented. The independent
verifier cannot pass, the supervisor is forbidden, and the run is abandoned pre-lifecycle;
neither cleanup nor a second preparation invocation may adopt or remove that state.

Each `authority`, `process_a`, and `process_b` clone object has exactly:

```text
root
root_device
root_inode
root_owner_uid
root_mode
head_sha
tree_sha256
raw_materialization_sha256
git_status_sha256
python_version
uv_version
environment_inventory
environment_inventory_sha256
venv_materialization_sha256
venv_python_sha256
passes
```

The four root identity integers are obtained from `fstat` on a no-follow directory
descriptor. `root_mode` is the permission-bit integer. Authority's `python_version`,
`uv_version`, `environment_inventory`, `environment_inventory_sha256`,
`venv_materialization_sha256`, and `venv_python_sha256` are all null. For each prepared process they are all non-null,
the two version strings equal the frozen values, and the compact distribution inventory is
embedded. A and B `venv_python_sha256` values must be equal; their full venv-materialization
hashes are not required to be equal. No other clone-object member is nullable in a complete
object.

The field named `environment_inventory` is specifically a compact installed-distribution
RECORD inventory, not a claim to represent every byte or semantic property of the Python
environment. It is a name-sorted array of exact distribution objects. Each object has
exactly `normalized_name`, `version`, `file_count`, and `files_sha256`.
`normalized_name` is lowercase PEP 503 normalization. `files_sha256` hashes the canonical
path-sorted array of exact objects with `path`, `size_bytes`, and `sha256` for every regular
installed distribution file; that larger per-file array is recomputed but is not embedded.
Raw RECORD names may contain dot-dot components such as `../../../bin/f2py`. Each is joined
to its containing site-packages root, lexically normalized without following symlinks,
required to remain beneath the same `.venv`, and stored as the resulting normalized path
relative to `.venv`. The target is then opened component by component from the `.venv`
directory descriptor without following any symlink ancestor; an unsafe ancestor or target
fails rather than reading outside the venv. Raw and normalized names must decode/encode as
strict UTF-8; non-UTF-8 bytes fail. Stored paths contain no empty, dot, dot-dot, backslash, or absolute
component. `file_count` is the exact array length. `environment_inventory_sha256` hashes
the canonical compact distribution array. Duplicate normalized names or file paths fail.
The inventory must be exactly the distributions and versions installed by the frozen lock;
it supplies semantic distribution comparability, not a substitute for the lock, raw audit,
or complete venv materialization evidence.

`venv_materialization_sha256` hashes a canonical recursive inventory of every entry beneath
the clone's `.venv`, sorted by relative UTF-8 path bytes. Each entry has exactly `path`,
`type`, `mode`, `size_bytes`, `sha256`, and `symlink_target`. `type` is `directory`,
`regular`, or `symlink`. Permission-bit `mode` is always an integer. A regular entry has
nonnegative `size_bytes` and its byte SHA-256, with `symlink_target=null`; a symlink has the
exact uninterpreted link target and null size/hash; a directory has all three nullable
payload members null. Sockets, devices, FIFOs, unknown types, duplicate paths, paths with an
empty/dot/dot-dot/backslash/absolute component, and enumerated paths escaping `.venv` fail. The
canonical entry array is not embedded because it can be large. A and B hashes need not be
equal: generated scripts or metadata may contain their distinct absolute clone roots. Each
hash is compared only with a fresh recomputation for that same clone by authority and later
by its own runner. Traversal never follows a symlink. Its target is recorded as uninterpreted
strict-UTF-8 link text and may be absolute or external, as uv-managed interpreter links
normally are; a non-UTF-8 entry name or target fails. Canonical JSON remains ASCII.

`venv_python_sha256` is SHA-256 of the resolved regular executable bytes reached by the
literal `.venv/bin/python3` link chain. The exact `Python 3.12.13\n` stdout, link chain,
regular-file type, and executable bytes are recomputed by independent verification and by
the owning runner; A and B executable hashes must be equal. The registration binds the
system Python and uv tools, not these later uv-managed CPython bytes. Their provenance is
the preregistered frozen/offline uv construction plus the resulting receipt and live checks,
not a pre-O8 executable-byte claim.

Each `command_ledger` object has exactly these nineteen keys:

```text
sequence_index
attempt_index
label
phase
cwd
argv
argv_sha256
stdin_size_bytes
stdin_sha256
started
exit_code
outcome
timed_out
duration_milliseconds
stdout_size_bytes
stdout_sha256
stderr_size_bytes
stderr_sha256
child_cleanup_passes
```

`sequence_index` is contiguous from zero in actual attempt order. `attempt_index` is one or
two for an attempt-owned command and null only for an authority-wide validation command.
`label` is `authority`, `A`, `B`, or null exactly as fixed by the registered arrays and the
deterministic per-attempt command automaton in this section.
`phase` is one of `clone`, `git_config`, `checkout`, `raw_audit`, `environment_build`, or
`preflight`, and ledger order must be an allowed prefix of that plan. Internal exclusive
directory creation, promotion, and owned cleanup remain represented by the attempt's
existing `promotion` and `cleanup` objects rather than being misrepresented as subprocesses.

`cwd` is an absolute fixed or deterministically derived Linux path, including the exact
attempt staging path where applicable. `argv` is the fully substituted string array
passed to the child, and `argv_sha256` hashes its canonical array. Every preparation child
uses the one exact `execution_contract.preparation_command_environment` mapping in section
8, constructed from empty. Top-level `command_environment_sha256` hashes that canonical
mapping. A mismatch fails; per-row copies or alternative environment names are forbidden.
`stdin_size_bytes` and `stdin_sha256` describe the complete intended materialized input.
When a child starts, exactly those bytes are supplied. Deliberately empty stdin is represented
by size zero and SHA-256 of the empty byte string, never null.
The nonempty `git cat-file --batch` request stream is therefore bound without embedding it.
Every command admitted by the deterministic automaton gets one record, including a
pre-spawn `stdin_limit` rejection or spawn failure. A later command that is never admitted
after an earlier terminal outcome has no record.

For a spawned child, `started=true` and `outcome` is exactly `completed`, `nonzero`,
`timeout`, `stdout_limit`, or `stderr_limit`. `completed` requires actual exit zero;
`nonzero` requires an actual nonzero exit. For spawn failure,
`started=false`, `exit_code=null`, `outcome=spawn_error`, `timed_out=false`, both stream
objects describe the complete empty bytes, and `child_cleanup_passes=null`. `exit_code` is
the actual integer return observed from the child, including a negative signal return, and
is null when no child was spawned or no actual return was obtained after forced cleanup. In
particular, neither 127 for spawn failure nor 124 for timeout is synthesized. If intended
stdin exceeds its registered cap, `started=false`, `exit_code=null`, `outcome=stdin_limit`,
`timed_out=false`, no bytes are supplied to a child, output streams are empty, and cleanup is
null. The readers/controller retain independent `stdout_overflow`, `stderr_overflow`, and
`timeout_initiated` facts. After both capture threads report, outcome precedence is exactly `stdout_limit`, then
`stderr_limit`, then `timeout`; otherwise exit zero/nonzero decides. `timed_out=true` exactly
when `timeout_initiated=true`, even if a higher-precedence stream outcome
is exposed. This classification is independent of reader chunk timing.
`child_cleanup_passes` is a Boolean exactly when forced tree cleanup was required and is null
otherwise. Cleanup failure never replaces the initiating outcome: it is represented by
`child_cleanup_passes=false`. Stdin, stdout, and stderr are represented only by actual byte count and SHA-256;
the receipt does not embed or Base64-encode command streams. The universal registered caps
are 1,048,576 stdin bytes, 134,217,728 stdout bytes, and 1,048,576 stderr bytes. Raw-audit
`git cat-file --batch` can therefore stream and hash the roughly 54 MiB O8 object response
and is not subject to the Windows verifier's 4,096-byte cap. A successful command's
size/hash cover its complete stream. On stdout/stderr overflow the reader hashes and counts
exactly the first `cap+1` bytes, stops reading that stream, initiates forced cleanup, and
never includes a chunk-dependent longer prefix; those fields are not described as the
child's complete possible output. The independent verifier
recomputes read-only outputs/current state; the ledger is contemporaneous evidence, not
proof of historical causality.

`duration_milliseconds` is the nonnegative integer floor of the actual monotonic nanoseconds
from one epoch immediately before input-cap/admission evaluation (and therefore before any
later spawn attempt) until rejection, child return, or required cleanup. It is never clamped to a command, attempt, cleanup, or
driver limit. Stdin rejection and spawn failure therefore have actual, possibly zero,
durations. Command classifications,
preparation process stages, attempt `passes`, receipt `status`, and every later
administrative stage are derived from these observed outcomes plus independently verified
filesystem state. There is no `--stage`, `--status`, `--exit-code`, or comparable
operator-supplied outcome argument.

The preparation process can record only children it owns. The earlier operator/bootstrap
Git commands are intentionally not backfilled into this ledger. Their resulting authority
state is established by the live independent verification in section 5, not by a claim that
the receipt observed their historical execution.

## 5. Persisted independent preparation verification

The execution contract adds this path:

```text
/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/preparation-verification.json
```

After the sole preparation process exits zero and before the Windows supervisor is allowed,
authority invokes exactly once:

```json
["/usr/bin/python3","-I","-B","scripts/reconstruct_action_qbc_v8_open_registration.py","--repository-root",".","--registration","artifacts/action_qbc_v8_open_registration.json","--verify-preparation","--preparation-receipt","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/preparation-receipt.json","--verification-receipt","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/preparation-verification.json"]
```

The independent standard-library verifier first validates its own raw O8 bytes, fixed argv,
registration, P8v3/O8 ancestry, and preparation receipt v2. It then recomputes live, without
calling or importing a scientific module: authority and both process root identities; exact
HEAD/tag/tree; every tracked raw byte; exact Git status; the permitted `.venv` boundary;
both Python/uv versions; each compact installed-distribution RECORD inventory; each complete
venv materialization inventory; and both empty fixed output parents. It compares recomputed values to the receipt
and registration. Reading a stored digest without recomputing its preimage is not
verification.

On complete success only, it exclusively creates, fsyncs, reopens, hashes, and validates a
canonical receipt with schema:

```text
action-qbc-v8-preparation-verification-receipt-v1
```

The receipt has exactly:

```text
schema_version
treatment_id
open_freeze_commit_sha
open_freeze_tag
registration_content_sha256
preparation_receipt_sha256
verification_argv_sha256
authority
process_a
process_b
status
content_sha256
```

`content_sha256` hashes the canonical object containing the preceding fields.
`preparation_receipt_sha256` hashes the exact validated receipt bytes.
`verification_argv_sha256` hashes the exact argv above. `status` is exactly `verified`; a
failure exits nonzero and leaves the verification-receipt destination absent. There is no
verification retry and no failed receipt is adopted.

The three clone objects have the same exact keys as the preparation clone objects except
that `environment_inventory` is omitted; each compact distribution hash, complete venv
materialization hash, and resolved venv-Python hash is freshly recomputed and matched to the
preparation receipt for that same clone. Authority's five environment/venv members remain null. `passes` is true for all
three in a published receipt. Successful publication also requires fresh no-follow checks
that the execution root and both fixed output parents are the expected plain owner-controlled
mode-0700 directories and that both output parents are empty; their device/inode values are
not persisted as a new cross-component schema.

The Windows supervisor is forbidden unless preparation and this independent verifier both
exit zero and the persisted verification receipt reopens as canonical. Failure remains
pre-lifecycle unarmed preparation: no Windows lifecycle claim, remote query, driver,
science, finalizer, or R8 is permitted, and a later attempt requires a new preregistration.

## 6. Arm receipt v2 and downstream evidence

The arm schema changes from `action-qbc-v8-arm-receipt-v1` to:

```text
action-qbc-v8-arm-receipt-v2
```

The exact arm, lifecycle-driver execute, and finalizer argvs insert this pair immediately
after their existing `--preparation-receipt <PATH>` pair:

```text
--preparation-verification-receipt
/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/preparation-verification.json
```

Each A/B scientific runner inserts the same pair immediately after
`--registration artifacts/action_qbc_v8_open_registration.json`. Payload-validator argvs do
not receive the pair and remain unchanged; they validate the resulting start/arm chain. The
path is not user-selectable. Each runner uses it before its start claim as specified in
section 7.

Arm receipt v2 has exactly:

```text
schema_version
treatment_id
open_freeze_commit_sha
registration_content_sha256
preparation_receipt_exists
preparation_receipt_read_status
preparation_receipt_sha256
preparation_verification_receipt_exists
preparation_verification_receipt_read_status
preparation_verification_receipt_sha256
remote_claim_sha256
remote_verifier_claim_sha256
remote_receipt_sha256
remote_supervisor_receipt_sha256
status
```

Each `*_exists` value is false exactly for an absent fixed basename and true when directory
enumeration finds an entry. Each adjacent `*_read_status` is exactly `absent`, `readable`,
`unsafe_type`, `oversized`, `read_error`, or `changed_during_read`. `absent` pairs with false
and a null SHA; `readable` pairs with true and SHA-256 of stable no-follow regular-file bytes;
every other status pairs with true and a null SHA. The fixed administrative evidence read
cap is 67,108,864 bytes. A no-follow `fstat` before and after the read must agree on type,
device, inode, owner, mode, size, and modification/change times before `readable` is allowed.
Thus an unsafe existing path is recorded without pretending its bytes were read. `status=armed`
requires both canonical receipts, the verification receipt's exact binding to the
preparation receipt, fresh no-follow validation of the fixed execution/output directories,
and the complete mutually valid verified remote set. Otherwise status is `failed`. The arm
process
never repairs, replaces, or regenerates either preparation receipt.

For the incorporated remote hash-only members, a SHA is likewise present only after a safe,
stable regular-file read. Null means that usable bytes were unavailable and does not by
itself assert path absence; arm status and finalizer path inspection determine the failure.

Two new independently derived stages are inserted at the beginning of the incorporated
underlying-stage precedence:

```text
preparation_receipt_invalid
preparation_verification_invalid
```

They apply only after the irreversible Windows lifecycle claim exists. A failure before
that claim remains unarmed preparation and is not an R8 result. All later incorporated
underlying stages retain their relative order. No ledger value chooses a stage: the driver
and finalizer derive it independently from canonical artifacts, raw existence/hashes,
actual child returns, and the fixed precedence, then require the ledger to agree.

The successful result schema becomes
`action-qbc-v8-open-diagnostic-receipt-v2`; the administrative terminal becomes
`action-qbc-v8-open-diagnostic-administrative-terminal-v2`. Their common exact key set is:

```text
schema_version
treatment_id
open_freeze_commit_sha
open_freeze_tag
registration_content_sha256
preparation_receipt
preparation_receipt_exists
preparation_receipt_read_status
preparation_receipt_sha256
preparation_verification_receipt
preparation_verification_receipt_exists
preparation_verification_receipt_read_status
preparation_verification_receipt_sha256
remote_verification_claim
remote_verifier_claim
remote_verification_receipt
remote_supervisor_receipt
arm_receipt
lifecycle_driver_claim
lifecycle_ledger
process_a
process_b
payloads_byte_identical
```

The successful receipt then has exactly `published_payload_path`,
`published_payload_sha256`, and `authorization`. The administrative terminal instead has
exactly `stage` and `authorization`. A receipt object is embedded only when complete and
canonical; otherwise it is null. The adjacent exists/status/SHA triples follow the arm rule,
so unsafe existing evidence remains machine-recordable without a fabricated digest. A scientific result requires both embedded
preparation objects, their exact hash chain through arm v2, and fresh finalizer validation.
An administrative terminal retains whatever canonical objects and read-state evidence exist.

The normal finalization-bundle schema and file-object schema remain v1 because their shape
does not change. The emergency bundle changes to
`action-qbc-v8-emergency-result-bundle-v2` and has exactly this key set:

```text
schema_version
treatment_id
open_freeze_commit_sha
registration_content_sha256
disposition
stage
underlying_stage
finalizer_classification
finalizer_exit_code
finalizer_timed_out
finalizer_child_cleanup_passes
finalization_bundle_exists
finalization_bundle_sha256
lifecycle_ledger_exists
lifecycle_ledger_sha256
preparation_receipt_exists
preparation_receipt_read_status
preparation_receipt_sha256
preparation_verification_receipt_exists
preparation_verification_receipt_read_status
preparation_verification_receipt_sha256
files
authorization
content_sha256
```

Each triple follows the same exact read-state rule above. The emergency bundle also has
`finalizer_classification` with exactly one of
`spawn_error`, `deadline_admission_failed`, `timeout`, `nonzero`, `child_cleanup_failed`,
`spawned_no_return`, or `bundle_invalid`. Their exact evidence table is:

| Classification | Exact trigger | Exit | Timed out | Cleanup |
|---|---|---:|---:|---:|
| `deadline_admission_failed` | complete finalizer allowance did not fit, so no spawn | null | null | null |
| `spawn_error` | process creation raised before a child existed | null | null | null |
| `timeout` | the GNU timeout wrapper returned 124 or the driver initiated its timeout path, and required cleanup did not fail | actual or null | true | null or true |
| `nonzero` | an actual nonzero return was observed, no timeout was initiated, and the wrapper did not return 124 | actual | false | null |
| `bundle_invalid` | actual return zero but the normal bundle was absent or invalid | 0 | false | null |
| `spawned_no_return` | child started, no return was obtained, no timeout initiated, and forced cleanup confirmed the tree gone | null | false | true |
| `child_cleanup_failed` | required driver cleanup did not confirm the process tree gone; this classification takes precedence | actual or null | true or false | false |

`finalizer_timed_out` and `finalizer_child_cleanup_passes` are the last two table columns. A
`timeout` exit is the actual observed integer, including 124 or a negative signal return, or
null when no return was obtained; 124 is never synthesized. `child_cleanup_failed` is the
exclusive classification whenever required cleanup is false, including after a timeout.
Any combination outside the table is noncanonical. All other incorporated emergency fields
and semantics remain unchanged. Its deterministic document records both preparation
existence/read-state/hash triples, the classification, and the existing ledger/bundle evidence.

For the incorporated `finalization_bundle_exists`/SHA and `lifecycle_ledger_exists`/SHA
pairs, false requires absence and a null SHA; true plus a non-null SHA means stable safe
regular bytes, while true plus null truthfully means an unsafe, oversized, unreadable, or
changing existing entry. The emergency renderer never invents a digest.

## 7. Per-runner live gate and complete payload parity

Before exclusive start-claim creation, each runner independently reopens and revalidates
only its own fixed process clone and output parent. In addition to every incorporated
precondition, it must:

1. validate preparation receipt v2, the persisted verification receipt, arm v2, and their
   complete raw-hash chain;
2. open the clone root and its registered ancestors by no-follow directory descriptors and
   match the root device, inode, owner UID, and mode recorded by independent verification;
3. resolve HEAD and the lightweight O8 tag with replacement objects disabled, recompute the
   O8 tree and every tracked raw materialized byte, require clean status, and permit only the
   registered plain `.venv` directory;
4. recompute the compact installed-distribution RECORD inventory and the complete recursive
   venv materialization hash for that clone, match both preparation and independent
   verification evidence, resolve and hash `.venv/bin/python3`, require the A/B interpreter
   hash contract, and recheck the exact Python and uv version identities;
5. open its own literal fixed output parent by no-follow descriptor, require the registered
   owner/type/mode policy, and require it empty before claiming a start.

Any failure occurs before audit-module import and before a scientific start. These are
validation requirements, so the existing `action-qbc-v8-scientific-start-claim-v1` shape is
retained. Its existence means the fixed O8 code path completed those checks under the stated
threat model; it is not external attestation. B still additionally requires the exact valid
A-validation receipt.

Full payload parity means literal equality of the complete canonical payload bytes after
each payload independently passes the complete nineteen-key v1 schema, every nested schema,
all semantic checks, the byte cap, and all resource counters. No key is removed, masked,
normalized, reordered, defaulted, or compared through a subset. Equality requires equal
length, SHA-256, and bytes. A mismatch anywhere, including an identity, authorization,
fallback, row, aggregate, evidence, terminal, size, or counter field, is
`payload_byte_mismatch`; neither payload is published as the scientific result. The
published successful payload bytes are exactly A's already validated bytes and must be
byte-identical to B's.

## 8. Exact command anchors and Git isolation

The registration remains `action-qbc-v8-open-registration-v1` because no v8 registration
artifact has yet existed. Its execution contract adds exactly
`preparation_verification_receipt_path`, `preparation_command_environment`, and
`preparation_command_policy`. The existing
`post_preparation_validation_argv` becomes the exact section-5 argv, and the existing arm,
lifecycle-driver, scientific-template, and finalizer argv fields receive the fixed pair at
the exact positions in section 6. No `operator_command_plan`, generic filesystem
policy object, or parallel argv schema is added.

The existing `argv_hashes` object retains exactly these keys in canonical key order:

```text
arm
bootstrap
environment_build
finalizer
lifecycle_driver
linux_host_launcher
payload_validator
post_preparation_validation
preflight
preparation
producer
reconstructor
remote_supervisor
remote_verifier
result_publisher
result_ref_transaction
scientific
tests
```

Each value remains SHA-256 of the corresponding complete registered array/object after the
v3 corrections. Templates are closed by the already registered label/path/prior/output
tables; the driver constructs exactly four concrete arrays—A/B runner and A/B validator—and validates each
resulting hash before spawn. The runbook reproduces the exact bootstrap, preparation,
independent-verification, Windows-supervisor, lifecycle, publication-only, local-transfer,
push, and remote-check argv arrays verbatim from these existing registration fields. They
are passed directly without shell retokenization. Runbook display is not historical proof
of execution, and no new show-command interface is introduced.

`preparation_command_environment` is exactly this string mapping:

```text
PATH=/usr/bin:/bin
HOME=/home/bansarinejad
XDG_CONFIG_HOME=/nonexistent
LANG=C
LC_ALL=C
TZ=UTC
GIT_CONFIG_NOSYSTEM=1
GIT_CONFIG_GLOBAL=/dev/null
GIT_CONFIG_COUNT=0
GIT_NO_REPLACE_OBJECTS=1
GIT_TERMINAL_PROMPT=0
PYTHONHASHSEED=0
PYTHONNOUSERSITE=1
PYTHONDONTWRITEBYTECODE=1
UV_CACHE_DIR=/home/bansarinejad/.cache/uv
UV_NO_PROGRESS=1
UV_PYTHON_DOWNLOADS=never
```

`preparation_command_policy` has exactly:

```text
default_timeout_seconds=60
environment_timeout_seconds=600
term_grace_seconds=5
kill_grace_seconds=5
stdin_cap_bytes=1048576
stdout_cap_bytes=134217728
stderr_cap_bytes=1048576
```

Every preparation child receives exactly that mapping constructed from empty. The exact
environment-build argv retains `/usr/bin/env UV_OFFLINE=1 ... --offline`; `UV_OFFLINE` is not
silently added to the base map. The fixed cache path is an explicitly disclosed local
offline substrate under the same non-malicious UID; the frozen lock, compact distribution
inventory, full venv hash, and live interpreter check validate the result. Every unlisted
member is absent, including inherited `GIT_*`, `UV_*`, `PYTHONPATH`, `PYTHONHOME`, virtualenv/
Conda, user-site, proxy, certificate override, credential, askpass, SSH, pager/editor/diff,
`LD_PRELOAD`, `LD_LIBRARY_PATH`, and other loader/config-injection variables.

Every protocol-owned Linux Git child is the literal `/usr/bin/git` and places the global option
`--no-replace-objects` immediately after that executable. Every Git argv in the operator
bootstrap and immutable-result local-transfer arrays receives the same global option. Both the authority bootstrap array
and each process-clone automaton add, immediately after detached checkout and before the
final HEAD check, the exact command
`["/usr/bin/git","--no-replace-objects","-C","<CLONE_ROOT>","remote","remove","origin"]`.
Detached checkout is explicitly an untrusted materialization step. It may read the clone's
initial config and objects only to materialize bytes; no receipt field, accepted hash,
validation conclusion, or evidence use may depend on that materialization until origin is
removed and every following check passes. After remote removal, the exact local Git-config
mapping is:

```text
core.repositoryformatversion=0
core.filemode=true
core.bare=false
core.logallrefupdates=true
core.autocrlf=false
core.eol=lf
core.safecrlf=true
```

Every other local key, duplicate key, or different value fails. The protocol then repeats
HEAD/tag/tree, tracked-byte, raw-materialization, and status validation from scratch before
accepting any evidence. Each authority/process Git directory is also checked as a plain owner-controlled administrative directory;
`.git/objects/info/alternates` and `.git/objects/info/http-alternates` must both be absent,
as must legacy `.git/info/grafts` and `.git/shallow`; no environment/config alternate-object
or promisor source is allowed. Loose or packed `refs/replace/*` are also forbidden, even
though replacement interpretation is separately disabled. These checks repeat at each later
live Git-identity gate. Both the empty-built environment and `--no-replace-objects` are required.
Every protocol-owned nonpublisher Linux Git child uses the exact
`preparation_command_environment`, including reconstruction, runner/finalizer validation,
and preparation. Publisher-only command-specific `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, and
fixed author/committer members remain solely in the incorporated exact
`result_git_environment` object, also constructed from empty.

Every preparation child except the exact offline environment build has a 60-second
monotonic deadline; the environment build has 600 seconds. Every protocol-owned local Git subprocess,
owned by preparation/lifecycle code, including local file-URL process clone, config,
checkout, raw audit, reconstruction, lifecycle validation, finalization, and R8 plumbing,
therefore has 60 seconds. Forced preparation
cleanup fixes `TERM_deadline=cleanup_start+5 seconds` and
`KILL_deadline=cleanup_start+10 seconds` once. TERM/wait consume the first interval;
KILL/final wait consume only the remainder to the second. Neither endpoint is reset. A later
stage starts only after the child and process group are confirmed gone.

The earlier operator bootstrap Git argv and later immutable-result local-transfer argv remain
verbatim operator commands, not children of a registered Python supervisor, so this
correction does not falsely claim they have an enforced subprocess timeout. A hang is
manually aborted; bootstrap failure remains pre-lifecycle, while post-R8 transfer can be
retried without changing evidence. Both use the registered literal Git argv/no-replacement
form, but their elapsed time is not result evidence.

The outer sole preparation invocation remains deliberately unwrapped and pre-lifecycle. It
creates no Windows lifecycle claim and has no invented whole-process hard deadline. If the
preparation process itself hangs outside a bounded child, the operator may abort it; no
supervisor, lifecycle result, retry, or cleanup/adoption claim follows, and a new
preregistration is required.

The Windows Git environment is the incorporated exact empty-built sixteen-key object plus
exactly `GIT_NO_REPLACE_OBJECTS=1`. Every Windows Git argv likewise places
`--no-replace-objects` immediately after `git.exe`. The online `ls-remote` query alone has
the 120-second per-attempt deadline; no local Git command inherits that online allowance.
The remote policy schema remains v1 but records the corrected seventeen-key environment and
these administrative timing substitutions: verifier `overall_deadline_seconds=390`,
`verifier_child_deadline_seconds=430`, and
`supervisor_receipt_reserve_seconds=20`. Accordingly the exact verifier argv uses
`--overall-deadline-seconds 390`, and the exact supervisor argv uses
`--verifier-child-deadline-seconds 430`; the 480-second supervisor deadline and 30-second
cleanup value remain. Maximum attempts remains three as a cap, not a promise all three fit.

## 9. Actual timing and absolute cleanup/reserve semantics

Every duration field that actually exists is an unclamped monotonic interval, floored to
integer milliseconds. A preparation ledger row runs from its single pre-cap/admission epoch
through rejection, observed return, or forced cleanup. A remote-attempt duration covers that
Git attempt through return/cleanup. `total_duration_milliseconds` runs from verifier `main`
entry epoch `V` through its final attempt/cleanup and excludes construction/publication of the receipt
that contains it. The supervisor duration begins at child-start epoch `C` and covers its verifier-child spawn attempt through
return/cleanup and does not claim to include subsequent evidence validation or its own
receipt publication. The lifecycle ledger and final result schemas contain no duration and
make no timing claim. A configured timeout is a decision threshold, not a maximum
representable duration. Producers record actual values and fake-clock tests prove the code
does not clamp them. Validators require nonnegative values and threshold/lower-bound
consistency and accept above-threshold cleanup durations; a receipt integer alone cannot
prove the truth of a historical clock.

The incorporated remote receipt/supervisor v1 classification and synthetic-124 timeout
sentinel rules remain unchanged. The new actual-exit/no-synthetic rule applies only to
preparation command-ledger rows and emergency finalizer-child evidence, not to those frozen
remote v1 fields.

Let `S` be the supervisor's first `main`-entry monotonic read, before parsing,
prevalidation, or claim creation; let `C` be its read immediately before the verifier spawn
attempt after those fixed steps; and let `V` be the verifier's `main`-entry read. All use the
same Windows monotonic clock and `S<=C<=V`. The supervisor fixes, never slides, the
dominating outer endpoints `S+430` for child control, `S+460` for supervisor-owned tree
cleanup, and `S+480` for post-child evidence validation and supervisor receipt publication.
Those endpoints govern parsing, prevalidation, claim handling, spawn, child execution,
cleanup, and publication; a stall before `C` consumes the same budget and cannot move an
endpoint. Supervisor duration begins at `C`. No dynamic S value is passed through argv or
environment; the supervisor independently enforces the outer endpoints, so startup delay
may shorten or eliminate the verifier's relative allowances and no full-relative-allowance
promise is made.

For an online attempt starting at `A`, verifier admission requires both
`A+120 <= V+390` and `A+150 <= V+420`. Forced verifier cleanup has the single deadline
`min(cleanup_start+30,V+420)`. All `taskkill`, parent wait, `TerminateJobObject`,
zero-active-process polling, and Job-handle close steps consume that same remainder; no step
gets a fresh 30 seconds. Verifier receipt construction/exit targets `V+430`. The earlier
external `S+430` supervisor child threshold always dominates when it arrives first; the
protocol does not promise every inner allowance will complete. Three attempts remain only a
maximum. If the verifier is still live at `S+430`, the
supervisor uses its own single cleanup deadline
`min(cleanup_start+30,S+460)`, then uses only the remaining interval to `S+480` for child
evidence reading, cross-validation, classification, canonical supervisor-receipt creation,
reopen validation, and publication.

These are process admission and cleanup endpoints, not a claim that a blocking filesystem
flush can be forcibly interrupted at an exact nanosecond. Receipt publication is
best-effort within the reserved interval; overrun or failure is recorded by the surrounding
one-shot failure semantics and never by clamping a duration.

For the Linux lifecycle driver, `D0` is the first monotonic read at `main` entry, before
argument parsing, fixed-argv validation, or any preclaim local Git child. The same value is
threaded through all helpers. Its absolute deadline is `D0 + 8,400 seconds`; the final
1,200-second reserve begins at `D0 + 7,200 seconds`. Arm, science, and validator children
may start only when the GNU-timeout allowance including `kill-after` plus the driver's fixed
ten-second TERM/KILL process-group cleanup allowance fits before the reserve boundary: 135 seconds
for arm, 2,725 for a runner, and 315 for a validator. Cleanup may consume time up to, but
never move, that boundary. Crossing it prevents every later scientific start. Preclaim and
later local Git each require their complete 60+5+5-second driver allowance to fit before the
applicable absolute boundary.

Every GNU-timeout wrapper started by the Linux lifecycle driver—arm, A/B runner, A/B
validator, finalizer, and publisher—omits the literal `--foreground` token in its corrected
registered argv; every scientific 2,100/2,400/2,700-second duration and every other timeout
token remains unchanged. The driver starts each wrapper in a fresh owned session and PGID.
The wrapper, its Python child, scientific code, and every nested protocol-owned Git child
must retain that PGID; none may create a new session or process group. After any wrapper
return or control failure, the driver enumerates that PGID and accepts completion only when
no member survives. If a member remains, the driver sends TERM and then KILL to the whole
PGID within that child's already registered fixed cleanup endpoint and confirms the group
empty; cleanup failure is terminal, and no later lifecycle stage starts first. An inner Git
controller may signal and wait for its direct PID under its own 60+5+5-second rule, but that
does not replace conclusive outer driver group cleanup. The unwrapped pre-lifecycle
preparation/reconstructor paths retain their separately owned behavior already specified.

At or after the reserve boundary the driver may only finish fixed cleanup, publish the
ledger, make its sole finalizer start attempt when the complete 300-second wrapper,
five-second `kill-after`, and ten-second driver-cleanup allowance fits
before the 8,400-second deadline, create the emergency bundle if required, and make its sole
in-driver Git publisher invocation. The existing `result_publisher_argv` becomes a fixed
`["/usr/bin/timeout","--signal=TERM","--kill-after=5s","600s", ...]`
wrapper around the incorporated publish command, which adds exactly
`--control-time-seconds 570` as its final argument pair. The driver starts the wrapper as one
owned process group. The wrapper, publisher, and every nested Git child must retain that one
PGID; the publisher and Git children must not create a session or process group. The
publisher records `P0` at its own `main` entry. Its own admission permits a nested Git child
only when the full 60+5+5-second allowance fits by `P0+570`, and its own cleanup target is
`P0+580`. Those are best-effort inner bounds: the actual child/control and cleanup endpoints
are respectively the minima of those P0-relative bounds and the earlier outer-wrapper/group
TERM/KILL endpoints. Startup delay can therefore curtail an inner allowance. The outer
timeout and the driver's fixed process-group TERM/KILL cleanup conclusively dominate every
descendant; a nested child cannot be orphaned in a separate session. Tests require the
wrapper, publisher, and nested Git child to report the same PGID and fail any new-session or
new-group spawn path. The driver admits this wrapper only if its complete
600-second duration, five-second wrapper `kill-after`, and ten-second driver cleanup—615
seconds total—fit before `D0+8,400`. If the finalizer cannot be admitted, it is not spawned
and the emergency classification is `deadline_admission_failed`; no synthetic exit code is
invented. No driver operation may reset or extend the 8,400-second deadline. If publisher
control ends before atomic hard-link creation, no authoritative result tag exists. If it
ends after the link, a complete candidate tag may remain even though post-link validation did
not return; the incorporated publication-only command independently validates and adopts
only the exact tag. The publication-only recovery command uses the same registered bounded
publisher argv and may later repeat Git-only publication without
rerunning arm, science, validation, finalization, rendering, or evidence generation.
Publication-only recovery is outside the original driver's deadline and revalidates all
immutable evidence before acting.

## 10. Linux directory-descriptor hardening

Direct Python evidence creation, atomic promotion/link, owned cleanup, bundle publication, and
result-ref publication use component-wise `openat` traversal from the fixed execution or
authority root with `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`. Each relative component is a single
nonempty name other than dot or dot-dot and contains no slash or NUL. Before and after each
mutation, the program `fstat`s the still-open relevant parent and requires the device,
inode, owner UID, type, and permission policy captured or revalidated for that operation;
these transient identities are not falsely described as preregistered values. Ordinary
read-only source checks need not be rewritten into a universal openat framework, but direct
Python reads must use no-follow open plus `fstat` for the final object and fail on unsafe
type/change. A
pathname `stat` or `Path.resolve` alone is not identity proof.

This does not claim that Git, uv, or CPython subprocess internals use these dirfds. Their
access is constrained by exact anchored cwd/argv, the closed registered environment, frozen
tool identities, and protocol-owned before/after raw-state validation.

Evidence destinations use exclusive creation within the already opened parent, flush,
file fsync, reopen-by-dirfd, exact byte/hash/canonical validation, and parent-directory
fsync. Atomic promotion/link operations require same-device verified parents. Cleanup is
limited to exact registered basenames and only regular files or directory trees whose
owner marker, device, inode, UID, mode, expected bytes where applicable, and link-count
rules establish that this invocation owns them. An identity mismatch fails closed and is
never cleaned. Open descriptors reduce pathname races but, per section 3, do not defend
against a malicious same-UID process capable of modifying an already open object.

The runner rechecks only its own clone and output parent before start; the independent
preparation verifier and finalizer check the complete set. The publisher additionally
revalidates the authority tag parent immediately before and after its atomic hard-link ref
publication. Windows artifacts retain only the explicitly limited Windows guarantees in
section 3; Linux dirfd language must not be applied to them.

## 11. Narrow document-only finalization escape

`receipt_finalization_failed` remains a disposition override, not an underlying evidence
stage. It is permitted only when all of the following are true:

1. the finalizer process started once and validated its own O8 identity, registration, P8v3
   ancestry, result-document renderer/template identities, and enough fixed/raw evidence to
   render a deterministic failure document;
2. ordinary evidence invalidity has already been mapped to the appropriate machine
   administrative terminal where possible; it is not a reason to choose this override;
3. after evidence capture in memory, construction or self-validation of the canonical
   machine receipt/terminal fails, no normal machine file or payload has been included, and
   the deterministic document itself still renders and revalidates exactly;
4. the normal bundle destination is absent and exclusive publication succeeds with exactly
   the one registered result-document file.

The exposed stage is `receipt_finalization_failed`; `underlying_stage` retains the earlier
independently derived stage or is null if no earlier stage was derivable. The document uses
only fixed identities plus existence, raw hashes, validation states, and the two preparation
hash chains; it contains no exception text, hostname, clock, operator prose, guessed outcome,
or partial payload. If any prerequisite, rendering, bundle encoding, exclusive publication,
reopen, or validation step fails, no doc-only normal bundle is accepted and the driver uses
the one emergency path. This escape cannot convert unequal payloads, an invalid payload, or
missing scientific execution into scientific evidence.

## 12. Required implementation tests and gates

All incorporated tests and exact frozen gate commands remain required. Before O8, new tests
must additionally prove:

- P8v3 is the one-file direct child of P8v2; v3 is a lightweight tag; O8 is its direct child;
  and the v3 document/tag/commit substitutions reverse exactly to the frozen v7 module;
- preparation receipt v2 rejects every key mutation, noncanonical byte sequence, missing or
  extra nineteen-key ledger record, noncontiguous order, impossible phase prefix,
  argv/command-environment hash mismatch, inherited environment member, stdin/stdout/stderr
  cap or digest error, false null, duration violating registered semantic bounds, invented command, inconsistent stage,
  malformed compact RECORD or recursive venv inventory, duplicate normalized target, and
  inventory-preimage/hash mismatch;
- spawn, zero/nonzero, stdin/stream limit, timeout, deterministic collision precedence,
  orthogonal cleanup failure, first-attempt cleanup, second attempt,
  promotion, pre-promotion failure, post-promotion stranding, and prepared paths produce
  their only legal ledger/attempt/status combinations, without backfilling bootstrap history
  or deleting/adopting a promoted parent;
- the independent verifier recomputes rather than echoes every live identity, exclusively
  persists one canonical receipt, rejects mutation of either `.venv`, a tracked byte, raw
  registration, Git status, clone identity, output-parent state, receipt
  preimage, or command ledger, and leaves no receipt on failure;
- arm v2 binds both preparation read-state triples and all incorporated remote hashes with
  exact absent/unsafe/oversized/unstable/readable nullability; final result/admin v2 and
  emergency v2 preserve both preparation artifacts or their truthful read-state evidence
  under every precedence collision;
- A and B independently reject a swapped clone root, modified venv file, symlink, mode, or
  metadata, changed distribution inventory, unequal/resolved venv-Python bytes, wrong Python/uv identity,
  replaced/wrong-mode/nonempty output parent, invalid arm chain, or replacement-object influence before a
  start claim and before audit import;
- the existing exact argv-hash keyset covers every registered array/object, the four concrete
  A/B runner/validator arrays are the only legal template expansions, the runbook is
  verbatim, and edited cwd/path/label/prior/deadline/output arguments fail; no operator
  outcome or stage input exists;
- payload comparison covers every raw byte and nested member; mutations with equal selected
  summaries, rows, aggregates, or counters still yield `payload_byte_mismatch`;
- hostile inherited Git config, retained origin/remote keys, replace refs, alternates,
  grafts/shallow state, promisor config, hooks, credentials, proxies,
  `GIT_CONFIG_COUNT`, and URL rewrites cannot enter either fixed environment or affect any
  local/online result; protocol-owned local Git receives 60 seconds and online `ls-remote` receives 120;
- fake-clock producer tests prove duration code is not clamped and exercise values above
  child thresholds; validator tests enforce nonnegative/lower-bound consistency and accept
  valid cleanup overruns; preparation TERM/KILL and Windows cleanup consume their fixed absolute
  endpoints, prove no deadline reset, and
  prove the absolute 7,200/8,400-second driver reserve/admission rules at both sides of every
  boundary;
- Linux lifecycle child-tree tests cover arm, both runners, both validators, finalizer, and
  publisher; each registered wrapper omits `--foreground`, every descendant retains one
  owned PGID, and wrapper-return-with-a-lingering-child, timeout, TERM/KILL, and cleanup-
  failure cases prove that no orphan survives or later stage starts;
- publisher tests enforce the 600/5 wrapper without `--foreground`, 570-second inner control
  time, the minimum of the `P0+580` and earlier outer cleanup endpoints, 615-second driver
  admission, one PGID with no orphanable nested child, and post-link
  publication-only recovery;
- Linux symlink, dot-dot, rename, device/inode/UID/mode, link-count, foreign scratch, and
  parent-replacement cases fail closed through dirfd checks; tests and documentation make no
  malicious-same-UID or Windows-directory-fsync claim;
- normal machine terminals handle ordinary invalid evidence; the doc-only override is
  reachable only at the four section-11 conditions, has exactly one file, and otherwise
  yields the one emergency bundle with truthful finalizer classification/nullability;
- all source/help/static tests remain offline, never create the real execution root or a
  result path, never call the complete producer, and never import the scientific module on a
  pre-start failure.

The builder may generate the registration only after all other O8 additions are staged.
Registration reconstruction must be byte-identical; the full frozen pytest, Ruff, and
strict-mypy gates must pass from explicit Ubuntu. O8 may then be committed, lightweight
tagged, pushed, and independently verified. Only after that remote O8 verification may the
single preparation/supervisor/lifecycle sequence begin.

## 13. Claims that remain prohibited

This correction does not authorize a lockbox, sealed evaluation, gameplay, leaderboard
submission, model change, development matrix, or a positive mechanism claim. All five
authorization Booleans remain false. A preparation record, independent-verification receipt,
start claim, duration, hash chain, dirfd check, or two equal public payloads is not calibrated
Bayesian evidence, unseen generalization, causal attribution, security attestation, or proof
against a malicious same-UID actor. A failed or incomplete lifecycle remains publishable
only with its exact administrative/scientific meaning and cannot be tuned away.
