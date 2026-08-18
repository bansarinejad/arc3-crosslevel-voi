# Action-QBC v8 open diagnostic: combined-gate fixture recovery (P8v9)

Date frozen: 19 August 2026 (Australia/Sydney)

Status: prospective administrative recovery amendment. This execution created
no local O8v5 commit, freeze-v5 tag, result-v5 tag, or v5 runtime path and
performed no authorized O8v5 push, runtime start, scientific start, or result
publication before these bytes were authored. No unqueried remote absence is
claimed.

## 1. Scope and authority

This amendment recovers from a stopped pre-O8v5 construction gate. The stopped
candidate exposed test-harness isolation and fixture drift; it did not expose a
scientific defect and did not create or consume a local or authorized-protocol
O8v5 or R8v5 namespace. No unqueried remote absence follows from that fact.

The frozen base is P8v8 commit
`98479dcf66411281e96fbcf88402a486490b2f79`, tree
`bb1dc0b765ea3f759896f1804050d061d7acff96`, and document:

    docs/experiment_amendment_2026-08-19_action_qbc_v8_open_bounded_remote_verification_v8_environment_relocation_recovery.md

That document has Git blob
`ee942a1b38ee74d16168c7f0dfccca2389e0e9cc`, raw SHA-256
`8a9f3d878c34465cc4a7b08bac48273befce8f4b8d06390d861c234801fb23d4`,
and byte count 70,826. P8v8 is the direct child of consumed R8v4 commit
`b1d4c68891f0ecee05363bafe8e12549d9c8430b`.

P8v9 must be the direct one-document child of P8v8. Its sole added path is:

    docs/experiment_amendment_2026-08-19_action_qbc_v8_open_bounded_remote_verification_v9_combined_gate_fixture_recovery.md

P8V9_COMMIT, P8V9_TREE, P8V9_DOCUMENT_GIT_BLOB_SHA1,
P8V9_DOCUMENT_SHA256, and P8V9_DOCUMENT_BYTE_COUNT mean identities derived
from the exact committed bytes after P8v9 exists. They are not operator choices
and are intentionally symbolic in this self-describing document.

This amendment authorizes only:

1. the exact commit-only P8v9 construction and publication in section 5;
2. the exact stale-registration removal in section 6;
3. corrections within the same fourteen O8 source paths in section 7;
4. one fresh P8v9-bound registration production and the frozen construction
   gates in section 8;
5. the otherwise incorporated O8v5 and outcome-dependent R8v5 sequence after
   every new gate succeeds.

It authorizes no reset, checkout, force operation, history rewrite, broad
cleanup, cache deletion, evidence deletion, scientific tuning, private-scene
access, gameplay, leaderboard submission, or extra scientific start.

### 1.1 P8v8 incorporation and exhaustive correction boundary

Except for the exhaustive narrow replacements below, P8v9 incorporates every
P8v8 requirement unchanged, including every scientific, schema, timing,
resource, evidence, authority, claim, ordering, publication-safety,
claim-before-import, no-cleanup, stop, and no-retry rule:

1. P8v9 becomes the direct preregistration parent and adds its exact lineage
   identities;
2. the sole P8v9 commit/tag publication and credential-disabled post-push query
   in section 5 are inserted before O8v5;
3. the pytest argv and argv-hash partition change only as section 8.2 and 8.3
   specify;
4. authority/attempt arithmetic and tree counts change only to the exact values
   in sections 9 and 10;
5. the two test-fixture files and the bounded administrative-lineage consumers
   change only as section 7 specifies; and
6. the exact stale P8v8 registration is removed and a new P8v9 registration is
   generated only as sections 6 and 8 specify.

This list is exhaustive. In particular, item 2 expressly and narrowly replaces
P8v8's rule that no network action may occur between its publication and O8v5:
only the P8v9 atomic push and immediately following one-shot query are inserted.
After that query, the incorporated no-network rule resumes until the authorized
O8v5 atomic push. No other P8v8 prohibition or obligation is weakened.

## 2. Exact stopped P8v8-bound candidate

### 2.1 Producer and registration

The P8v8 producer was invoked once with its registered argv and returned zero:

```json
["uv","run","--frozen","--extra","dev","python3","-I","-B","scripts/build_action_qbc_v8_open_registration.py","--repository-root",".","--preregistration-tag","prereg-action-qbc-v8-open-bounded-remote-verification-v8","--output","artifacts/action_qbc_v8_open_registration.json"]
```

Its sole canonical summary line was semantically exactly:

```json
{"content_sha256":"d2288e6bb8ed4ff6d17d18d0d0be9463319ffc1a519bb421b361675465b8b692","file_sha256":"93fd8e0b8174fd62e78ce659936bc85e7b06fc293bfac87c334dc37484a350f3","output":"artifacts/action_qbc_v8_open_registration.json","row_count":140,"status":"registered_zero_result"}
```

The generated registration had these exact identities:

- path: `artifacts/action_qbc_v8_open_registration.json`;
- byte count: 210,841;
- raw SHA-256:
  `93fd8e0b8174fd62e78ce659936bc85e7b06fc293bfac87c334dc37484a350f3`;
- Git blob SHA-1: `5a71573d94b697fb1c3ca903510d46981bff3e62`;
- content SHA-256:
  `d2288e6bb8ed4ff6d17d18d0d0be9463319ffc1a519bb421b361675465b8b692`;
- source-manifest SHA-256:
  `41870a6d9c8b246665a653197ba0fad529bf4df4999af398b76dc013777bc91d`;
- row count: 140;
- status: `registered_zero_result`.

At the stopped boundary its worktree path was an ordinary WSL regular file with
uid 1000, gid 1000, mode `0600`, link count 1, and no final LF byte. Its exact
stage-zero index entry had Git mode `100644` and blob
`5a71573d94b697fb1c3ca903510d46981bff3e62`.

The independent reconstructor was then invoked once with its registered argv,
returned zero, and emitted the semantically exact canonical summary:

```json
{"content_sha256":"d2288e6bb8ed4ff6d17d18d0d0be9463319ffc1a519bb421b361675465b8b692","file_sha256":"93fd8e0b8174fd62e78ce659936bc85e7b06fc293bfac87c334dc37484a350f3","row_count":140,"status":"verified"}
```

No additional raw-stream hash or invocation timestamp is asserted. The return
codes, canonical values, and exact frozen argv arrays are the retained facts.

The P8v8 producer authorization is consumed. Neither the old registration nor
the old producer invocation may be reused or repeated under P8v8.

### 2.2 Exact staged state and never-committed tree

After the registration was staged, the index represented P8v8 plus exactly the
fifteen registered O8 paths. The index had:

- raw SHA-256:
  `eb997b5170d83bc18555c6400849aaab4cf0d96092cb367c59637d5dd7c9c2f3`;
- byte count: 25,725;
- total stage-zero entry count: 249.

The computed-only prospective tree identity was
`404c20ead560183eaf6de19f3731c3d00b693330`; that hypothetical tree contained
249 entries. No tree object with that identity existed, and it was never
committed, tagged, pushed, or made authoritative. Only the stale registration
blob may remain as an unreachable local object. This amendment authorizes no
object-store deletion and gives that blob no evidentiary status.

### 2.3 Exact failed gate

The reconstructor passed, then the first of the three frozen construction-gate
arrays ran with the incorporated P8v8 pytest argv. It returned 1 after 143.96
seconds with exactly:

    621 passed, 30 skipped, 12 failed

The following twelve node IDs failed:

```text
tests/test_action_qbc_v8_lifecycle.py::test_validator_rejects_a_runner_helper_with_preclaim_import_side_effects
tests/test_action_qbc_v8_lifecycle.py::test_validator_runner_helper_exec_failure_cleans_private_module_authority
tests/test_action_qbc_v8_lifecycle.py::test_validator_runner_helper_replacement_failure_cleans_private_authority
tests/test_action_qbc_v8_lifecycle.py::test_validator_verified_actual_helper_remains_exact_until_caller_cleanup
tests/test_action_qbc_v8_lifecycle.py::test_isolated_runtime_gate_rejects_preloaded_science_and_path_injection
tests/test_action_qbc_v8_lifecycle.py::test_real_promoted_a_b_children_claim_before_exact_installed_import
tests/test_action_qbc_v8_registration.py::test_prepare_attempt_orders_raw_audits_around_build_and_promotes_all_four_paths
tests/test_action_qbc_v8_registration.py::test_prepare_attempt_budget_and_cleanup_gate_are_fail_closed[retry_then_success-expected_attempts0-prepared]
tests/test_action_qbc_v8_registration.py::test_prepare_attempt_budget_and_cleanup_gate_are_fail_closed[cleanup_failure_stops-expected_attempts1-None]
tests/test_action_qbc_v8_registration.py::test_prepare_attempt_budget_and_cleanup_gate_are_fail_closed[two_clean_failures-expected_attempts2-failed]
tests/test_action_qbc_v8_registration.py::test_reconstructor_independently_revalidates_prepared_receipt_and_live_clones
tests/test_action_qbc_v8_registration.py::test_real_offline_uv_copy_mode_environment_survives_parent_promotion
```

The stop rule was obeyed. The Ruff array, strict-mypy array, O8 commit, O8 tag,
O8 publication, anonymous freeze query, authority bootstrap, preparation,
remote supervisor, remote verifier, lifecycle, scientific runners, payload
validators, finalizer, and result publisher were not invoked. No later array
or runtime action is backfilled by this amendment.

### 2.4 Exact pytest-cache drift

The stopped pytest process changed exactly these retained cache payloads:

| path | bytes | raw SHA-256 | `mtime` UTC |
|---|---:|---|---|
| `.pytest_cache/v/cache/nodeids` | 171,628 | `a8ba0e21fe91210b4f423ff386f26671f6ffdd74c4fd06f01499e280a8c07d32` | `2026-08-18T18:27:11.3112258Z` |
| `.pytest_cache/v/cache/lastfailed` | 2,170 | `27cd9944502657938477a560a35537f42b11e89bd2ecd8a479887489817cc960` | `2026-08-18T18:27:11.3278740Z` |

Under WSL both paths are ordinary regular files on device 99 with uid 1000,
gid 1000, mode `0644`, and link count 1. `nodeids` has inode
`281474977098859`; `lastfailed` has inode `844424930522681`. Windows reports
both as plain, non-reparse, Archive files owned by `MSI\User`.

The exact `lastfailed` payload contains sixteen node keys whose values are
`true`: the twelve current failures in section 2.3 plus four pre-existing keys.
The four pre-existing keys are retained cache history, not failures attributed
to this stopped combined gate.

No new `tests/__pycache__/test_action_qbc_v8_registration.cpython-312-pytest-8.4.2.pyc`
was retained. No such pyc identity is attributed to the stopped gate.

The two cache files are non-authoritative local tool state. They are not Git
tree members, protocol evidence, scientific evidence, or registration input.
They must remain byte-for-byte and metadata-stable through this recovery. This
amendment does not authorize deleting, truncating, rewriting, restoring, or
otherwise cleaning either cache file or any parent cache directory. Any cache
identity change is a stop condition.

### 2.5 Read-only metadata-audit telemetry

The first default WSL metadata-audit invocation was blocked by the sandbox with
`E_ACCESSDENIED` before a Linux child started. An approved first retry then
mis-tokenized the format and path: `stat` reported a missing operand and Bash
reported permission errors. That retry changed no repository, index, ref,
cache, network, protocol, or evidence state. A direct
`wsl -e /usr/bin/stat` retry returned zero and yielded the metadata frozen in
section 2.4. These events are authoring telemetry only. This amendment claims
neither exact raw stdout/stderr identity nor scientific or protocol execution
for them.

Separately, an earlier timed audit pytest context created the nonprotocol local
path
`tests/__pycache__/test_action_qbc_v8_registration.cpython-312-pytest-8.4.2.pyc`.
Its retained facts are byte count 549,253 and `mtime`
`2026-08-18T17:50:41Z`. It was exactly removed before the official combined
gate. No SHA-256, Git blob, mode, owner, creator-command detail, or raw-stream
identity was retained, and none is inferred here. That audit-created and
removed pyc is distinct from the official gate's two retained cache changes.

During the final document-only audit, two Python AST-wrapper invocations were
also nonprotocol failures. Windows native-argv quote stripping altered the
first wrapper's data argument, so `ast.parse` reported `SyntaxError` before any
embedded unlink-helper source executed. A first base64 wrapper then lost quotes
inside its own wrapper expression and raised `NameError`, again before embedded
source execution. A later wrapper passed base64 only as data, decoded it without
a quoted codec argument, and successfully parsed the embedded source as an AST;
it did not execute that source. These invocations made no repository, index,
ref, cache, network, protocol, or evidence mutation. No exact wrapper argv,
stdout, stderr, timestamp, or raw-stream identity is retained or inferred. They
do not consume either removal-process authorization in section 6.

## 3. Failure classification

Read-only retained-context and source diagnosis accounts for all twelve
failures as construction-fixture defects. No failed node was rerun or reproduced
after the official stop. None justifies changing the production preload gates,
installed-origin gates, environment validator, recovery-tree validator,
preparation retry policy, schema, or science.

### 3.1 Combined-process project-module state

The combined pytest command collects
`tests/test_action_qbc_v8_audit.py` before executing the lifecycle nodes. That
module imports `arc3_voi.action_qbc_v7_audit`,
`arc3_voi.action_qbc_v8_audit`, and `arc3_voi.types` at collection time. The
modules correctly remain in the pytest process-wide `sys.modules` mapping.

Five lifecycle tests incorrectly assumed that their in-process interpreter had
no preloaded `arc3_voi` module. Four reached
`_preverify_and_load_runner` with the project package already resident and were
rejected before their intended hostile-helper fixture. The isolated-runtime
test was likewise rejected before its intended baseline assertion.

The production checks are correct. A real runner or validator child is a fresh
registered `-I -B` interpreter and must reject every pre-claim project preload.
The correction belongs only in lifecycle test isolation.

### 3.2 Stale preparation and reconstruction fixtures

The registration ordering test still mocked the retired split inventory and
materialization helpers. Current preparation uses the combined
`_validate_installed_environment` helper, so the test reached the real helper
against an intentionally empty clone.

The three retry parameter cases supplied `_RawAudit(entries=())`. The exact
historical recovery-tree validation correctly rejected that value before the
retry state machine under test.

The independent-reconstructor receipt fixture supplied hand-made empty venvs,
reached the real combined validator, and retained an obsolete nine-token
environment build argv instead of the exact twelve-token P8v8/P8v9 argv.

These are fixture defects. The combined production validator and immutable
historical O8v4/R8v4 reconstruction remain mandatory and unchanged.

### 3.3 Ambient uv destination leakage

The shared disposable-copy helper copied ambient `os.environ` and removed only
`VIRTUAL_ENV`. The registered construction shell contains
`UV_PROJECT_ENVIRONMENT=.venv-wsl`. Consequently `/usr/local/bin/uv` returned
zero but built `.venv-wsl` beneath each disposable root, leaving the fixture's
required `.venv` absent. The real registration and lifecycle smoke nodes then
failed before any fresh child scientific import.

Production preparation does not use that ambient mapping. It launches the
environment build with the exact registered preparation command environment.
The correction belongs only in the shared registration test helper.

## 4. Namespace ruling

The following remained absent after the stopped gate:

- local `refs/tags/action-qbc-v8-open-diagnostic-freeze-v5`;
- local `refs/tags/action-qbc-v8-open-diagnostic-result-v5`;
- `/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v5`;
- `D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification-claim-v5.json`;
- `D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verifier-start-claim-v5.json`;
- `D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification-v5.json`;
- `D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification-supervisor-v5.json`.

No network mutation or public visibility query was consumed by the stopped
construction. The exact local v5 refs were absent and no authorized v5 ref
creation or publication occurred. This amendment does not claim or infer remote
or public absence of either v5 tag. Their later sole non-force pushes must prove
new-tag creation through exact returned status or stop on collision.

This amendment reuses v5 consistently for the O8 freeze tag, R8 result tag,
Linux execution root, Windows evidence paths, and all derived path literals.
It does not authorize a partial v5/v6 mix. Immediately before the first
post-P8v9 v5 action, every absence above must be revalidated through the
incorporated local collision gates. Any collision stops the recovery and
requires a later preregistration amendment; no operator may substitute v6
under this document.

The consumed preregistration namespace is different. P8v8 and its immutable
tag remain historical. P8v9 has the new lightweight tag:

    prereg-action-qbc-v8-open-bounded-remote-verification-v9

The branch remains:

    refs/heads/action-qbc-v8-prereg

## 5. Commit-only P8v9 construction and publication

### 5.1 Preserve the staged fifteen entries

The five newly authorized local processes in sections 5 and 6 - direct Git
`add`, `commit`, `tag`, and `rm`, plus the WSL Python unlink/fsync helper - each
has an exact externally enforced 60-second wall timeout and independent raw
stdout and raw stderr capture caps of 1,048,576 bytes per stream. Capture starts
with process creation, keeps the streams separate, and performs no
decode/re-encode or presentation transform. These timeout/cap settings belong
to the external supervisor and are not argv members. Exact success for every
one of the five processes requires zero stdout and zero stderr bytes. A spawn,
timeout, cap, capture, cleanup, ambiguity, or nonzero-exit boundary consumes
that process authorization and stops without retry. The incorporated network
push/query bounds remain unchanged and are not replaced by this local envelope.

Before the P8v9 document is staged, revalidate all facts in section 2. In
particular, HEAD must be exact P8v8 and the fifteen staged path/mode/blob entries
must still produce computed-only prospective tree identity
`404c20ead560183eaf6de19f3731c3d00b693330` and the exact failed registration.
The two cache files must retain section 2.4 identities.

Stage only this recovery document in addition to the existing fifteen entries
by invoking this exact Windows Git argv directly without a shell:

```json
["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-C","D:\\kaggle competitions\\arc3-crosslevel-voi","add","--","docs/experiment_amendment_2026-08-19_action_qbc_v8_open_bounded_remote_verification_v9_combined_gate_fixture_recovery.md"]
```

Require exit zero and the exact zero-stream outcome under the local envelope.
Then audit an exact A16 index relative to P8v8: 250 stage-zero entries, the
unchanged frozen failed A15 path/mode/blob entries plus only this document at
mode `100644` and P8V9_DOCUMENT_GIT_BLOB_SHA1, with no other stage, flag, path,
or worktree change. Both pytest-cache identities remain exact. Any add or A16
failure is terminal; do not repeat `add`, unstage, repair, or run `commit`.

Create P8v9 by invoking this binding Windows Git argv directly without a shell,
passing every JSON member as one argv token:

```json
["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-C","D:\\kaggle competitions\\arc3-crosslevel-voi","-c","user.name=behzad.ansarinejad","-c","user.email=behzad.ansarinejad@gmail.com","-c","user.useConfigOnly=true","-c","commit.gpgSign=false","-c","core.hooksPath=NUL","commit","--only","--quiet","--no-gpg-sign","--no-verify","--cleanup=verbatim","-m","Preregister action QBC v8 open diagnostic recovery v9","--","docs/experiment_amendment_2026-08-19_action_qbc_v8_open_bounded_remote_verification_v9_combined_gate_fixture_recovery.md"]
```

The `core.hooksPath=NUL` configuration disables every hook; `--no-verify` also
forbids the bypassable commit hooks. `commit.gpgSign=false` and
`--no-gpg-sign` disable signing. `--cleanup=verbatim` is binding, and the exact
commit-message payload is the single subject above followed by one LF, with no
body. `user.useConfigOnly=true` plus the two explicit identity values makes both
the author and committer
`behzad.ansarinejad <behzad.ansarinejad@gmail.com>`.

The launch environment must contain none of `GIT_AUTHOR_NAME`,
`GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`,
`GIT_AUTHOR_DATE`, or `GIT_COMMITTER_DATE`. No `--author`, `--date`, replacement
clock, preselected timestamp, or other author/committer/date override is
permitted. Git chooses the two timestamps during this sole command; only after
it returns may both raw commit timestamps and offsets be observed, recorded,
and audited. They are not preregistration inputs.

`--only` is binding. The commit must have exactly one parent, P8v8, and its tree
must be exact P8v8 plus only this document. It must contain 235 recursive
entries. The post-command audit must also prove the exact author, committer,
message, parent, tree, path delta, lack of signature, and observed timestamps.
The process must return zero with the exact zero-stream outcome under the local
envelope; `--quiet` is binding. Any other outcome is terminal and consumes the
commit authorization.

After the commit, the ordinary index relative to P8v9 must again contain the
same exact fifteen staged path/mode/blob entries and no recovery-document
delta. No reset, mixed reset, checkout, restore, alternate index, or restaging
of those fifteen entries is authorized as part of P8v9 creation.

If commit-only construction changes, omits, restages, or commits any of the
fifteen entries, stop. Do not repair or retry the P8v9 commit.

### 5.2 Tag and publish P8v9

Immediately before tag creation, the local ref
`refs/tags/prereg-action-qbc-v8-open-bounded-remote-verification-v9` must be
absent. No remote absence is claimed or queried. Invoke this exact Windows Git
argv directly without a shell:

```json
["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-C","D:\\kaggle competitions\\arc3-crosslevel-voi","-c","tag.gpgSign=false","tag","--no-sign","prereg-action-qbc-v8-open-bounded-remote-verification-v9","P8V9_COMMIT"]
```

Require exit zero and the exact zero-stream outcome under the local envelope.
Post-command local audits must prove that the new ref resolves to exactly
P8V9_COMMIT; resolving the ref names an object of type `commit`, not `tag`; no
annotated or signed tag object was created; and no other ref moved. The tag is
then immutable. Any pre-existing local ref, nonzero or nonempty-stream result,
timeout, ambiguity, wrong type or resolution, or other-ref movement consumes
the sole tag authorization and stops. Do not retry, delete, replace, force, or
repair the tag.

Only after those audits pass may the preregistration branch fast-forward P8v8
to P8v9 through this exact atomic publication argv:

```json
["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-C","D:\\kaggle competitions\\arc3-crosslevel-voi","push","--atomic","origin","refs/heads/action-qbc-v8-prereg:refs/heads/action-qbc-v8-prereg","refs/tags/prereg-action-qbc-v8-open-bounded-remote-verification-v9:refs/tags/prereg-action-qbc-v8-open-bounded-remote-verification-v9"]
```

No force flag or lease override is permitted. The tag status must be exact
new-tag creation; an existing tag, up-to-date tag, rejected branch, non-fast-
forward, or any other status stops.

Only after that successful atomic push, consume this exact credential-disabled
anonymous query once, with every JSON member passed as a distinct argv token:

```json
["C:\\Windows\\System32\\wsl.exe","-d","Ubuntu","--cd","D:\\kaggle competitions","--","/usr/bin/env","-i","GIT_CONFIG_COUNT=0","GIT_CONFIG_GLOBAL=/dev/null","GIT_CONFIG_NOSYSTEM=1","GIT_NO_REPLACE_OBJECTS=1","GIT_TERMINAL_PROMPT=0","HOME=/home/bansarinejad","LANG=C","LC_ALL=C","PATH=/usr/local/bin:/usr/bin:/bin","XDG_CONFIG_HOME=/nonexistent","/usr/bin/git","--no-replace-objects","-c","credential.interactive=never","-c","core.askPass=","-c","credential.helper=","ls-remote","--refs","https://github.com/bansarinejad/arc3-crosslevel-voi.git","refs/heads/action-qbc-v8-prereg","refs/tags/prereg-action-qbc-v8-open-bounded-remote-verification-v9"]
```

The exact executable is `C:\Windows\System32\wsl.exe`; the neutral Windows cwd
token is `D:\kaggle competitions`, corresponding to WSL cwd
`/mnt/d/kaggle competitions`; `/usr/bin/env -i` constructs the exact empty-base
environment shown above; and `/usr/bin/git` reads the literal public HTTPS URL.
No shell, ambient variable, credential helper, alternate remote, authenticated
transport, ref reordering, or argv substitution is permitted.

Capture exit code, stdout, and stderr separately as raw byte streams without
merging, decoding-and-reencoding, truncation, or presentation transformation.
Success is exit zero, zero stderr bytes with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
and the concatenation of exactly these two ASCII strings, branch first and tag
second, each once, where `P8V9_COMMIT` is the same recorded lowercase 40-hex
commit in both positions:

```json
["P8V9_COMMIT\trefs/heads/action-qbc-v8-prereg\n","P8V9_COMMIT\trefs/tags/prereg-action-qbc-v8-open-bounded-remote-verification-v9\n"]
```

No peeled, duplicate, additional, malformed, reordered, credential-assisted,
or authenticated record is accepted. The authorization is consumed whether
the process succeeds, fails, times out, or is ambiguous; it is never retried.
The query proves only the two post-push values and does not prove prior remote
absence. No pre-push public query or additional recovery query is authorized.

This P8v9 atomic push and immediately following one-shot query are the sole,
narrow supersession of P8v8's no-network-between-P8v8-and-O8v5 clause. After
this query, that clause resumes unchanged until the authorized O8v5 atomic push.

PUBLIC repository visibility remains unchanged. P8v8 and prereg-v8 remain
immutable and publicly reachable.

## 6. Sole post-publication stale-artifact removal

Only after P8v9 commit, tag, atomic publication, and public verification all
succeed may the stale P8v8-bound registration be removed. This is one exact
two-process operation. Each process is authorized once, in the order below.

Before process 1, require all section-2.1 byte identities, an ordinary
no-follow WSL worktree regular file with uid 1000, gid 1000, mode `0600`, link
count one, size 210,841, raw SHA-256
`93fd8e0b8174fd62e78ce659936bc85e7b06fc293bfac87c334dc37484a350f3`,
and no final LF byte, plus the exact stage-zero Git mode `100644` index blob
`5a71573d94b697fb1c3ca903510d46981bff3e62`.

Process 1 is exactly:

```json
["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-C","D:\\kaggle competitions\\arc3-crosslevel-voi","rm","--cached","--quiet","--","artifacts/action_qbc_v8_open_registration.json"]
```

Invoke it directly without a shell and capture exit code, stdout, and stderr
separately under the local envelope. `--quiet` is binding; it must return zero
with exactly zero stdout and zero stderr bytes. Immediately afterward, the
registration must be absent from every index stage while its worktree file
retains every exact pre-process byte and no-follow metadata identity above. No
other index entry or worktree path may change. A nonzero, nonempty-stream,
timed-out, capped, ambiguous, partial, or unexpected result stops before
process 2 and is never retried or repaired.

Process 2 is this exact WSL argv; the final JSON member is one `-c` source token,
including every encoded LF shown:

```json
["C:\\Windows\\System32\\wsl.exe","-d","Ubuntu","--cd","D:\\kaggle competitions\\arc3-crosslevel-voi","--","/usr/bin/env","-i","LANG=C","LC_ALL=C","PATH=/usr/bin:/bin","/usr/bin/python3","-I","-B","-c","import hashlib\nimport os\nimport stat\n\nDIRECTORY = \"artifacts\"\nNAME = \"action_qbc_v8_open_registration.json\"\nEXPECTED_SIZE = 210841\nEXPECTED_SHA256 = \"93fd8e0b8174fd62e78ce659936bc85e7b06fc293bfac87c334dc37484a350f3\"\nFIELDS = (\"st_dev\", \"st_ino\", \"st_mode\", \"st_uid\", \"st_gid\", \"st_nlink\", \"st_size\", \"st_mtime_ns\", \"st_ctime_ns\")\n\ndef identity(value):\n    return tuple(getattr(value, field) for field in FIELDS)\n\nif os.path.basename(NAME) != NAME:\n    raise SystemExit(\"registration name is not a basename\")\ndirectory_fd = os.open(DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)\ntry:\n    before = os.stat(NAME, dir_fd=directory_fd, follow_symlinks=False)\n    if not (\n        stat.S_ISREG(before.st_mode)\n        and before.st_uid == 1000\n        and before.st_gid == 1000\n        and stat.S_IMODE(before.st_mode) == 0o600\n        and before.st_nlink == 1\n        and before.st_size == EXPECTED_SIZE\n    ):\n        raise SystemExit(\"stale registration metadata mismatch\")\n    file_fd = os.open(NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory_fd)\n    try:\n        opened = os.fstat(file_fd)\n        if identity(opened) != identity(before):\n            raise SystemExit(\"stale registration changed before descriptor open\")\n        data = bytearray()\n        eof_reached = False\n        while len(data) < EXPECTED_SIZE + 1:\n            chunk = os.read(file_fd, EXPECTED_SIZE + 1 - len(data))\n            if not chunk:\n                eof_reached = True\n                break\n            data.extend(chunk)\n        after = os.fstat(file_fd)\n        if identity(after) != identity(opened):\n            raise SystemExit(\"stale registration changed during descriptor read\")\n    finally:\n        os.close(file_fd)\n    if (\n        not eof_reached\n        or len(data) != EXPECTED_SIZE\n        or hashlib.sha256(data).hexdigest() != EXPECTED_SHA256\n        or data.endswith(b\"\\n\")\n    ):\n        raise SystemExit(\"stale registration byte identity mismatch\")\n    current = os.stat(NAME, dir_fd=directory_fd, follow_symlinks=False)\n    if identity(current) != identity(after):\n        raise SystemExit(\"stale registration changed before unlink\")\n    os.unlink(NAME, dir_fd=directory_fd)\n    try:\n        os.stat(NAME, dir_fd=directory_fd, follow_symlinks=False)\n    except FileNotFoundError:\n        pass\n    else:\n        raise SystemExit(\"stale registration remains after unlink\")\n    os.fsync(directory_fd)\nfinally:\n    os.close(directory_fd)"]
```

The helper opens the `artifacts` directory with `O_DIRECTORY|O_NOFOLLOW`, uses
only descriptor-relative no-follow `stat`, `open`, and `unlink` operations for
the fixed basename, checks the registered regular-file type, uid, gid, mode,
link count, size, SHA-256, and absent final LF, and compares the complete live
device/inode/mode/uid/gid/link-count/size/mtime/ctime tuple before, during, and
after its descriptor read. Its bytearray can hold at most
`EXPECTED_SIZE + 1` bytes; exact acceptance requires an observed EOF with
exactly `EXPECTED_SIZE` bytes before hashing or unlinking. Only after all
pre-unlink checks pass may it unlink that basename. It then proves
descriptor-relative absence and fsyncs the open parent directory. It emits no
success output. The prior producer already demonstrated directory fsync on this
filesystem; no preliminary removal or fsync probe is authorized.

Invoke process 2 directly without another shell and capture exit code, stdout,
and stderr separately. Exact success is exit zero with zero stdout and zero
stderr bytes. If it fails before unlink, succeeds in unlinking but fails its
absence/fsync boundary, times out, or is ambiguous, the operation is partial
and terminal: do not repeat either process, re-add the index entry, run another
unlink, repair the directory, or continue under P8v9.

After exact two-process success, audit all these postconditions before any
section-7 edit:

1. HEAD remains exact P8v9 and every local ref is unchanged; no other worktree
   entry's name, type, or bytes change, apart from the inherent `artifacts`
   directory metadata effect of removing and durably fsyncing the basename;
2. `artifacts/action_qbc_v8_open_registration.json` is absent from every index
   stage and absent by descriptor-relative no-follow worktree lookup;
3. the index contains exactly 249 stage-zero entries and, relative to P8v9, is
   exact A14: precisely the fourteen section-7.1 paths, each mode `100644` and
   each retaining its exact pre-removal failed-A15 blob; there is no unmerged,
   intent-to-add, skip-worktree, assume-unchanged, extra, or missing entry;
4. the committed P8v9 document has no index or worktree delta, and no source
   blob has yet been replaced under section 7;
5. both section-2.4 pytest-cache files retain their exact bytes, SHA-256,
   device, inode, uid, gid, mode, link count, `mtime`, Windows owner, attributes,
   and non-reparse status; and
6. the `artifacts` directory remains present and the helper's successful parent
   fsync is the sole worktree durability mutation beyond removing the basename.

Any postcondition mismatch is a partial terminal STOP with no retry or repair.
No broad clean, reset, checkout, object deletion, cache cleanup, source
deletion, alternate helper, or third removal process is authorized. The two
`.pytest_cache` files remain a bounded local authoring exception only; neither
may enter P8v9, O8v5, a registration manifest, an authority clone, an execution
clone, or any published tree.

## 7. Exact source correction boundary

### 7.1 Path allowlist

P8v9 deletes no O8 path because those paths are not in its tree. O8v5 may add
all and only these fourteen non-registration paths:

```text
docs/action_qbc_v8_open_diagnostic_runbook.md
scripts/build_action_qbc_v8_open_registration.py
scripts/execute_action_qbc_v8_open_lifecycle.py
scripts/finalize_action_qbc_v8_open_diagnostic.py
scripts/prepare_action_qbc_v8_open.py
scripts/reconstruct_action_qbc_v8_open_registration.py
scripts/run_action_qbc_v8_open_diagnostic.py
scripts/supervise_action_qbc_v8_remote_tag.py
scripts/validate_action_qbc_v8_open_payload.py
scripts/verify_action_qbc_v8_remote_tag.py
src/arc3_voi/action_qbc_v8_audit.py
tests/test_action_qbc_v8_audit.py
tests/test_action_qbc_v8_lifecycle.py
tests/test_action_qbc_v8_registration.py
```

The fresh P8v9-bound producer later creates the sole fifteenth path:

    artifacts/action_qbc_v8_open_registration.json

Every addition is Git mode `100644`. There is no rename, deletion, submodule,
symlink, executable path, or sixteenth addition.

### 7.2 Lifecycle test isolation

`tests/test_action_qbc_v8_lifecycle.py` must give each of the five affected
in-process clean-runtime tests an exact project-module isolation boundary. The
boundary must:

1. snapshot every existing `sys.modules` entry named `arc3_voi` or beginning
   `arc3_voi.` and retain the exact module object for each name;
2. remove only those entries before the clean-runtime assertion;
3. allow the test's intended hostile or private-helper entry to exercise the
   unchanged production rejection/cleanup behavior;
4. remove every project-module entry created inside the boundary; and
5. restore the exact prior name-to-object mapping before leaving the test.

It may not reload science, synthesize a passing production state, weaken the
preload predicate, or hide a module from a real runner/validator child. Extend
only existing node bodies or their existing shared fixture so the same five
node IDs prove their behavior after audit-module collection has populated the
parent pytest process. Do not add, rename, parameterize, split, or remove a test
node; the exact combined node inventory must remain unchanged.

The production validator and runner must continue to reject every `arc3_voi`
preload before their durable claim and must retain exact post-import origin and
byte revalidation.

### 7.3 Registration fixture corrections

`tests/test_action_qbc_v8_registration.py` must make these fixture-only
corrections:

- the preparation ordering fixture mocks and observes the combined
  `_validate_installed_environment` return tuple rather than obsolete split
  inventory/materialization helpers;
- all three retry cases use a complete exact frozen recovery-tree audit with
  immutable historical O8v4 addition entries, so they reach the retry logic
  they claim to test;
- the independent-reconstructor receipt fixture uses the exact twelve-token
  environment build argv and a complete combined environment-validator state,
  not empty hand-made venvs plus a nine-token argv;
- the disposable copy-mode builder passes the registration's exact
  `preparation_command_environment` to the environment-build child instead of
  copying ambient `os.environ`; in particular ambient
  `UV_PROJECT_ENVIRONMENT=.venv-wsl` may not redirect the child; and
- the real registration and lifecycle fixtures require `.venv` beneath each
  disposable process root, exact noneditable copy-mode installation, and the
  unchanged shared thirteen-key materialization/RECORD/origin contract.

No production validation is relaxed. Historical O8v4/R8v4 blobs, the
thirteen-key walker, regular-file single-link rule, exact four symlinks,
noneditable installation, RECORD closure, installed origin, and post-import
revalidation remain unchanged.

### 7.4 P8v9 lineage propagation

Administrative consumers must retain P8v8 as immutable history and make P8v9
the active preregistration parent. They must update only the identities,
lineage rows, path-derived administrative hashes, runbook facts, and regression
expectations implied here.

The scientific audit source remains an exact administrative overlay. Its
P8v9-bound version must reverse to the same O8v4 and frozen v7 scientific
source under exact count, byte, Git-blob, SHA-256, AST, and function-inventory
audits. No scientific literal, function body, schema, row, scene, transform,
control, tolerance, fallback, limit, or authorization Boolean may change.

The historical registration builder remains byte-identical to its incorporated
O8v1 bytes. P8v9 behavior continues to come through the independent same-path
reconstructor; prose-only builder churn is forbidden.

## 8. Fresh P8v9-bound registration and gates

### 8.1 Stage fourteen, then produce once

After section 7, the index relative to P8v9 must have exactly the fourteen
listed additions, each ordinary stage zero and mode `100644`. The stale
registration must be absent. No source path may retain a P8v8 active-parent
constant where P8v9 is required.

Invoke the producer exactly once under P8v9:

```json
["uv","run","--frozen","--extra","dev","python3","-I","-B","scripts/build_action_qbc_v8_open_registration.py","--repository-root",".","--preregistration-tag","prereg-action-qbc-v8-open-bounded-remote-verification-v9","--output","artifacts/action_qbc_v8_open_registration.json"]
```

That is a new one-shot authorization derived from P8v9. It is not a retry of
the consumed P8v8 producer. Stage the new registration as the sole fifteenth
addition, verify it with the independent reconstructor once, and freeze its
new content, file, blob, source-manifest, and index identities. No failed
section-2 identity may be copied forward as an expected P8v9 value.

### 8.2 Exact no-cache pytest argv

The fresh execution contract changes the tests argv to this exact array:

```json
["uv","run","--frozen","--extra","dev","pytest","-p","no:cacheprovider","-q","tests/test_action_qbc_v7_audit.py","tests/test_action_qbc_v8_audit.py","tests/test_action_qbc_v8_lifecycle.py","tests/test_action_qbc_v8_registration.py"]
```

`-p no:cacheprovider` is an explicit administrative construction control. No
`PYTEST_ADDOPTS`, alias, plugin autoload substitution, reordered spelling, or
post-test cache cleanup may substitute for it. The two retained cache files
must have the same bytes and metadata before and after pytest.

The twelve node IDs in section 2.3 may not be renamed, removed, skipped, xfailed,
or deselected. With the node inventory unchanged, the exact successful combined
outcome is 633 passed, 30 skipped, zero failed. Any additional, missing,
renamed, skipped, xfailed, deselected, or failed node stops construction.

Only after pytest succeeds may the unchanged Ruff array run; only after Ruff
succeeds may the unchanged strict-mypy array run. If the producer,
reconstructor, pytest, Ruff, mypy, an index audit, or a cache-stability check
fails, no later array or O8 operation may run. There is no retry under P8v9.

### 8.3 Exact argv-hash partition

The execution contract retains exactly eighteen argv-hash keys. Relative to
consumed O8v4, these fifteen hashes must derive-change:

```text
arm
bootstrap
environment_build
finalizer
lifecycle_driver
payload_validator
post_preparation_validation
preparation
producer
remote_supervisor
remote_verifier
result_publisher
result_ref_transaction
scientific
tests
```

These three hashes must remain unchanged:

```text
linux_host_launcher
preflight
reconstructor
```

There is no nineteenth key. The sole difference from P8v8's 14/4 partition is
the explicit no-cache tests argv. The exact twelve-token environment-build
array remains:

```json
["/usr/bin/env","UV_OFFLINE=1","/usr/local/bin/uv","sync","--python","3.12.13","--frozen","--no-dev","--offline","--no-editable","--link-mode","copy"]
```

Its canonical SHA-256 remains
`a815872b8bc76c3b8118e47ddac9e0e36b97820181a81ae28cc1bcddcc9a642c`.
The three dependency rows retain exact order, names, versions, and key sets;
all three `editable` values remain false.

## 9. Lineage, tree counts, and result boundary

The binding lineage is:

    P8v7 -> O8v4 -> R8v4 -> P8v8 -> P8v9 -> O8v5 -> R8v5

The exact tree relations are:

- P8v8 has 234 entries;
- P8v9 is exact P8v8 plus this one document and has 235 entries;
- P8v7 to P8v9 is exact A2, the P8v8 and P8v9 documents;
- R8v4 to P8v9 is exact D17+A2;
- O8v5 is P8v9's exact A15 child and has 250 entries;
- scientific R8v5 is O8v5+A3 and has 253 entries;
- normal administrative R8v5 is O8v5+A2 and has 252 entries; and
- doc-only override R8v5 is O8v5+A1 and has 251 entries.

The retained and reused prospective tag names are:

```text
action-qbc-v8-open-diagnostic-freeze-v5
action-qbc-v8-open-diagnostic-result-v5
```

Neither name denotes an already-created immutable local tag at this freeze, and
no remote absence is claimed. Freeze-v5 becomes immutable only after its valid
sole creation at exact O8v5. Result-v5 becomes immutable only after its valid
sole creation at the selected exact R8v5. Neither tag may point to P8v8, P8v9,
the computed-only stopped prospective tree identity, or a failed registration.

The stable result branch may advance only by non-force fast-forward along:

    R8v4 -> P8v8 -> P8v9 -> O8v5 -> R8v5

No alternate parent, merge commit, force update, or skipped lineage node is
permitted.

## 10. Authority and attempt command arithmetic

The O8v5 authority plan has exactly 70 rows, ordered as follows:

1. one initial local-config row;
2. freeze-v5 tag-type, tag-resolution, and HEAD rows;
3. four rows each for P8v1, P8v2, P8v3, P8v4, O8v1, P8v5, O8v2,
   P8v6, O8v3, P8v7, O8v4, R8v4, P8v8, and P8v9: tag type,
   resolution, sole-parent relation, and exact direct diff;
4. P8v9 document `ls-tree` and `cat-file` rows;
5. O8v5 sole-parent P8v9 and exact P8v9-to-O8v5 A15 rows; and
6. the incorporated post-config, HEAD, tree, batch-object, index, and status
   rows.

The arithmetic is:

    1 + 3 + (14 * 4) + 2 + 2 + 6 = 70

P8v8 document identity remains independently frozen and audited even though
the two active-document command rows now bind P8v9.

The preparation attempt plan remains exactly 54 rows. Reusing the unconsumed
v5 runtime paths changes no attempt row count. A successful first-attempt
receipt therefore contains exactly:

    70 authority + 54 attempt = 124 rows

The 70 authority rows precede all 54 attempt rows. No failure prefix,
duplicate, reordering, omitted row, extra row, or reused P8v8 120-row receipt
is valid.

## 11. Unchanged schemas, science, and environment invariants

The registration schema remains
`action-qbc-v8-open-registration-v1`. The execution contract retains exactly
70 keys. Every incorporated preparation, verification, remote, lifecycle,
process, validator, payload, finalization, emergency, result-owner,
result-document, and administrative-terminal schema name and exact key set
remains unchanged.

The treatment ID, diagnostic ID, comparison semantics, runtime-science
identifiers, 140 rows, twelve scenes, transforms, roles, controls, selectors,
data, tolerances, reasons, fallbacks, call automata, payload limits, resource
budgets, and 2,100/2,400/2,700-second scientific limits remain unchanged. All
five authorization Booleans remain false.

The shared installed-environment contract remains the exact thirteen-key row:

```text
path,type,device,inode,mode,owner_uid,owner_gid,link_count,size_bytes,mtime_ns,ctime_ns,sha256,symlink_target
```

Descriptor-relative no-follow traversal, complete stable symlink `lstat`
tuples, regular-file link count one, exact four symlinks, RECORD closure,
noneditable direct URL, installed-vs-Git package equality, exact final
site-packages origin, claim-before-import, and post-import revalidation remain
mandatory. The two `uv_cache.json` timestamp objects remain independently
bounded canonical objects. No fixture correction may weaken these rules.

## 12. O8v5 publication and runtime sequence

Only after every section-8 gate succeeds may O8v5 be committed as the direct
A15 child of P8v9. Create freeze-v5 locally only at exact O8v5. Atomically push
only the preregistration branch fast-forward P8v9-to-O8v5 and the new
freeze-v5 tag. Both must report exact permitted status.

Then consume the incorporated anonymous query for exactly:

```text
refs/heads/action-qbc-v8-prereg
refs/tags/action-qbc-v8-open-diagnostic-freeze-v5
```

It must return branch then tag exactly once at O8v5 with empty stderr.

After that query, the incorporated v5 bootstrap, preparation, independent
preparation verification, Windows supervisor/verifier, mandatory claimed Linux
lifecycle, finalizer, and result publisher apply unchanged except for P8v9
lineage identities, the 70/54/124 command arithmetic, 250-entry O8v5 tree, and
outcome-dependent 251/252/253-entry R8v5 trees.

A valid remote failure still skips science and publishes administratively. A
verified receipt may reach only the unchanged process-A-then-process-B
scientific sequence, with process B conditional on valid process-A validation.
No failed construction fact grants a scientific start.

## 13. Publication order

The only permitted high-level order is:

1. audit exact P8v8 HEAD, the stopped A15 index, stale registration, cache
   identities, and all absence predicates;
2. stage this document without changing the fifteen entries;
3. create exact commit-only P8v9 and prereg-v9 tag;
4. atomically publish the preregistration branch plus prereg-v9 tag;
5. consume the sole P8v9 branch-plus-tag public query;
6. remove only the exact stale registration, preserving fourteen staged
   additions and both cache files;
7. apply the bounded fourteen-path source correction and stage exact A14;
8. run the sole P8v9 producer and reconstructor and stage exact A15;
9. run pytest with explicit no-cache provider, then Ruff, then strict mypy;
10. commit, tag, audit, and atomically publish exact O8v5;
11. consume the sole anonymous branch-plus-freeze-v5 query;
12. run the incorporated one-shot v5 administrative/runtime sequence; and
13. create and publish exactly one selected R8v5 result.

No later step may run after an earlier failure. No step may be reordered or
backfilled.

## 14. Terminal stop conditions

Stop without repair, retry, substitution, or later action if any of these is
true:

- P8v8 HEAD, tree, tag, document, or R8v4 parent differs;
- any section-2 registration, index, source-manifest, prospective-tree, pytest,
  or cache identity differs before its authorized transition;
- the exact twelve failures cease to be fully accounted for by the retained
  read-only diagnosis as bounded fixture defects without weakening production;
- this recovery document is not P8v9's sole diff from P8v8;
- commit-only P8v9 includes or alters any staged O8 path;
- prereg-v9 exists before sole creation, is annotated, or resolves elsewhere;
- the preregistration branch cannot fast-forward P8v8-to-P8v9;
- the P8v9 push or sole query has unexpected status, ordering, value, stderr,
  or visibility;
- the stale registration fails any exact identity or no-follow removal check;
- either pytest cache file changes or any cache cleanup is attempted;
- any v5 ref, root, or evidence path collides before sole use;
- the fourteen-path source allowlist, A14/A15 state, mode, or stage drifts;
- the new registration reuses a failed identity or fails reconstruction;
- pytest creates cache state, changes node inventory, skips a failed node, or
  does not finish at exact 633 passed/30 skipped/zero failed;
- Ruff or strict mypy fails;
- the argv partition is not exact 15/3, the environment argv hash is not
  `a815872b8bc76c3b8118e47ddac9e0e36b97820181a81ae28cc1bcddcc9a642c`,
  or the execution contract is not exactly 70 keys;
- authority/attempt arithmetic is not exact 70/54/124;
- P8v9/O8v5/R8v5 ancestry, entry count, tag, or diff differs;
- any schema, science, dependency version/order, installed-environment rule,
  or authorization Boolean changes outside this amendment; or
- any unlisted mutation, query, network action, protocol action, evidence
  action, or scientific action is proposed.

Such a stop requires a later explicit preregistration amendment. It does not
authorize a retry under P8v8 or P8v9.

## 15. Scientific interpretation

This recovery changes no scientific hypothesis, treatment, observation,
analysis, or claim. This execution ran no registered scientific child and
acquired no scientific-start claim. The combined pytest process did import the
project audit modules during collection as section 3.1 records; that
administrative test import was not a protocol runtime or scientific start.
P8v9 repairs only combined-pytest module isolation, exact modern environment
fixtures, ambient uv test isolation, cache-free construction testing, and
administrative lineage.

Any eventual A/B payloads remain two deterministic observations of the same
unchanged treatment. A successful administrative recovery is not evidence for
a positive mechanism claim.
