# Action-QBC v8 P8v5 public-visibility recovery preregistration

Correction freeze: 18 August 2026 (Australia/Sydney)

Status: prospective preregistration-only administrative recovery. One O8v1
publication push and one anonymous O8v1 read-only verification command existed
before this document. That anonymous command failed before bootstrap. No v8
execution root, authority bootstrap, preparation invocation, preparation
receipt, preparation-verification receipt, Windows lifecycle claim, execution-
phase remote-verification artifact, arm receipt, scientific start, payload,
finalization bundle, R8 object, result ref, or v8 scientific observation existed
when this document was written.

## 1. Authority, reset ancestry, and immutable identities

This document corrects and otherwise incorporates the complete protocol through:

    docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification_v4_correction.md

The binding P8v4 commit is:

    e0bff9ffc185196cafa938c8f7c9a7186366258b

Its immutable lightweight tag is:

    prereg-action-qbc-v8-open-bounded-remote-verification-v4

The first implementation freeze, O8v1, is the direct child of P8v4 at:

    7685fbdccd41702216b3a3f06d2a0ac699aca7ec

Its historical branch and immutable lightweight tag are:

    action-qbc-v8-prereg
    action-qbc-v8-open-diagnostic-freeze-v1

Both refs resolved to that exact commit after the successful atomic publication
described in section 2. O8v1 and its tag remain immutable administrative history.
The freeze-v1 tag must remain at O8v1 permanently. No operator may move, replace,
delete, force-update, execute, bootstrap, or anonymously reverify O8v1.

P8v5 is the direct child of O8v1. Its exact diff deletes all fifteen paths that
O8v1 added and adds only this new recovery document:

    docs/experiment_amendment_2026-08-18_action_qbc_v8_open_bounded_remote_verification_v5_public_visibility_recovery.md

The fifteen deleted paths are exactly the fourteen non-registration paths and
registration path listed in section 6. P8v5 modifies, deletes, or renames no
other path. Consequently the P8v5 tree is byte-for-byte and mode-for-mode the
P8v4 tree plus this one recovery document. No O8 implementation or registration
path exists in the P8v5 tree.

Its immutable lightweight tag is:

    prereg-action-qbc-v8-open-bounded-remote-verification-v5

The existing lineage branch remains:

    action-qbc-v8-prereg

P8v5_COMMIT, P8v5_DOCUMENT_GIT_BLOB_SHA1, P8v5_DOCUMENT_SHA256, and
P8v5_DOCUMENT_BYTE_COUNT mean the identities obtained from the committed bytes
of this path after P8v5 exists. They are identities, not operator choices.

The replacement implementation freeze is O8v2. O8v2 must be the direct child of
P8v5 and add exactly the fifteen paths in section 6. It may modify, delete, or
rename no path present at P8v5. Its new immutable lightweight tag is:

    action-qbc-v8-open-diagnostic-freeze-v2

The result branch retains its incorporated unversioned alias:

    action-qbc-v8-open-diagnostic-result

The new immutable lightweight result tag is:

    action-qbc-v8-open-diagnostic-result-v2

The old result tag remains reserved to the failed O8v1 lineage and must remain
absent:

    action-qbc-v8-open-diagnostic-result-v1

No v1 tag is moved, repointed, deleted, or reused. The branch advances only by
the two registered non-force transitions in section 7. The linear lineage is:

    R7 -> P8v1 -> P8v2 -> P8v3 -> P8v4 -> O8v1 -> P8v5 -> O8v2 -> R8v2

O8v1 remains reachable in the authority ancestry and by its immutable
freeze-v1 tag. P8v5 resets the tree boundary without deleting or rewriting the
historical O8v1 commit or tag. O8v2 then re-adds the same fifteen path names as
new direct-child additions. R8v2 exists only if the incorporated one-shot
lifecycle reaches its registered result publication boundary.

## 2. Complete failed-O8v1 disclosure

O8v1 construction, frozen gates, commit creation, lightweight tagging, and the
one registered non-force atomic push completed. The push placed both:

    refs/heads/action-qbc-v8-prereg
    refs/tags/action-qbc-v8-open-diagnostic-freeze-v1

at:

    7685fbdccd41702216b3a3f06d2a0ac699aca7ec

After that push, the exact runbook credential-disabled check was invoked once
from the registered neutral WSL cwd and empty environment:

    ["C:\\Windows\\System32\\wsl.exe","-d","Ubuntu","--cd","D:\\kaggle competitions","--","/usr/bin/env","-i","GIT_CONFIG_COUNT=0","GIT_CONFIG_GLOBAL=/dev/null","GIT_CONFIG_NOSYSTEM=1","GIT_NO_REPLACE_OBJECTS=1","GIT_TERMINAL_PROMPT=0","HOME=/home/bansarinejad","LANG=C","LC_ALL=C","PATH=/usr/local/bin:/usr/bin:/bin","XDG_CONFIG_HOME=/nonexistent","/usr/bin/git","--no-replace-objects","-c","credential.interactive=never","-c","core.askPass=","-c","credential.helper=","ls-remote","--refs","https://github.com/bansarinejad/arc3-crosslevel-voi.git","refs/heads/action-qbc-v8-prereg","refs/tags/action-qbc-v8-open-diagnostic-freeze-v1"]

That sole invocation had these exact observed outcomes:

    Git exit code:        128
    stdout byte count:    0
    stdout SHA-256:       e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    stderr byte count:    83
    stderr encoding:      ASCII
    stderr final LF:      present
    stderr SHA-256:       2e554a39e2bb4414b5e2c3f5a90ebc87b405b5b8231d692704ec6df4580e8f60
    stderr text:          fatal: could not read Username for 'https://github.com': terminal prompts disabled\n

The repository visibility was PRIVATE. The literal HTTPS URL therefore required
authentication and could not satisfy the required anonymous two-ref read. No
authentication token, password, credential helper, askpass program, or other
secret was supplied to that command. It accepted no remote ref record.

The invocation consumed O8v1's single-use anonymous check. Making the repository
public cannot make that historical invocation pass and cannot authorize a second
O8v1 check. O8v1 stopped before bootstrap exactly as required by its frozen
runbook.

No authority bootstrap command, execution root, preparation command, independent
preparation verification, Windows supervisor, execution-phase remote verifier,
Linux lifecycle driver, scientific runner, payload validator, finalizer, result
publisher, or result transfer command was invoked for O8v1. No private scene,
extension scene, scientific module, scientific payload, or v8 result was
observed. This recovery is based only on the disclosed administrative
publication failure.

## 3. Scope and claim boundary

This correction authorizes one prospective replacement implementation freeze and
one narrowly placed repository-visibility transition. It does not retroactively
repair O8v1.

The treatment ID, diagnostic ID, comparison semantics, all 140 scientific rows,
all twelve public scenes, every transform, role, control, selector, datum,
tolerance, reason, fallback, scientific resource counter, analysis rule,
dependency, scientific function body, payload field, payload limit, and the
2,100/2,400/2,700-second scientific limits remain exactly as incorporated. A and
B remain two deterministic observations of the same unchanged treatment.

No scientific or private outcome was available for choosing this recovery. The
only new fact is that an anonymously unreadable PRIVATE repository cannot pass a
check explicitly defined against a public HTTPS URL.

All five authorization Booleans remain false. This document authorizes no
lockbox, sealed evaluation, gameplay, leaderboard submission, development
matrix, model change, positive mechanism claim, or third scientific start.

## 4. Schema, path, and identifier invariance

The registration schema remains:

    action-qbc-v8-open-registration-v1

All incorporated receipt, bundle, claim, payload, and result-document schema
names and exact key sets remain unchanged, including:

    action-qbc-v8-preparation-receipt-v2
    action-qbc-v8-preparation-verification-receipt-v1
    action-qbc-v8-remote-tag-verification-claim-v1
    action-qbc-v8-remote-tag-verifier-start-claim-v1
    action-qbc-v8-remote-tag-verification-receipt-v1
    action-qbc-v8-remote-tag-verification-supervisor-receipt-v1
    action-qbc-v8-arm-receipt-v2
    action-qbc-v8-open-diagnostic-payload-v1
    action-qbc-v8-open-diagnostic-receipt-v2
    action-qbc-v8-open-diagnostic-administrative-terminal-v2
    action-qbc-v8-emergency-result-bundle-v2

The treatment, diagnostic, runtime, platform, comparison, transform, resource,
and scientific-contract identifiers remain unchanged. The execution-root,
authority, process, output, preparation, verification, Windows claim/receipt,
arm, lifecycle, finalization-bundle, emergency-bundle, and result-work paths
remain unchanged. Their absence before O8v2 bootstrap is mandatory.

The following administrative values change prospectively:

    preregistration tag:       prereg-action-qbc-v8-open-bounded-remote-verification-v5
    preregistration commit:    P8v5_COMMIT
    preregistration document:  docs/experiment_amendment_2026-08-18_action_qbc_v8_open_bounded_remote_verification_v5_public_visibility_recovery.md
    document Git blob:         P8v5_DOCUMENT_GIT_BLOB_SHA1
    document SHA-256:          P8v5_DOCUMENT_SHA256
    document byte count:       P8v5_DOCUMENT_BYTE_COUNT
    open-freeze branch:        action-qbc-v8-prereg
    open-freeze tag:           action-qbc-v8-open-diagnostic-freeze-v2
    result branch:             action-qbc-v8-open-diagnostic-result
    result tag:                action-qbc-v8-open-diagnostic-result-v2

The registration content SHA-256, preregistration-tree manifest, O8v2 added-file
manifest, argv hashes, and source identities are recomputed from the replacement
bytes. Changed hash values are identities derived from those bytes, not schema
changes. The existing branch name and exact Windows local-config mapping remain
unchanged; no v2 branch key or config mutation is introduced.

The exact execution-contract key set remains the incorporated P8v4 key set. No
visibility credential, GitHub token, visibility receipt, recovery counter,
operator-selected stage, or new scientific input is added to the registration.
The pre-bootstrap transition is bound directly by this document and the O8v2
runbook.

The existing local execution paths may be reused only because the complete
incorporated absence gate proves that O8v1 never created them. Any existing,
unsafe, nonempty, or ambiguous path stops O8v2 before bootstrap; it is never
cleaned, adopted, or repaired.

## 5. Deterministic administrative substitutions

All executable O8v2 identities use P8v5, its v5 preregistration tag, this document
path and identities, the existing lineage branch, the freeze-v2 tag, the
unchanged result branch alias, and the result-v2 tag.

The deterministic v7-to-v8 scientific source transformation remains unchanged
except for administrative identity outputs. In particular, the generated v8
audit module must still reverse exactly to the same frozen v7 audit module after
reversing the declared administrative substitutions. Scientific code, data, row
inventory, scene inventory, transforms, selectors, controls, and resource
semantics may not change.

O8v1 implementation bytes may be used only as an administrative source reference
for constructing the replacement files. No O8v1 result exists to inspect or
reuse. Every difference from O8v1 must be required by:

1. the P8v5 commit/tag/document identities;
2. the freeze and result ref identities;
3. the exact linear reset ancestry and reconstruction checks;
4. the one-shot visibility and anonymous-verification sequence;
5. the resulting registration, manifest, argv, config, test, and documentation
   identities; or
6. a necessary implementation test for those administrative changes.

Any other executable, scientific, schema, path, claim, timing, retry, or evidence
change is forbidden and requires another preregistration.

## 6. Exact O8v2 tree boundary

P8v5 deletes all and only these fourteen O8v1 non-registration paths:

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

P8v5 also deletes the O8v1 registration path:

    artifacts/action_qbc_v8_open_registration.json

Together with the sole added recovery document, those deletions are P8v5's
complete diff from O8v1. The committed P8v5 tree must equal the P8v4 tree plus
the recovery document by path, mode, Git blob, raw SHA-256, and byte count.

After P8v5 is committed, tagged, and published, O8v2 re-adds all and only the
fourteen non-registration paths above. After those fourteen paths alone are
staged, the producer is invoked exactly once with:

    ["uv","run","--frozen","--extra","dev","python3","-I","-B","scripts/build_action_qbc_v8_open_registration.py","--repository-root",".","--preregistration-tag","prereg-action-qbc-v8-open-bounded-remote-verification-v5","--output","artifacts/action_qbc_v8_open_registration.json"]

It generates the sole fifteenth addition:

    artifacts/action_qbc_v8_open_registration.json

The incorporated exact reconstruction, index, manifest, pytest, Ruff, strict-
mypy, source-transformation, raw-byte, tool, environment, and no-science gates
remain binding. Each one-shot producer, reconstructor, and frozen gate invocation
retains the incorporated no-retry semantics. A failed or partial construction is
not O8v2 and requires another preregistration.

Only after every gate passes may all and only the fifteen additions be committed
as the direct child of P8v5 and tagged:

    action-qbc-v8-open-diagnostic-freeze-v2

No O8v1 source or registration path remains in the P8v5 tree. O8v1 remains an
immutable ancestor whose bytes may be read only to construct and audit the
prospective O8v2 additions. This exact delete-then-re-add reset preserves both
the historical failure and the P8v5 -> O8v2 implementation boundary.

## 7. Existing preregistration branch reset and publication

The existing branch has exactly two additional allowed fast-forward states after
O8v1:

1. it advances from O8v1 to P8v5 together with the immutable v5
   preregistration tag; and
2. it is advanced exactly once from P8v5 to its direct child O8v2 as part of the
   atomic O8v2 publication.

After the O8v2 atomic publication it is immutable at O8v2. It is never forced,
deleted, rewound, redirected, or reused for another attempt. The freeze-v1 tag
continues to resolve O8v1 before and after both branch advances.

While the repository remains PRIVATE, publish P8v5 with one non-force atomic
Windows Git invocation:

    ["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-C","D:\\kaggle competitions\\arc3-crosslevel-voi","push","--atomic","origin","refs/heads/action-qbc-v8-prereg:refs/heads/action-qbc-v8-prereg","refs/tags/prereg-action-qbc-v8-open-bounded-remote-verification-v5:refs/tags/prereg-action-qbc-v8-open-bounded-remote-verification-v5"]

That preregistration publication is not an anonymous connectivity rehearsal.
Failure stops before O8v2 construction. It may not be retried under this
preregistration.

After O8v2 exists and every post-commit local audit passes, publish the existing
branch's second fast-forward and the freeze tag with one non-force atomic Windows
Git invocation while the repository is still PRIVATE:

    ["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-C","D:\\kaggle competitions\\arc3-crosslevel-voi","push","--atomic","origin","refs/heads/action-qbc-v8-prereg:refs/heads/action-qbc-v8-prereg","refs/tags/action-qbc-v8-open-diagnostic-freeze-v2:refs/tags/action-qbc-v8-open-diagnostic-freeze-v2"]

Failure, non-atomic behavior, an unexpected ref, or uncertainty stops the
replacement before visibility transition. No push is retried and no ref other
than the two registered branch fast-forwards is moved under this
preregistration.

## 8. Sole PRIVATE-to-PUBLIC transition

The repository must remain PRIVATE through the successful O8v2 atomic push.
Thereafter, and before any anonymous O8v2 verification or bootstrap, the
interactive repository owner invokes exactly once the following GitHub CLI
executable:

    path:        C:\Program Files\GitHub CLI\gh.exe
    version:     2.96.0
    byte count:  41504056
    SHA-256:     cd79f16203f1fbe56937c4c96e2b6eadd10549418dcb241d91576ac77af0ac8b

The exact argv is:

    ["C:\\Program Files\\GitHub CLI\\gh.exe","repo","edit","bansarinejad/arc3-crosslevel-voi","--visibility","public","--accept-visibility-change-consequences"]

This is the sole authorized repository-visibility mutation. It is an external
owner-authorized administrative action using the existing interactive GitHub
authentication context. No credential or environment value is embedded in a
registration, receipt, command transcript, source file, or result.

The visibility invocation occurs only after the O8v2 atomic push returns success.
No visibility query, API rehearsal, browser refresh used as a protocol check,
authenticated ref query, anonymous ref query, or other connectivity probe may
run between that push and this invocation. The GitHub CLI call's own necessary
API interaction is the transition, not a separate query.

The invocation counts whether it succeeds or fails. A nonzero exit, launch
failure, timeout, ambiguous return, uncertain repository state, already-PUBLIC
state that prevents the registered PRIVATE-to-PUBLIC transition, or any other
unexpected condition stops O8v2 before anonymous verification and bootstrap.
The command is never repeated, replaced by a browser action, or followed by a
repair transition under this preregistration.

After a normal successful return, repository visibility must remain PUBLIC
without an intervening PUBLIC-to-PRIVATE or other visibility transition through
the O8v2 anonymous check, authority bootstrap, preparation, Windows verification,
Linux lifecycle, R8v2 transfer, remote result publication, and final remote
result-ref verification. A visibility change during that interval is terminal
administrative failure and never authorizes a retry.

The visibility command does not prove its own historical effect. The immediately
following credential-disabled literal-HTTPS read is the sole registered
anonymous evidence that the two requested O8v2 refs are publicly readable.

## 9. Sole O8v2 anonymous verification

After the successful visibility invocation, the next protocol network action is
exactly one credential-disabled read from neutral WSL cwd
/mnt/d/kaggle competitions with an empty environment:

    ["C:\\Windows\\System32\\wsl.exe","-d","Ubuntu","--cd","D:\\kaggle competitions","--","/usr/bin/env","-i","GIT_CONFIG_COUNT=0","GIT_CONFIG_GLOBAL=/dev/null","GIT_CONFIG_NOSYSTEM=1","GIT_NO_REPLACE_OBJECTS=1","GIT_TERMINAL_PROMPT=0","HOME=/home/bansarinejad","LANG=C","LC_ALL=C","PATH=/usr/local/bin:/usr/bin:/bin","XDG_CONFIG_HOME=/nonexistent","/usr/bin/git","--no-replace-objects","-c","credential.interactive=never","-c","core.askPass=","-c","credential.helper=","ls-remote","--refs","https://github.com/bansarinejad/arc3-crosslevel-voi.git","refs/heads/action-qbc-v8-prereg","refs/tags/action-qbc-v8-open-diagnostic-freeze-v2"]

The command is invoked exactly once. Its stdout is parsed as records rather than
presentation order. Success requires exactly these two records, each exactly
once, both at the recorded lowercase 40-hex O8v2 commit:

    refs/heads/action-qbc-v8-prereg
    refs/tags/action-qbc-v8-open-diagnostic-freeze-v2

Stderr must be empty. A peeled, duplicate, missing, additional, malformed,
uppercase, wrong-hash, or authenticated result is rejected.

Any spawn failure, nonzero exit, timeout, empty or unexpected output, nonempty
stderr, wrong ref state, loss of PUBLIC visibility, or uncertain observation
stops O8v2 before bootstrap. The check is never retried. No second visibility
transition, credentials, alternate URL, helper, browser query, API query, SSH
query, or later anonymous O8v2 pre-bootstrap check is allowed. A later attempt
requires another prospective preregistration and fresh ref identities.

Only the exact successful two-ref result authorizes the incorporated read-only
host preflight and one-shot authority bootstrap for O8v2.

## 10. Downstream execution and result publication

After successful anonymous verification, the incorporated bootstrap,
preparation, independent gate, Windows supervisor, Linux lifecycle, finalizer,
publisher, transfer, and result-verification protocol applies unchanged except
for the P8v5, O8v2, and R8v2 administrative identities.

The authority bootstrap clones:

    action-qbc-v8-open-diagnostic-freeze-v2

and checks out the recorded O8v2 commit. It never clones or executes freeze-v1.
The incorporated absence, no-cleanup, no-retry, claim, timing, process ownership,
evidence, and failure-classification rules remain unchanged.

The execution-phase Windows verifier retains its incorporated bounded maximum of
three internal attempts. Those attempts are part of the later one-shot claimed
lifecycle and are not retries of the sole pre-bootstrap anonymous O8v2 check.
They introduce no exception to sections 8 or 9.

If an R8v2 result is validly created, its local and remote identities use only:

    refs/heads/action-qbc-v8-open-diagnostic-result
    refs/tags/action-qbc-v8-open-diagnostic-result-v2

The incorporated immutable-result transaction, publication-only recovery, local
transfer, two result pushes, and final two-ref check remain otherwise unchanged.
No v1 result ref may be created or accepted.

## 11. Required implementation tests and gates

Before O8v2, all incorporated offline tests and exact frozen gates remain
mandatory. Additional tests must prove:

- O8v1 is the exact-fifteen-addition direct child of P8v4; P8v5 is O8v1's direct
  child with exactly fifteen deletions plus the one recovery-document addition;
  its tree equals P8v4 plus that document; and O8v2 is the exact-fifteen-
  addition direct child of P8v5;
- the freeze-v1 tag remains exactly at O8v1 and is never accepted as O8v2 or
  moved by any publication argv;
- the existing branch has only the O8v1 -> P8v5 -> O8v2 non-force
  fast-forwards, both new tags are lightweight and immutable, and every
  force/delete/rewind/ref-reuse variant fails;
- the complete failed-O8v1 telemetry in section 2 is represented exactly and
  cannot be described as success, an unconsumed check, a scientific result, or
  authority to bootstrap O8v1;
- the registration retains its exact v1 schema and all incorporated scientific,
  receipt, claim, path, and timing identities except the declared administrative
  lineage/ref substitutions;
- the v7-to-v8 source reversal and complete scientific contract are identical,
  and any nonadministrative O8v1-to-O8v2 source change fails;
- the P8v5 and O8v2 producer, reconstruction, runbook, Windows config, source-
  manifest, argv-hash, and result-ref identities are complete and exact;
- the one GitHub CLI path, version, byte count, SHA-256, and argv are accepted
  only after successful O8v2 atomic publication and before anonymous checking;
- zero, duplicate, reordered, replaced, failed, uncertain, already-PUBLIC, or
  reverse visibility transitions forbid anonymous verification and bootstrap;
- no separate visibility, connectivity, API, browser, authenticated-ref, SSH, or
  anonymous-ref probe is permitted before the sole O8v2 check;
- the exact anonymous argv accepts only the two v2 refs once at O8v2 with empty
  stderr, and every failure consumes the check and authorizes no retry;
- PUBLIC visibility is required continuously through final R8v2 remote
  verification, while tests themselves make no live network or visibility
  mutation;
- bootstrap and every later executable path accept freeze-v2, the unchanged
  result branch alias, and the result-v2 tag, while rejecting
  freeze-v1/result-v1 without changing any scientific behavior; and
- all source/help/static tests remain offline, create no real execution root,
  mutate no repository visibility, make no remote request, import no scientific
  module on a pre-start failure, and write no real result path.

The registration builder runs only after every other O8v2 addition is staged.
Registration reconstruction must be byte-identical. The full frozen pytest,
Ruff, and strict-mypy gates must pass once in the incorporated explicit Ubuntu
environment. O8v2 may then be committed, lightweight-tagged, privately pushed,
made public once, and anonymously checked once in exactly that order.

## 12. Claims that remain prohibited

This recovery is a minimal-honest administrative response to a private-
visibility publication error. It is not evidence about the Action-QBC mechanism,
model quality, scientific rows, public scenes, unseen generalization, causality,
calibrated Bayesian inference, runtime readiness, security, or Kaggle
performance.

The visibility transition and anonymous check are bounded consistency controls
under the incorporated threat model. They are not cryptographic attestation,
tamper-proofing, proof against a malicious same-authority actor, or proof of
historical execution. A failed or incomplete replacement remains publishable
only with its exact administrative or scientific meaning and cannot be tuned
away.
