# Action-QBC v8 P8v4 minimal-honest administrative correction

Correction freeze: 11 August 2026 (Australia/Sydney)

Status: preregistration-only administrative correction. No O8 registration, O8 commit or
tag, execution root, remote-verification artifact, lifecycle claim, arm receipt, scientific
start, payload, finalization bundle, R8 object, or v8 scientific observation existed when
this document was written.

## 1. Authority, ancestry, and exact scope

This document corrects and otherwise incorporates the complete protocol in
`docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification_v3_correction.md`.
That incorporated document is the sole file added by P8v3 commit
`996ab2bb5a24143a110673977f63e7d111cf2060`, whose parent is P8v2 commit
`91c5ba1862fc7701ed2276ddd64b99fdb8b7ad1d`. P8v3 is tagged with the immutable
lightweight tag `prereg-action-qbc-v8-open-bounded-remote-verification-v3`.

The commit made from this document alone is `P8v4`. It must be a direct child of P8v3,
add exactly this one path, and modify, delete, or rename no P8v3 path:

```text
docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification_v4_correction.md
```

Its immutable lightweight tag is:

```text
prereg-action-qbc-v8-open-bounded-remote-verification-v4
```

`P8v4_COMMIT`, `P8v4_DOCUMENT_GIT_BLOB_SHA1`, `P8v4_DOCUMENT_SHA256`, and
`P8v4_DOCUMENT_BYTE_COUNT` mean the identities obtained from the committed bytes of this
path after P8v4 exists. They are identities, not choices. O8 must be a direct child of P8v4
and add exactly the same fifteen O8 paths fixed by the incorporated protocol. No path
present at P8v4 may change at O8. The O8 and R8 lightweight tag names remain:

```text
action-qbc-v8-open-diagnostic-freeze-v1
action-qbc-v8-open-diagnostic-result-v1
```

All executable v8 identities use P8v4, the v4 preregistration tag, and this document path.
The deterministic v7-to-v8 source transformation is unchanged except for these
administrative outputs:

```text
preregistration tag  = prereg-action-qbc-v8-open-bounded-remote-verification-v4
preregistration SHA  = P8v4_COMMIT
document path        = docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification_v4_correction.md
document Git blob    = P8v4_DOCUMENT_GIT_BLOB_SHA1
document SHA-256     = P8v4_DOCUMENT_SHA256
document byte count  = P8v4_DOCUMENT_BYTE_COUNT
```

The registration producer substitutes the v4 tag in its exact argv. The reconstructor
verifies the complete ancestry R7 -> P8v1 -> P8v2 -> P8v3 -> P8v4 -> O8, each exact
one-file preregistration diff, all four lightweight preregistration tags, and this
document's object identities. P8v1, P8v2, and P8v3 remain immutable audit history and are
not described as executed protocols.

This correction changes only administrative process classification, cleanup evidence,
preparation-evidence embedding, Windows original-checkout isolation, registration binding,
and duration-validation wording. It introduces no scientific choice or observation.

## 2. Complete pre-O8 disclosure and why correction is required

After P8v3, static inspection and synthetic tests found three administrative contradictions
before staging or execution:

1. A finalizer wrapper can return zero or nonzero while a same-PGID descendant remains.
   P8v3 requires conclusive cleanup but its emergency table requires null cleanup for the
   resulting `bundle_invalid` or `nonzero` row.
2. Windows `Popen` can create a suspended child before Job assignment or resume fails. The
   v1 remote schemas cannot distinguish that post-create initialization failure from a
   failure in which no child existed, and their frozen nullability cannot record whether
   required cleanup passed.
3. Windows local Git evidence reads the original checkout's local administrative state.
   P8v3 closes the process environment but does not bind the exact safe local-config and
   administrative-source gate needed before accepting that evidence.

The same inspection found that a complete canonical preparation receipt with
`status=failed` can be incorrectly discarded from a later machine terminal by code that
conflates canonicality with lifecycle eligibility. P8v3 already requires canonical objects
to be retained; section 4 below makes the stage semantics explicit.

The following read-only original-checkout facts were recomputed twice immediately before
this correction. They are administrative admission identities, not scientific evidence:

```text
HEAD                              996ab2bb5a24143a110673977f63e7d111cf2060
.git/config byte count            846
.git/config SHA-256               a78fd50c029f9b0755a7fceac2b77a39479c30becb2eff1794d77df5d185f702
.git/info/exclude byte count       240
.git/info/exclude SHA-256          6671fe83b7a07c8932ee89164d1f2793b2318058eb8b98dc5c06ee0a5a3b0ec1
absolute Git directory            D:/kaggle competitions/arc3-crosslevel-voi/.git
Git common directory              .git
replacement refs                  none
promisor pack sidecars            none
```

No remote query, claim, preparation invocation, real execution root, scientific module,
scene, payload, result, or result publication was used to find these defects or facts.

## 3. Schema and registration identities

Because no O8 registration or v8 receipt instance exists and no affected top-level receipt
keyset changes, every incorporated schema name and exact keyset remains unchanged. In
particular, these affected identities remain unchanged:

```text
action-qbc-v8-open-registration-v1
action-qbc-v8-preparation-receipt-v2
action-qbc-v8-preparation-verification-receipt-v1
action-qbc-v8-remote-tag-verification-receipt-v1
action-qbc-v8-remote-tag-verification-supervisor-receipt-v1
action-qbc-v8-arm-receipt-v2
action-qbc-v8-open-diagnostic-receipt-v2
action-qbc-v8-open-diagnostic-administrative-terminal-v2
action-qbc-v8-emergency-result-bundle-v2
```

The registration execution contract adds exactly one member named
`windows_repository_contract`. No other registration schema member is added, removed, or
renamed. Its resulting exact execution-contract keyset is:

```text
administrative_stage_order
argv_hashes
arm_argv
arm_receipt_path
arm_timeout_seconds
authority_root
bootstrap_steps
compute_deadline_seconds
driver_deadline_seconds
emergency_bundle_path
environment_build_argv
execution_root
finalization_bundle_path
finalizer_argv_template
finalizer_cwd
finalizer_timeout_seconds
hard_timeout_seconds
lifecycle_driver_argv
lifecycle_driver_claim_path
lifecycle_ledger_path
linux_host_launcher
linux_platform
linux_tool_identities
local_git_timeout_seconds
payload_validator_argv_template
payload_validator_timeout_seconds
post_preparation_validation_argv
preflight_argvs
preparation_argv
preparation_command_environment
preparation_command_policy
preparation_receipt_path
preparation_verification_receipt_path
process_a_output
process_a_root
process_a_start_claim
process_a_validation_receipt
process_a_validator_claim
process_b_output
process_b_root
process_b_start_claim
process_b_validation_receipt
process_b_validator_claim
process_labels
producer_argv
reconstructor_argv
registered_start_count
remote_claim_linux_path
remote_claim_windows_path
remote_policy
remote_receipt_linux_path
remote_receipt_windows_path
remote_supervisor_argv
remote_supervisor_receipt_linux_path
remote_supervisor_receipt_windows_path
remote_verifier_argv
remote_verifier_claim_linux_path
remote_verifier_claim_windows_path
result_document_contract
result_git_environment
result_git_max_attempts
result_git_owner_path
result_git_work_root
result_publisher_argv
result_ref_transaction
scientific_argv_template
test_argvs
third_start_allowed
wall_time_seconds
windows_repository_contract
```

All source identities, document identities, result-document variants, argv hashes, and
registration content hashes are recomputed from O8. The existing `remote_policy` keyset
remains unchanged. Top-level non-Git argv arrays remain unchanged except for the section-1
P8v4 administrative identity substitutions. Windows original-checkout Git argvs additionally
insert `--no-optional-locks` immediately after `--no-replace-objects`; no other token changes.
The new Windows repository object is indirectly bound into every remote receipt through the
exact registration-content SHA-256.

## 4. Canonical failed preparation evidence

Receipt canonicality and lifecycle eligibility are distinct predicates. A preparation
receipt v2 is canonical only after its complete exact schema, canonical bytes, identities,
command automaton, attempts, promotion/cleanup semantics, hashes, and status-specific
nullability pass. A canonical `status=prepared` receipt must satisfy the incorporated
prepared and live-filesystem rules before it is lifecycle-eligible. A canonical
`status=failed` receipt must have `process_a=null`, `process_b=null`, no promoted processes
parent, only failed attempts with truthful passed owned cleanup, and the complete command
prefix actually attempted.

A compliant canonical failed preparation remains preclaim and unarmed. The independent
verification receipt, Windows supervisor, lifecycle claim, driver, finalizer, and R8 remain
forbidden; no result is created merely because preparation failed.

If a canonical failed preparation receipt is nevertheless encountered after the irreversible
Windows lifecycle claim while a normal administrative terminal is being derived, the receipt
remains canonical evidence and must be embedded with its exact readable/hash triple. It is
not replaced with null. It is invalid as a lifecycle prerequisite and maps to the existing
first underlying stage `preparation_receipt_invalid`; no new `preparation_failed` stage is
introduced. It cannot support a valid preparation-verification receipt, armed receipt,
scientific start, or scientific result. A machine terminal that reports a readable canonical
failed receipt but embeds null, or embeds it without deeply validating its failed semantics,
is noncanonical.

## 5. Linux finalizer emergency evidence correction

P8v3's emergency-bundle keyset, schema, and all classifications remain except for the exact
cleanup semantics in this table:

| Classification | Exact trigger | Exit | Timed out | Cleanup |
|---|---|---:|---:|---:|
| `deadline_admission_failed` | complete finalizer allowance did not fit, so no spawn | null | null | null |
| `spawn_error` | process creation raised before a child existed | null | null | null |
| `timeout` | wrapper returned 124 or the driver initiated timeout, and required cleanup did not fail | actual or null | true | null or true |
| `nonzero` | actual nonzero return, no timeout initiated, wrapper did not return 124, and required cleanup did not fail | actual | false | null or true |
| `bundle_invalid` | actual return zero, normal bundle absent or invalid, and required cleanup did not fail | 0 | false | null or true |
| `spawned_no_return` | child started, no return was obtained, no timeout initiated, and forced cleanup confirmed the PGID empty | null | false | true |
| `child_cleanup_failed` | required cleanup did not confirm the owned PGID empty; this classification takes precedence | actual or null | true or false | false |

For `nonzero` and `bundle_invalid`, cleanup is true exactly when a same-PGID member survived
wrapper return and the fixed TERM/KILL cleanup confirmed the group empty; it is null exactly
when no cleanup was required. Conversion of a zero-return `completed` child into
`bundle_invalid` must preserve an observed true cleanup value. A zero-return finalizer with
a valid normal bundle may complete normally after passed lingering-descendant cleanup; the
normal schema has no cleanup member and makes no claim that cleanup was unnecessary. No
later lifecycle stage starts until every required group cleanup passes.

There is exactly one permitted normal/emergency coexistence override. If the finalizer
returns zero and leaves a canonical normal bundle but required outer PGID cleanup is false,
the driver preserves that normal bundle byte-for-byte, creates only the
`child_cleanup_failed` emergency bundle with exit zero, `timed_out=false`, cleanup false,
and the normal bundle's truthful existence/SHA evidence, and selects only the emergency
bundle. It does not delete, replace, adopt, or publish the normal bundle, and it starts no
publisher or other later child. In every other zero-return canonical-normal-bundle case an
emergency bundle is forbidden. Selection and every independent validator apply this sole
override before the incorporated general normal/emergency exclusivity rule.

## 6. Windows post-spawn, capture, and cleanup correction

The remote-attempt v1 classification enum adds exactly:

```text
post_spawn_initialization_failed
stream_capture_failed
```

Its exact classification/nullability matrix is:

| Classification | Exit | Timed out | Cleanup | Additional condition |
|---|---:|---:|---:|---|
| `spawn_error` | null | false | null | no OS child was created |
| `post_spawn_initialization_failed` | actual | false | true | suspended child existed; Job assignment or resume failed; required cleanup passed |
| `stream_capture_failed` | actual, or synthetic 124 after independently initiated timeout | actual Boolean | true | bounded capture failed; required cleanup passed |
| `retryable_timeout_124` | synthetic 124 | true | true | existing timeout rule |
| `overall_deadline` | synthetic 124 | true | true | existing overall-deadline rule |
| `stdout_limit` | actual iff timed out is false; synthetic 124 iff timed out is true | actual Boolean | true | stdout cap has classification precedence |
| `stderr_limit` | actual iff timed out is false; synthetic 124 iff timed out is true | actual Boolean | true | stderr cap has classification precedence |
| `verified` | actual | false | null or true | true only after passed lingering-Job cleanup |
| `retryable_empty_exit_0` | actual | false | null or true | true only after passed lingering-Job cleanup |
| `retryable_git_128` | actual | false | null or true | true only after passed lingering-Job cleanup |
| `unexpected_output` | actual | false | null or true | true only after passed lingering-Job cleanup |
| `unexpected_exit` | actual | false | null or true | true only after passed lingering-Job cleanup |
| `child_cleanup_failed` | actual or null | actual Boolean | false | any required tree cleanup failed; takes precedence |

The supervisor-receipt v1 classification enum adds the same two names. Its exact matrix is:

| Classification | Exit | Timed out | Cleanup | Additional condition |
|---|---:|---:|---:|---|
| `spawn_error` | null | false | null | no verifier OS child was created |
| `post_spawn_initialization_failed` | actual | false | true | suspended verifier existed; Job assignment or resume failed; required cleanup passed |
| `stream_capture_failed` | actual, or synthetic 124 after independently initiated timeout | actual Boolean | true | bounded capture failed; required cleanup passed |
| `verifier_timeout_124` | synthetic 124 | true | true | existing verifier-timeout rule |
| `stdout_limit` | actual iff timed out is false; synthetic 124 iff timed out is true | actual Boolean | true | stdout cap has classification precedence |
| `stderr_limit` | actual iff timed out is false; synthetic 124 iff timed out is true | actual Boolean | true | stderr cap has classification precedence |
| `verifier_completed` | actual | false | null or true | true only after passed lingering-Job cleanup |
| `remote_receipt_missing` | actual | false | null or true | true only after passed lingering-Job cleanup |
| `remote_receipt_invalid` | actual | false | null or true | true only after passed lingering-Job cleanup |
| `child_cleanup_failed` | actual or null | actual Boolean | false | any required tree cleanup failed; takes precedence |

`actual` means the integer return observed from the child. No integer is invented for an
initialization failure. Cleanup cannot pass unless the parent return is observed and the
applicable tree-gone predicate passes; absence of an observed return therefore makes a
post-spawn cleanup failure use `child_cleanup_failed` with a null exit. The existing
synthetic-124 rule remains limited to an independently initiated timeout whose cleanup
passes. `timed_out` records that actual orthogonal fact even when a higher-precedence
classification is exposed.

The producer precedence after capture/controller completion is exactly:

1. `child_cleanup_failed` when any required cleanup is false;
2. `post_spawn_initialization_failed` when suspended creation succeeded but Job assignment
   or resume failed and cleanup passed;
3. `stream_capture_failed` when capture failed and cleanup passed;
4. `stdout_limit`, then `stderr_limit`, then the applicable timeout classification, while
   preserving the independently initiated timeout fact;
5. the existing normal-return/output/evidence classification.

The two new classifications are terminal and nonretryable. `child_cleanup_failed` is used
only with cleanup false. A capture failure with passed process-tree cleanup cannot be called
`child_cleanup_failed`. Normal-return classification is preserved when a lingering Job
member is conclusively removed; its cleanup field is then true rather than erased. Stream
fields for `stream_capture_failed` describe exactly the bounded bytes captured before
failure and are not represented as the child's complete possible output. A suspended child
that never successfully resumed has empty captured streams.

A remote attempt with either new classification is terminal, cannot be selected, and makes
its remote receipt `status=failed`. This does not invent a supervisor-side failure: when the
verifier cleanly returns the canonical remote failed receipt with the incorporated exit-one
contract, the supervisor retains `classification=verifier_completed` and
`status=completed`. Either new classification arising in the supervisor's own verifier-child
control instead makes the supervisor receipt `status=failed`. `child_cleanup_failed`,
`spawn_error`, and every other existing terminal failure retain their layer-specific status
and retry rules. Clean observation of any canonical remote `status=failed` receipt likewise
remains `verifier_completed`/`completed`; downstream finalization maps the remote failure
without rewriting the supervisor observation.

Once `Popen` returns a child, the controller records that a child existed. It may not return
`spawned=false` or use `spawn_error`. Job construction or `Popen` failure before a child
exists remains `spawn_error`. Assignment/resume failure is returned to the common bounded
controller with the process and Job handles still owned; `_spawn_suspended` performs no
ad-hoc five-second kill/wait and does not hide cleanup evidence.

For a verifier online attempt, post-spawn cleanup uses the one deadline
`min(cleanup_start+30 seconds,V+420 seconds)`. For the supervisor's verifier child, it uses
`min(cleanup_start+30 seconds,S+460 seconds)`. Direct-parent termination/wait is required if
assignment failed. Job termination, parent return, and `ActiveProcesses == 0` are required
if assignment succeeded. Taskkill, wait, Job termination/query, handle close, and capture
closure consume the same remaining interval; no step obtains a new endpoint. Every other
Windows managed child uses the earlier of its registered local cleanup endpoint and the
applicable fixed outer endpoint. Cleanup failure is terminal, and no later child or evidence
acceptance occurs first.

For an online attempt beginning at A, the live endpoint is the earlier of A+120 and V+390.
If A+120 is strictly earlier, an initiated deadline timeout is
`retryable_timeout_124`; if V+390 is earlier or equal, including exact equality, it is
`overall_deadline`. A cap or capture failure observed before that endpoint has the table's
higher classification precedence. If its observation collides with or is completed after an
independently initiated timeout, the cap/capture classification remains exposed,
`timed_out=true` remains recorded, passed cleanup remains true, and the exit is synthetic
124. Every live wait/admission comparison uses `min(A+120,V+390)`. Every cleanup comparison
uses its applicable section-6 cleanup endpoint. Each endpoint is fixed once and never slides.

## 7. Exact Windows original-checkout contract

`execution_contract.windows_repository_contract` has exactly these canonical JSON keys and
values:

```json
{
  "active_hooks_allowed": false,
  "common_directory": "D:\\kaggle competitions\\arc3-crosslevel-voi\\.git",
  "forbidden_admin_relative_paths": [
    ".git\\commondir",
    ".git\\config.worktree",
    ".git\\index.lock",
    ".git\\info\\attributes",
    ".git\\info\\grafts",
    ".git\\info\\sparse-checkout",
    ".git\\objects\\info\\alternates",
    ".git\\objects\\info\\http-alternates",
    ".git\\refs\\replace",
    ".git\\shallow"
  ],
  "forbidden_pack_suffixes": [
    ".promisor"
  ],
  "forbidden_ref_prefixes": [
    "refs/replace/"
  ],
  "git_config_byte_count": 846,
  "git_config_sha256": "a78fd50c029f9b0755a7fceac2b77a39479c30becb2eff1794d77df5d185f702",
  "git_directory": "D:\\kaggle competitions\\arc3-crosslevel-voi\\.git",
  "index_path": "D:\\kaggle competitions\\arc3-crosslevel-voi\\.git\\index",
  "info_exclude_byte_count": 240,
  "info_exclude_sha256": "6671fe83b7a07c8932ee89164d1f2793b2318058eb8b98dc5c06ee0a5a3b0ec1",
  "local_config": {
    "branch.action-qbc-v6-prereg.merge": "refs/heads/action-qbc-v6-prereg",
    "branch.action-qbc-v6-prereg.remote": "origin",
    "branch.action-qbc-v7-open-diagnostic.merge": "refs/heads/action-qbc-v7-open-diagnostic",
    "branch.action-qbc-v7-open-diagnostic.remote": "origin",
    "branch.action-qbc-v7-prereg.merge": "refs/heads/action-qbc-v7-prereg",
    "branch.action-qbc-v7-prereg.remote": "origin",
    "branch.action-qbc-v8-prereg.merge": "refs/heads/action-qbc-v8-prereg",
    "branch.action-qbc-v8-prereg.remote": "origin",
    "branch.main.merge": "refs/heads/main",
    "branch.main.remote": "origin",
    "core.bare": "false",
    "core.filemode": "false",
    "core.ignorecase": "true",
    "core.logallrefupdates": "true",
    "core.repositoryformatversion": "0",
    "core.sshcommand": "ssh -i .git/arc3_crosslevel_voi_deploy_key -o IdentitiesOnly=yes -o UserKnownHostsFile=.git/github_known_hosts -o StrictHostKeyChecking=yes",
    "core.symlinks": "false",
    "remote.origin.fetch": "+refs/heads/*:refs/remotes/origin/*",
    "remote.origin.url": "https://github.com/bansarinejad/arc3-crosslevel-voi.git"
  },
  "plain_admin_relative_directories": [
    ".git",
    ".git\\hooks",
    ".git\\info",
    ".git\\objects",
    ".git\\objects\\info",
    ".git\\objects\\pack",
    ".git\\refs"
  ],
  "repository_ancestor_chain": [
    "D:\\",
    "D:\\kaggle competitions",
    "D:\\kaggle competitions\\arc3-crosslevel-voi"
  ],
  "repository_root": "D:\\kaggle competitions\\arc3-crosslevel-voi"
}
```

Both the supervisor and verifier independently enforce this object before accepting any
original-checkout HEAD, tag, tree, blob, raw-materialization, or status result. They use
fixed absolute paths and Windows non-reparse checks under the incorporated threat model.
The gate is:

1. walk the registered lexical absolute `repository_ancestor_chain` component by component
   from the volume root without resolving through a reparse point; require each member to be
   an existing plain directory and record its stable device/inode (`st_dev`/`st_ino`, backed
   by the Windows volume/file identity), type, and attributes before any descendant or Git
   read;
2. require the repository root and every `plain_admin_relative_directories` member to be an
   existing plain non-reparse directory, and require `.git/config`, `.git/info/exclude`, and
   the exact `index_path` to be stable plain non-reparse regular files;
3. require exact byte counts and SHA-256 values for config/exclude, and record the index's
   stable device/inode (`st_dev`/`st_ino`, backed by the Windows volume/file identity), type,
   attributes, size, and SHA-256;
4. invoke every original-checkout Git command with the frozen Windows Git followed
   immediately by `--no-replace-objects --no-optional-locks`, the exact seventeen-key empty-
   built environment, neutral subprocess control, and the registered 60-second local-Git
   allowance; resolve the absolute Git directory and common directory to the registered
   absolute paths;
5. parse `git config --local --null --list`, normalize keys to lowercase, reject duplicate
   keys, and require exact equality with `local_config`; includes, includeIf, extra keys, and
   changed values fail;
6. require the index to contain exactly stage-zero entries for the complete O8 tree with
   matching paths, modes, and blob IDs; reject unmerged stages, split-index/link extension,
   every `.git/sharedindex.*` entry, sparse-index/directory entries, sparse-checkout state,
   skip-worktree, assume-unchanged, and any other nonordinary cache-entry flag;
7. require every `forbidden_admin_relative_paths` member absent by no-follow/reparse-aware
   inspection, no loose or packed ref under `forbidden_ref_prefixes`, and no object-pack
   sidecar ending in `forbidden_pack_suffixes`;
8. require `.git/hooks` to contain no active hook basename; only plain non-reparse regular
   files whose names end in `.sample` are permitted;
9. require `.git/HEAD`, every accepted loose or packed ref, and every object entry used by
   the identity audit to be a stable plain non-reparse file reached only through plain
   non-reparse directories; recursively reject reparse entries beneath `.git/objects` and
   `.git/refs`; and
10. after the local Git evidence batch, recheck the lexical ancestor identities, every
    directory/file identity, index identity/size/SHA and exact stage-zero semantics,
    config/exclude identities, and all forbidden-source checks before accepting any result.

The exact config mapping excludes include directives, filters, fsmonitor, credential or URL
rewrites beyond the registered origin, alternate object directories, promisor/partial-clone
configuration, hooks-path overrides, replacement-ref bases, worktree/common-dir overrides,
and every other local key. The exact environment separately excludes all unlisted inherited
members. The tracked raw-byte audit remains independently required and is not replaced by
this gate. A supervisor-side failure before claim creation remains pre-lifecycle. A
verifier-side failure after the Windows lifecycle claim is represented by the one-shot
supervisor/finalization path; it never authorizes another query.

## 8. Exact remote-duration lower bound

For `n` persisted remote attempts, every validator requires exactly this necessary lower
bound:

```text
total_duration_milliseconds
>= sum(attempt.duration_milliseconds) + 15000 * max(0,n-1)
```

There is no `+n`, per-attempt one-millisecond flooring allowance, configured-deadline
addition, clamp, or upper bound. Flooring the containing V-entry interval is already at
least the sum of floored contained attempt intervals and exact retry gaps. Real validation,
loop, scheduling, and cleanup overhead above the lower bound remains valid. The producer
uses the one incorporated V-entry monotonic epoch and records the actual unclamped interval.

## 9. Implementation boundary and required tests

The following apparent gaps remain implementation of already frozen P8v3 requirements and
do not receive new v4 schema or theory: each runner's exact observed argv, complete raw Git
identity/hash chain, fixed preparation/verification/arm dependency chain, output-parent
descriptor gate, start-claim publication, and cleanup ownership. Their P8v3 tests remain
mandatory.

Before O8, all incorporated gates and these additional tests must pass:

- P8v4 is the one-file direct child of P8v3, its tag is lightweight, O8 is its direct child,
  the v4 document identities reconstruct exactly, and the v8-to-v7 reversal remains exact;
- the registration has exactly the section-3 execution keyset and exact section-7 Windows
  object; any missing, extra, reordered-array, or changed scalar/config member fails;
- finalizer return zero/nonzero with no descendant, passed lingering-descendant cleanup, and
  failed cleanup produces only the legal table row; conversion to `bundle_invalid`
  preserves true cleanup; a valid normal bundle is accepted only after the PGID is empty;
  zero return plus a canonical normal bundle plus cleanup false preserves normal bytes,
  creates and selects only the `child_cleanup_failed` emergency, and starts no later child;
- a complete canonical failed preparation receipt is retained in a normal administrative
  terminal with stage `preparation_receipt_invalid`, rejects every failed-attempt or cleanup
  mutation, cannot satisfy verification/arm/science, and cannot be replaced by null when its
  readable canonical bytes are recorded;
- Job construction failure and `Popen` failure yield only `spawn_error`; assignment failure
  and resume failure with passed cleanup yield only `post_spawn_initialization_failed`;
  either with failed cleanup yields only `child_cleanup_failed` and preserves actual
  timed-out and actual-or-null return evidence;
- capture failure with passed tree cleanup yields only `stream_capture_failed`; capture
  failure colliding with cleanup failure yields `child_cleanup_failed`; collision tests
  enforce the complete precedence and synthetic-124 restriction;
- attempt and supervisor stdout/stderr cap tests cover cap before timeout, timeout before cap,
  and exact collision: cap classification wins, the actual timeout Boolean is retained,
  cleanup is true, and exit is actual iff false or synthetic 124 iff true;
- every normal remote-attempt and supervisor classification is tested with null cleanup and
  with a real lingering Job member whose passed cleanup is recorded true; false is legal
  only for `child_cleanup_failed` and no orphan or later child survives;
- fake-clock tests prove post-spawn cleanup uses the single V+420 or S+460 endpoint, every
  taskkill/wait/Job/query/close/capture action consumes the same remainder, and no helper
  retains an ad-hoc five-second wait or resets an endpoint; attempt-timeout earlier than
  overall yields retryable timeout, while overall earlier or equal yields
  `overall_deadline`, including exact equality;
- every config key/value/addition/deletion/duplicate, include/includeIf, filter, fsmonitor,
  URL rewrite, credential helper, hooks path, config/exclude byte mutation, active hook,
  info attributes, alternate, graft, shallow marker, common-dir/worktree config, loose or
  packed replacement ref, promisor sidecar, reparse point, or post-check change fails before
  Windows local Git evidence is accepted;
- ancestor substitution at the volume/root/intermediate/repository boundary, index type or
  identity change, index lock, split/shared index, sparse state/directory, non-stage-zero or
  non-O8 entry, unmerged entry, skip-worktree, assume-unchanged, other cache flag, missing
  `--no-replace-objects` or `--no-optional-locks`, or post-Git index mutation fails before
  evidence acceptance;
- propagation tests prove a new remote-attempt classification fails the remote receipt but
  a clean verifier return of that canonical failure remains supervisor
  `verifier_completed`/`completed`, while a new supervisor-owned classification fails only
  the supervisor layer;
- all independent remote-receipt, supervisor-receipt, arm, finalizer, emergency, publisher,
  and reconstruction validators accept every legal new classification/nullability row and
  reject every other combination; and
- duration tests reject the obsolete `+n` allowance, accept the exact lower bound and real
  positive overhead, and accept actual cleanup overruns without an upper clamp.

All tests remain offline and synthetic. They create no real execution root, Windows claim,
remote receipt, scientific start, payload, result bundle, Git result object, or ref.

## 10. Scientific invariance and prohibited claims

The treatment ID, diagnostic ID, comparison semantics, all 140 scientific rows, all twelve
public scenes, every transform and control, every scientific function body, datum, selector,
tolerance, reason, fallback, scientific resource counter, analysis rule, dependency,
payload field, payload byte limit, and the 2,100/2,400/2,700-second scientific limits remain
exactly as incorporated. A and B remain deterministic observations of the one unchanged
treatment. The flat nineteen-key payload remains
`action-qbc-v8-open-diagnostic-payload-v1`. The underlying-stage order and every stage name
remain unchanged. All five authorization Booleans remain false.

This correction authorizes no preparation, remote query, scientific execution, gameplay,
leaderboard submission, development matrix, model change, lockbox, sealed phase, or positive
mechanism claim. It makes no calibrated-posterior, unseen-generalization, causality,
tamper-proofing, malicious-same-user, or Windows-directory-fsync claim. Any scientific
change requires a new v9 preregistration.
