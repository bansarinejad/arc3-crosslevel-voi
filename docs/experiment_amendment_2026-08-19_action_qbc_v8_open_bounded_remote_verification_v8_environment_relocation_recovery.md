# Action-QBC v8 P8v8 environment-relocation recovery preregistration

Recovery freeze: 19 August 2026 (Australia/Sydney)

Status: prospective preregistration-only administrative recovery. O8v4 was
constructed, frozen, published to the already-PUBLIC repository, and verified
by its sole credential-disabled anonymous two-ref query. Its one-shot bootstrap,
preparation, independent preparation verification, Windows remote verification,
Linux lifecycle, finalization, result construction, transfer, publication, and
final public verification all reached their registered terminal boundaries.
Remote verification succeeded. Process A then acquired its scientific-start
claim and returned exit code 3 before producing a payload; process B did not
start. The valid administrative-terminal result R8v4 records that outcome.

Inspection of the preserved final process environments establishes a
deterministic sufficient administrative cause: the default editable project
installation in each staging virtual environment retained an absolute `.pth`
target under `.prepare-attempt-1`, but preparation atomically renamed the parent
to `processes`. No installed `arc3_voi` package copy remained as an alternative.
The runner's stdout and stderr were deliberately directed to `DEVNULL`, so its
exact exception text was not retained and is not invented here. This amendment
prospectively replaces only that causal environment-build and admission defect,
with the required fresh lineage, namespaces, identities, and result boundary.

## 1. Authority, incorporation, and immutable graph

This document corrects and otherwise incorporates the complete protocol through:

    docs/experiment_amendment_2026-08-18_action_qbc_v8_open_bounded_remote_verification_v7_consumed_lifecycle_recovery.md

Every P8v7 scientific, schema, timing, resource, evidence-mode, snapshot-order,
publisher-wrapper, claim, no-cleanup, no-retry, public-state, and result-
publication requirement remains binding unless this document expressly
replaces an administrative lineage, ref, path, environment-build argv,
installed-package validation, command-plan length, or derived identity.

P8v7 is:

    commit:              15059c482d9e463f01cb31fdfd33c96d1f60db0a
    tree:                96469ca9ee018cd32f99955df1ded57af12a8abc
    tag:                 prereg-action-qbc-v8-open-bounded-remote-verification-v7
    document:            docs/experiment_amendment_2026-08-18_action_qbc_v8_open_bounded_remote_verification_v7_consumed_lifecycle_recovery.md
    document Git blob:   c0cda2417bd98a42b76e8e1bbdee4cec01dd68f9
    document SHA-256:    f729904367dd7a2664ecd3fdfe4893841326668fbe892b3b733926ad7840745d
    document byte count: 37552

O8v4 is P8v7's direct exact-fifteen-addition child:

    commit: a2c4b93610a2b69e886f24b5626cc8a6adb9b196
    tree:   ae2d8036451807ad5991828463067b09cefc26d0
    tag:    action-qbc-v8-open-diagnostic-freeze-v4
    recursive tree entries: 248

R8v4 is O8v4's direct exact-two-addition child:

    commit: b1d4c68891f0ecee05363bafe8e12549d9c8430b
    tree:   630443b64347d59671a8d6c3fb4f8abaffa1ac5b
    tag:    action-qbc-v8-open-diagnostic-result-v4
    recursive tree entries: 250

The stable branches are:

    action-qbc-v8-prereg
    action-qbc-v8-open-diagnostic-result

At this recovery freeze, the checked-out local preregistration branch and its
remote-tracking ref resolve to O8v4. The local result branch, its remote-tracking
ref, and result-v4 tag resolve to R8v4. Section 8 freezes the non-network
fast-forward that must join those already immutable histories before P8v8 is
constructed. No reset, force, rebase, cherry-pick, replacement ref, or parallel
lineage is permitted.

P8v8 must be R8v4's direct child. Its direct diff deletes exactly the seventeen
O8v4/R8v4 additions listed in section 8 and adds only this document. The net
P8v7-to-P8v8 diff is exactly this one document addition. P8v8's recursive Git
tree inventory contains exactly 234 entries. Its immutable lightweight tag is:

    prereg-action-qbc-v8-open-bounded-remote-verification-v8

P8v8_COMMIT, P8v8_TREE, P8v8_DOCUMENT_GIT_BLOB_SHA1,
P8v8_DOCUMENT_SHA256, and P8v8_DOCUMENT_BYTE_COUNT mean identities derived
from these exact committed bytes after P8v8 exists. They are not operator
choices and remain symbolic in this document.

O8v5 must be P8v8's direct exact-fifteen-addition child. Its recursive tree
inventory contains exactly 249 entries. Its immutable lightweight tag is:

    action-qbc-v8-open-diagnostic-freeze-v5

R8v5 exists only if the O8v5 lifecycle reaches its registered result boundary.
It must be O8v5's direct child under exactly one incorporated outcome-dependent
result path set and have this immutable lightweight tag:

    action-qbc-v8-open-diagnostic-result-v5

The exact permitted direct delta and recursive tree count depend only on the
selected valid bundle:

| Selected bundle | Direct delta | Tree entries | Exact added paths |
| --- | ---: | ---: | --- |
| `scientific_result` | A3 | 252 | scientific JSON, scientific receipt JSON, result document |
| ordinary `administrative_terminal` | A2 | 251 | administrative-terminal JSON, result document |
| receipt-finalization/finalizer-process doc-only override | A1 | 250 | result document only |

The exact paths for all three sets are frozen in section 8. No execution may
choose a set independently of its selected canonical bundle.

The prospective prereg-v8, freeze-v5, and result-v5 tags must each be absent
locally before that tag's sole local creation. No authorized pre-push network
query observes their remote/public absence. Instead, each sole non-force push
must return the exact new-tag status for its prospective tag; `up to date`, an
already-existing tag, or any other status is a collision and permanent STOP.
Any authorized later public query proves only its requested post-push ref
values, not prior absence; no public query is authorized for prereg-v8 itself.
No existing object is accepted as the prospective tag and no tag is deleted,
replaced, or forced. Result-v5 must remain locally absent until a valid R8v5
bundle and outcome-dependent path set have been selected, constructed, and
validated. The existing preregistration and stable result branch names are the
only reused refs.

The stable result branch must advance from R8v4 to R8v5 by non-force
fast-forward only. Result-v4 and freeze-v4 remain immutable. The absent v8
result-v1, result-v2, and result-v3 refs remain absent and must never be
backfilled.

The binding graph is:

    P8v7 -> O8v4 -> R8v4 -> P8v8 -> O8v5 -> R8v5

The complete incorporated history before P8v7 remains unchanged. O8v4 and R8v4
are consumed historical evidence. Nothing in this amendment repairs, deletes,
chmods, reruns, reclassifies, or rewrites either object or its external
evidence.

## 2. O8v4 construction and public-freeze verification

O8v4 was constructed from P8v7 with exactly the registered fifteen additions.
Its generated registration has:

    path:             artifacts/action_qbc_v8_open_registration.json
    byte count:       210492
    final LF:         absent
    file SHA-256:     49a20edd3848cffabf4a25c2004ba782e591e8f3a6e4bbad8e207fab6e194061
    content SHA-256:  310c90154a12866591bdf522ad5cfd60a27fe11407a548ea9a483c6d2f3bff3d
    Git blob:         a0e6608a498e9d706f47c39e1ebddd30455a96d3
    source manifest:  c8c64a4f9e27d0aa968a8fee783c5be52d8205f57c60077f3c26e2ed5b04d6fe
    scientific rows:  140

The one construction sequence ran in the registered order and only once:

1. stage the fourteen authored non-registration paths: exit 0;
2. run the sole producer: exit 0;
3. stage the generated registration: exit 0;
4. run the sole reconstructor: exit 0;
5. run frozen pytest: exit 0, empty stderr, `607 passed, 30 skipped in
   118.77s (0:01:58)`;
6. run Ruff: exit 0, exact stdout `All checks passed!` plus LF, empty stderr;
7. run strict mypy: exit 0, exact stdout `Success: no issues found in 1 source
   file` plus LF, empty stderr; and
8. complete the incorporated source, tree, index, raw-byte, tool,
   no-science, commit, tag, and post-commit audits.

The one registered non-force atomic branch-plus-freeze-v4 push returned exit 0,
empty stdout, and a 229-byte stderr stream with SHA-256
`91496a89bf4539cdd5df7ecfefe4c30dd9e3dd946a7dee0c418b01dd3f4f1a02`.
It reported the preregistration branch fast-forward and the new freeze-v4 tag.
Empty stdout has SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The next protocol network action was the sole credential-disabled anonymous
freeze-v4 query. It returned exit 0 and empty stderr. Its exact 164-byte ASCII,
LF-terminated stdout had SHA-256
`5c2471b159e9126f69483bc6590a5eb801b0752abef5ee831635349e4b69eb5e`
and contained exactly these records in this order:

    a2c4b93610a2b69e886f24b5626cc8a6adb9b196	refs/heads/action-qbc-v8-prereg
    a2c4b93610a2b69e886f24b5626cc8a6adb9b196	refs/tags/action-qbc-v8-open-diagnostic-freeze-v4

That query is consumed and may never be repeated. It established only the two
public ref values at that observation. The repository was already PUBLIC and no
visibility mutation or visibility query occurred.

## 3. Complete consumed O8v4 lifecycle and R8v4 evidence

O8v4 used this execution root:

    /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4

The registered one-shot bootstrap completed, leaving the owner-controlled
authority clone at detached O8v4. Preparation then completed on its first
permitted internal attempt and atomically promoted its attempt parent:

    source:      /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4/.prepare-attempt-1
    destination: /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4/processes

Its preserved canonical receipt has:

    path:        /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4/preparation-receipt.json
    mode:        0444
    byte count:  96852
    SHA-256:     fb1669786e36a197e07bdabd967f85fe43d3b104db8e285dfeed2d3a7607662f
    status:      prepared
    attempts:    1
    ledger:      108 rows = 54 authority + 54 attempt
    ledger hash: 8deac5c6ffdf89ccd77d1da93ddc9bcedcb3a56996c69aa310a8c1c1cfcc0f26

Its preparation-command-environment SHA-256 is:

    6bd8625e7d3f4f329785adacc96569c2aece8682cfbfb998fed96be17a6c8398

Independent preparation verification completed and preserved:

    path:         /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4/preparation-verification.json
    mode:         0600
    byte count:   2970
    file SHA-256: 8148d249bbd277898bcf1f6bc02358b0770a59729aa8c3b0834d6fd3b83899d4
    content hash: 6e87c87e2f412520ee916fd8e9b4ad4209fd17dfbab2ec18d00a86597e7a801e
    status:       verified

Both final process checkouts were clean detached O8v4 trees. Both recorded
Python 3.12.13, uv 0.11.28, the same Python executable SHA-256
`9544d2a29138833e6177d45dbc57468d37710b5080c901fbb579d53f251cdd6f`,
and the same raw and repository tree identities. Their environment inventories
and virtual-environment materializations differed because their editable `.pth`
files contained different absolute process labels:

| Process | Environment inventory SHA-256 | Venv materialization SHA-256 |
| --- | --- | --- |
| A | `ccc5ceb961da27968066d3435e92848c5923d6c57dc2c6176b277789f090b799` | `43e37cb49fb30cc5815b417b02e229804ad0816ae18f330bcdf4c38b924fe694` |
| B | `2f1f4386877ae9357c3baadd7fee6fc2421b3b33dff65f250f5212bab826ed49` | `4b7d9f5fafb183436ceee33b0acb3ce1b4bbb25a5452781427ea2aab2d572933` |

The sole Windows supervisor completed successfully and the remote verifier made
one admitted remote attempt. The four fresh Windows artifacts were copied
byte-identically into the Linux root as mode-`0444` evidence:

| Artifact | Bytes | SHA-256 | Terminal fact |
| --- | ---: | --- | --- |
| lifecycle claim | 804 | `40586b134f3716acf32ff13ee1a54dd4941e747d04be6560491af799448d845f` | claim exists |
| verifier-start claim | 488 | `6b9ff413c7e8e76b6ae02c5216007a11fb6085bbfe0cc629ce8aa1ada1ebf13e` | verifier started |
| remote receipt | 2927 | `ed820deac98fd3c33e131f1ea60789ed9f9a131cc1e83b8ab36d25d4317df373` | `verified`, one attempt, selected attempt 1 |
| supervisor receipt | 1092 | `ec4c1c09f8c9bc944ebe9442bc0646ee8712239bff3013bac628324e4fd759b5` | `completed`, `verifier_completed`, verifier exit 0 |

The selected remote attempt returned exit 0 and empty stderr. Its 91-byte
stdout advertised only freeze-v4 at O8v4 and had SHA-256
`8a131c2904e9664254c4447132639f647b5afd7f3df7ec1ba15a45fd8d3c593f`.
This is valid bounded remote evidence, not a scientific result.

The Linux lifecycle then preserved:

| Linux evidence | Mode | Bytes | SHA-256 | Fact |
| --- | ---: | ---: | --- | --- |
| arm receipt | `0444` | 1082 | `4eddd45b31ad59cc9ce2a9c4adbe1ca7e6529ecf7d694aa7da8166cd2f8664cf` | status `armed` |
| lifecycle driver claim | `0600` | 484 | `cdf4092a0843a2f23083b8b56ee32e630dc156c9136cee42a39305f2ef770724` | exact driver argv hash |
| lifecycle ledger | `0600` | 1343 | `56ef3de69391329600bf571d6b8c8db464805987d300a62785957b2a4d1d8639` | stage `process_a_nonzero` |
| process A start claim | `0600` | 771 | `afafbafd800289124c3ca6087b120d7e3350a094e67c8de34c7b6b9dcc8fcbbf` | start claimed before import |
| finalization bundle | `0600` | 149694 | `d1a95eadf1930652e0b337bcdd4d07a66b6140463ee20ed79a1b449d91937f59` | administrative terminal |
| result-Git owner claim | `0600` | 558 | `774dfefd606399f248d1ff7e53677cc2a32a51c03c784c93c867fc83e9cfab04` | R8 owner established |

The lifecycle sequence is exactly `arm_returned`, then
`process_a_runner_returned`. Arm returned exit 0. Process A's runner returned
exit 3. Its output path remained absent, and its payload, validator claim,
validation receipt, and payload hash are null. Process B has no start claim,
runner exit, validator claim, validation receipt, or payload. Payload-byte
identity is therefore null. There is no emergency bundle; the normal
finalization bundle validly records the terminal administrative state.

The finalization bundle has content SHA-256
`729b768559b29ebb1661be7135c27cf07cb93d540f4688bfa89eb4a970052c6b`,
disposition `administrative_terminal`, stage and underlying stage
`process_a_nonzero`, and all five authorization Booleans false. It contains
exactly these two result files:

| Result path | Bytes | SHA-256 | Git blob |
| --- | ---: | --- | --- |
| `artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json` | 111030 | `34660057fecd0d4e280a5a9c0a752b084fe46d4247049228ce14032589db8135` | `fc0bee0dba6f94c91c7286fa2076f495e8a528ef` |
| `docs/action_qbc_v8_open_diagnostic_result.md` | 421 | `c7b0764bf3cef527fd3682bbb3fe3b7a3a62e1437b381e3e3e4fab1c0dd1be9f` | `57f027a3699e5eb1f0a5cdd729cd4f82e0934795` |

Those bytes form R8v4, with O8v4 as its sole parent and exact A2 direct diff.
The authority held only the result-v4 lightweight tag; its result branch was
absent. After the incorporated transfer and validation boundary, the original
repository acquired the stable result branch and result-v4 tag at R8v4.

The final sole public result query returned exit 0 and empty stderr. Its exact
180-byte ASCII, LF-terminated stdout had SHA-256
`6f1d966544dd4c7b811ec8dfc4925d750427fabc7a8f0445077338a96cd72c87`
and contained exactly these records in this order:

    b1d4c68891f0ecee05363bafe8e12549d9c8430b	refs/heads/action-qbc-v8-open-diagnostic-result
    b1d4c68891f0ecee05363bafe8e12549d9c8430b	refs/tags/action-qbc-v8-open-diagnostic-result-v4

Its exact argv was:

    ["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-c","credential.interactive=never","ls-remote","--refs","origin","refs/heads/action-qbc-v8-open-diagnostic-result","refs/tags/action-qbc-v8-open-diagnostic-result-v4"]

The O8v4 lifecycle and every O8v4/R8v4 query, claim, preparation, process-A
start, finalization, result-construction, transfer, push, and verification
boundary are consumed. No one may rerun or reuse them.

## 4. Deterministic sufficient environment-relocation defect

O8v4 registered this exact nine-token environment-build argv:

    ["/usr/bin/env","UV_OFFLINE=1","/usr/local/bin/uv","sync","--python","3.12.13","--frozen","--no-dev","--offline"]

Its canonical argv SHA-256 is:

    cc33e44024e65209fbac210d127116e18f73b35a9be8750ea3bd0d7fd581a6b4

With the local project present, that default `uv sync` built each environment as
an editable project installation inside the attempt root. Preparation then
atomically renamed the complete parent `.prepare-attempt-1` to `processes`.
The virtual environments themselves survived byte-for-byte, but their absolute
editable targets did not relocate.

The preserved final process-A file is:

    path: /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4/processes/process-a/.venv/lib/python3.12/site-packages/_editable_impl_arc3_crosslevel_voi.pth
    type/owner: no-follow regular file, uid/gid 1000
    mode: 0644
    link count: 2
    size: 83 bytes
    final LF: absent
    SHA-256: 07ec6a3b6a089a879955ed59dc3eba9938886ae425dcddf5458675abc1052643
    exact ASCII content: /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4/.prepare-attempt-1/process-a/src

The preserved final process-B file is:

    path: /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4/processes/process-b/.venv/lib/python3.12/site-packages/_editable_impl_arc3_crosslevel_voi.pth
    type/owner: no-follow regular file, uid/gid 1000
    mode: 0644
    link count: 2
    size: 83 bytes
    final LF: absent
    SHA-256: 73714dc1f5d4af922ac565f8cd416efea30fb8b5fbbdd3addbb4b2a58aa74b33
    exact ASCII content: /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4/.prepare-attempt-1/process-b/src

Both referenced staging paths are absent after the registered parent promotion.
Each final site-packages directory contains the project `.dist-info` metadata
and the editable `.pth`, but no plain installed `arc3_voi` package directory.
The registered isolated `-I -B` runner therefore has neither a surviving
editable source target nor an installed package copy from which to resolve the
scientific module.

The default uv link mode also left cache/shared hard links. In both processes,
the project `METADATA` and editable `.pth` have link count 2; representative
`numpy/__init__.py` files have link count 6. This is an additional
administrative aliasing weakness, not the scientific cause asserted for exit
3. O8v5 removes it from the complete recursive virtual-environment regular-file
boundary with explicit copy mode and exact link-count checks.

This preserved state is a deterministic sufficient explanation for the
post-claim pre-payload exit. It is not necessary, and is not permissible, to
guess the discarded exception. The lifecycle launched the runner with both
stdout and stderr set to `subprocess.DEVNULL`. The terminal evidence retains
only the process-A claim, exit code 3, absent payload and validator evidence,
and absent process B. It retains no exception class, exception text, traceback,
or raw runner stream. This amendment therefore does not assert a verbatim
`ModuleNotFoundError` or any other unobserved message.

The defect is administrative. It arose before any successful scientific-module
import, evaluation, or payload publication. The process-A start claim is still
a real consumed scientific start under the protocol; its existence must not be
erased or redescribed as no start. Conversely, acquiring the claim is not
evidence that the Action-QBC computation ran.

No O8v4 environment may be modified, rebuilt, relinked, copied, or probed by an
unregistered runner to simulate a recovery. The stale `.pth` files, absent
installed copies, final process roots, and all terminal evidence remain
immutable historical observations.

## 5. O8v5 copied non-editable installation and byte-parity boundary

O8v5 replaces the environment-build argv with exactly these twelve tokens:

    ["/usr/bin/env","UV_OFFLINE=1","/usr/local/bin/uv","sync","--python","3.12.13","--frozen","--no-dev","--offline","--no-editable","--link-mode","copy"]

Its canonical argv SHA-256 is frozen as:

    a815872b8bc76c3b8118e47ddac9e0e36b97820181a81ae28cc1bcddcc9a642c

The registration `dependencies` array retains its exact three-entry order,
names, and versions. Its only value change is the project entry:

    {"editable":true,"name":"arc3-crosslevel-voi","version":"0.1.0"}

becoming:

    {"editable":false,"name":"arc3-crosslevel-voi","version":"0.1.0"}

The NumPy and PyYAML dependency entries remain byte-semantically unchanged.
This Boolean change is an administrative packaging fact, not a dependency,
version, source-code, schema, or scientific-contract change.

The frozen `uv.lock` continues to record the project workspace source exactly
as `source = { editable = "." }`. That is the unchanged lock/workspace source
representation; it does not override the registered `uv sync --no-editable`
materialization mode. Neither `uv.lock`, `pyproject.toml`, an optional extra,
nor any build-backend input may change for this recovery.

No alias, reordered option, omitted offline control, editable fallback,
hard-link mode, automatic link-mode choice, later package repair, or second
environment-build command is accepted. The build runs in each registered
`.prepare-attempt-N/process-{a,b}` root before the one atomic parent promotion.
There is no post-promotion rebuild, reinstall, sync, path rewrite, `.pth`
rewrite, `RECORD` rewrite, relink, or environment mutation.

For each process independently, preparation must establish all of the following
before promotion:

- no project editable `_editable_impl*.pth` file exists anywhere in the
  registered site-packages tree;
- a plain no-follow `site-packages/arc3_voi` package directory exists;
- its relative path set equals exactly the verified repository
  `src/arc3_voi` relative path set;
- every corresponding regular file is byte-identical to the verified
  repository source file;
- neither tree contains an unregistered omission, extra path, symlink,
  nonregular entry, alias, hard-link ambiguity, or changing file;
- the project `.dist-info` directory and `RECORD` exist, and the metadata and
  `RECORD` are structurally consistent but never used as a substitute for
  direct path-set and byte equality; and
- every recursively visited regular file beneath `.venv` has link count exactly
  one, as does every corresponding regular frozen repository source-parity
  file;
- ordinary directory link counts are permitted, and the resolved external
  base-interpreter target is outside the recursive `.venv` link-count scope but
  remains subject to its incorporated interpreter identity checks;
- the complete permitted `.venv` symlink set is exactly
  `bin/python3 -> python`, `bin/python3.12 -> python`,
  `bin/python -> /home/bansarinejad/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12`,
  and `lib64 -> lib`; each has uid/gid 1000, no-follow mode `0777`, and link
  count one, and every other symlink or special file is rejected;
- the sole permitted `.pth` anywhere beneath `.venv` is the standard copied
  `_virtualenv.pth`, only as exact 18-byte,
  no-final-LF ASCII `import _virtualenv` with SHA-256
  `69ac3d8f27e679c81b94ab30b3b56e9cd138219b1ba94a1fa3606d5a76a1433d`,
  paired with exact `_virtualenv.py` SHA-256
  `cfb3db86aaa53bb62b5ff764970bec2d71c9228590a0ebec57f6ec926cc0bf1a`,
  after validation proves that pair cannot supply project code;
- every other `.pth`, including every project editable `_editable_impl*.pth`,
  is rejected; and
- no environment variable, user site, `PYTHONPATH`, import hook, or other
  `sys.path` injection supplies the project.

The source authority is the exact O8v5 Git `ls-tree` inventory beneath
`src/arc3_voi`: 45 blobs, comprising 44 `.py` paths and `py.typed`. The plain
installed `site-packages/arc3_voi` tree must have exactly those same relative
paths and bytes, with no `__pycache__`, extra, omission, symlink, or special
file. Direct installed-vs-Git path and byte comparison is authoritative; no
metadata digest may substitute for it.

Preparation, the independent verifier, each runner, and the payload validator
use the same incorporated no-follow, descriptor-relative `.venv` walker at
every applicable gate. It anchors and opens each directory with
`O_DIRECTORY|O_NOFOLLOW` and never resolves a discovered child through a text
path. For every child directory it obtains a descriptor-relative no-follow
pre-stat, opens with `O_DIRECTORY|O_NOFOLLOW`, and requires `fstat` to match the
same device, inode, directory type, uid, gid, and registered mode. It freezes
the sorted child-name inventory before traversal and, after traversing all
children, re-`fstat`s and re-enumerates through the directory descriptor; the
same identity, ownership, mode, and exact sorted names must remain. For each
regular file it obtains the no-follow pre-open `lstat`, opens the child
descriptor-relative with `O_NOFOLLOW`, and `fstat`s the descriptor. The
pre-open and open identity tuple -- device, inode, mode, uid, gid, link count,
size, mtime, and ctime -- must agree, and link count must be one. The helper
checks the registered ownership, mode, regular-file type, and bounded size;
performs the bounded read and hash only through that descriptor; then performs
a second `fstat` and requires the complete tuple, including link count one, to
remain unchanged. A symlink is inspected only by descriptor-relative no-follow
pre-`lstat`, `readlinkat`, and post-`lstat`. The complete device, inode, symlink
type, mode, uid, gid, link-count, size, `mtime_ns`, and `ctime_ns` tuple must be
identical around `readlinkat`; uid/gid must be 1000, mode must be `0777`, link
count must be one, and the lexical target must be the corresponding one of the
exact four registered targets. The symlink is never traversed. The helper
rejects an open race, replacement, growth, short or excess read, unstable
metadata, alias, any other symlink, or any special file. Regular-file link count
and every registered symlink tuple field and lexical target are included in the
existing canonical virtual-environment materialization-hash rows at each gate;
these are internal predicates and do not add a schema field.

Exactly one project dist-info directory is permitted, for normalized project
name `arc3-crosslevel-voi` and version `0.1.0`. Its `RECORD` paths must be
unique, safely normalized, nonescaping, and complete for the exact installed
project payload and metadata. Every recorded hash and size must match bytes
read directly from the exact descriptor-stable target through that walker:
each non-self row must contain the correctly encoded SHA-256 and decimal size,
and both must match the direct bytes. Exactly one exception is permitted: the
`RECORD` self-row must have both its hash and size fields blank. Its
`direct_url.json` must record a noneditable installation.

The preserved O8v4 process-A editable `WHEEL` directly reports `Generator:
hatchling 1.31.0`. No noneditable copy-mode fixture has yet run, and no cached
hatchling artifact path or hash has been identified, so that historical output
is not represented as a pre-bound O8v5 backend artifact identity. The mandatory
real offline copy-mode fixture must prospectively produce the same exact
`WHEEL` Generator value; a mismatch is a STOP before O8v5. That fixture freezes
the common project metadata and console-script path set and count and the exact
bytes, hashes, and sizes of path-invariant files. It also freezes exact
registered-root-derived templates for path-dependent `direct_url.json` and
console-script bytes and for their corresponding `RECORD` rows. Disposable
fixture, process-A, process-B, and live staging roots are distinct, so the
path-dependent bytes and complete `RECORD` bytes are validated against the
appropriate exact registered-root derivation for each process rather than
falsely required to be byte-identical across roots. This document deliberately
does not invent an unmeasured metadata count. Dist-info multiplicity, an unsafe
or incomplete `RECORD`, a Generator mismatch, or an editable direct URL fails
before O8v5 construction. Direct source/install parity and strict metadata
validation remain independent fail-closed checks.

The independent post-preparation verifier must repeat the complete no-editable,
installed-tree, repository-parity, ownership, mode, link, and immutability
checks against both final promoted roots. It must prove the attempt source is
gone, the final roots have the registered device/inode promotion relation, and
the installed bytes still equal the final verified detached O8v5 repository
bytes. It must recursively recheck all regular-file link counts, the exact four
symlinks, absence of every special file, and the standard virtualenv bootstrap
after promotion. A hash inventory alone, or agreement between two equally
stale environments, is insufficient.

The scientific runner must repeat the applicable final-root structural and
byte-parity checks without importing the scientific module. Only after every
incorporated live gate passes and the exclusive process start claim is durably
published may it import `arc3_voi.action_qbc_v8_audit`. For process A, the exact
required source origin is:

    /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v5/processes/process-a/.venv/lib/python3.12/site-packages/arc3_voi/action_qbc_v8_audit.py

For process B it is:

    /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v5/processes/process-b/.venv/lib/python3.12/site-packages/arc3_voi/action_qbc_v8_audit.py

The payload validator must likewise acquire its validator claim before its
scientific-module import and require the corresponding final site-packages
origin. The runner and validator must reject the repository `src` origin, the
staging origin, the other process root, a symlink-equivalent path, a loader
without a plain file origin, and every path outside the exact registered final
site-packages package.

Each runner's isolated `-I -B` pre-import gate must require `sys.prefix` to be
its exact final process `.venv`; exclude every staging, repository-source,
other-process, user-site, and injected entry from `sys.path`; prove the target
scientific module is not already in `sys.modules`; and revalidate the complete
environment boundary. After claim and import, it must require exact matching
`__file__` and `__spec__.origin`, an exact single final `arc3_voi` package
search path, and no namespace or loader alias. The payload validator has its
own equivalent preclaim gate, publishes its own exclusive validator claim, and
then performs the same post-import origin checks.

After each `-I -B` import, the runner or validator must revalidate the imported
module origin, installed path set, installed bytes, repository source bytes,
all recursive regular-file link counts, the exact symlink set, absence of
special files, and directory anchors. `-B` must prevent import-time bytecode
writes in the validated package tree. Any import-time mutation, newly appearing
file, missing file, extra file, changed byte, altered `RECORD`, new `.pth`,
regular-file link count other than one, unregistered symlink or special file,
wrong origin, or path injection fails closed before payload acceptance.

The repository remains the scientific source authority; the installed package
is only a verified byte-identical materialization needed for relocation-safe
module resolution. `--no-editable` does not authorize a source fork or
wheel-specific scientific variant.

This contract does not claim that every virtual-environment path is a regular
file, or that every metadata or script byte is relocation-neutral. The exact
four registered symlinks and ordinary directory link counts above remain
permitted; all recursively visited regular files still require link count one.
An unused `direct_url.json` may retain a staging URL, and an unused generated
`arc3-voi` console script may retain an absolute staging shebang. Both remain
subject to regular-file link-count one. Registered children invoke the final
`<process-root>/.venv/bin/python3` directly; they never invoke that console
script or use `direct_url.json` to resolve code. Those unused records are
non-authoritative and do not replace the direct installed-package byte and
origin checks. If either record, or any other stale metadata or generated
script, enters a registered execution path, the lifecycle must fail closed.

## 6. Post-R8v4 launcher, presentation, and audit-harness incidents

Three administrative launcher/capture incidents occurred after R8v4 existed.
They are disclosed because they occurred around the incorporated result
transfer and publication workflow. None changed R8v4 bytes, evidence, Git
objects, refs, `FETCH_HEAD`, or scientific state before its later exact command
ran. A separate blocked audit-harness command during P8v8 authoring is disclosed
in section 6.4 and is not a protocol operation.

### 6.1 Pre-fetch-1 ProcessStartInfo incident

Before fetch 1, a PowerShell/.NET `ProcessStartInfo.ArgumentList` object was
null. Thirteen attempted `Add` calls produced non-terminating errors. A
one-token process containing only:

    ["C:\\Windows\\System32\\wsl.exe"]

then spawned and returned exit 0 with zero-byte stdout and stderr. It contained
no Git executable or Git argument and performed no registered fetch. Read-only
post-incident checks established no Git object, ref, or `FETCH_HEAD` mutation.

The specific post-R8 transfer-retry clause incorporated from P8v3 therefore
controlled. The later exact full fetch-1 argv, with canonical SHA-256
`60e699a98c08084c011b453eb4ec29a9dbe095bf1a207bb6069f88af584a5fc5`,
ran once and succeeded. It returned exit 0 and empty stdout. PowerShell rendered
native Git's presentation through a 964-byte UTF-16 `NativeCommandError`
capture with SHA-256
`82197c21c5574e78818b45e3e5b823ffc06251e86c7d7a580280fafe3c5398c9`.
That transformed capture is not evidence of a failed Git command.

### 6.2 Pre-fetch-2 JavaScript interpolation incident

Before fetch 2, the orchestration layer evaluated a JavaScript template
containing `${r8}` and raised `ReferenceError` before `shell_command` was
called. No child process started and no file, object, ref, `FETCH_HEAD`, or
network state changed.

The later exact full fetch-2 argv, with canonical SHA-256
`6152cfc7bd9ec3b7a6a4fe49ea9905a8d4fdb8cad6b4f205229296b581c71d5e`,
ran once and succeeded. It returned exit 0 and empty stdout. Its transformed
970-byte UTF-16 `NativeCommandError` capture has SHA-256
`d7ff5dc0ab7c2c776e0fa1b449362737919f65edb0d3f56a7d14eacc6419259c`.

### 6.3 Pre-push-2 JavaScript parse incident

Before result-tag push 2, the orchestration layer encountered a JavaScript
syntax error caused by a PowerShell backtick-newline sequence. Parsing failed
before `shell_command`; no process, network action, file write, object change,
or ref mutation occurred.

The later exact push-2 argv ran once and succeeded:

    ["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","push","origin","refs/tags/action-qbc-v8-open-diagnostic-result-v4:refs/tags/action-qbc-v8-open-diagnostic-result-v4"]

It returned exit 0 and the exact new-tag report was observed. A byte-identical
stdout/capture record was not retained in the consolidated evidence, so no
push-2 stream size or hash is asserted here.

For completeness, the preceding result-branch push 1 used an exact argv with
canonical SHA-256
`d05752cc67cfe44964690b72997de1b66170c10cfcfea89f41fc3aa354080b56`,
returned exit 0 with empty stdout, and produced a transformed 1364-byte capture
with SHA-256
`673279c3c588c1c10640a9c771a2a1a3c7f6e4a29609853226f308fc859ea75d`
reporting the new result branch.

These three incidents and three transformed captures are presentation and
launcher facts, not additional protocol fetches, pushes, failures, or evidence
mutations. The final public query in section 3 independently passed with exact
branch and tag values. No incident may be hidden, promoted into scientific
evidence, or used to repeat a consumed R8v4 operation.

### 6.4 Blocked P8v8 audit-harness write-tree command

During independent review of this amendment, an auditor intended to compute a
prospective tree read-only but mistakenly attempted this exact argv from
`D:\kaggle competitions\arc3-crosslevel-voi`:

    ["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","write-tree"]

The command produced empty stdout and displayed exactly this stderr text:

    fatal: Unable to create 'D:/kaggle competitions/arc3-crosslevel-voi/.git/index.lock': Permission denied

The raw stream encoding and hash and the isolated command return code and time
were not captured. Git's usual fatal return code is not substituted: a later
composite shell ended with return code 0 after 1.2 seconds, which cannot establish
the isolated command's return code or duration. The attempt stopped at denied
lock creation before producing tree output. Immediate no-write checks found no
`index.lock`; the existing index remained 25,682 bytes with SHA-256
`4692d064b3117f542335773b128a52b83d0d2fdb766391b8b7ddef9fefef2cf3`,
248 indexed paths, the exact pre-existing O8v4 tree, no staged entry, and status
containing solely this untracked amendment. O8v4/R8v4 refs remained at their
recorded exact identities. No object, ref, index, worktree, or evidence mutation
was observed; the indexed O8v4 tree object already existed.

This was a blocked authoring-audit-harness error outside protocol and science,
not a construction command, evidence event, or authorization to retry
`write-tree`. Prospective-tree review must instead reconstruct from non-writing
`ls-files` and `ls-tree` observations.

## 7. Fresh namespaces, stable schemas, and scientific invariance

O8v4's claimed paths are permanent evidence and may not be reused. O8v5 uses
the fresh execution root:

    /var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v5

All authority, process, output, preparation, verification, copied-remote, arm,
lifecycle, bundle, result-owner, and result-work paths are derived beneath that
root exactly as incorporated, with only the v5 root substitution.

O8v5 uses exactly these four fresh Windows paths:

    D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification-claim-v5.json
    D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verifier-start-claim-v5.json
    D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification-v5.json
    D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification-supervisor-v5.json

Their Linux source paths are the exact `/mnt/d/kaggle competitions/...-v5.json`
counterparts. The complete v5 root and all four Windows paths must be absent
before O8v5 bootstrap or claim. Existing, unsafe, ambiguous, nonempty, or
partially created fresh state stops permanently; it is not cleaned or retried.
No O8v4 root, file, claim, environment, result-work root, or unsuffixed path is
an O8v5 input.

At this recovery freeze, the v5 root, all four v5 Windows paths, and all three
prospective v8/v5 tags are locally absent. This local observation does not
replace the collision gates for later local and remote/public creation.

The registration schema remains `action-qbc-v8-open-registration-v1`. The
execution contract retains exactly 70 keys. Every incorporated preparation,
verification, remote, arm, lifecycle, process, validator, payload, finalization,
emergency, result-owner, result-document, and administrative-terminal schema
name and exact key set remains unchanged. Installed-package parity and
no-editable validation are administrative implementation invariants, not new
JSON fields.

No `project_install_sha`, metadata-count field, origin field, or other schema
member is added. Direct installed-vs-Git equality, whole-venv materialization
and link predicates, dist-info/`RECORD` validation, and import-origin checks are
enforced internally and bound through the existing full inventory,
materialization, source-manifest, and content predicates.

The treatment ID, diagnostic ID, platform, comparison, transform, resource,
payload, result-document, and scientific-contract identifiers remain unchanged.
All 140 scientific rows, twelve public scenes, transforms, roles, controls,
selectors, data, tolerances, reasons, fallbacks, call automata, scientific
functions, payload limits, action templates, analysis rules, resource budgets,
and the 2,100/2,400/2,700-second scientific limits remain exactly as
incorporated.

The dependency array's key sets, order, three names, and three versions remain
unchanged. Only `arc3-crosslevel-voi.editable` changes from `true` to `false`,
as section 5 freezes. The runtime module-origin contract correspondingly moves
from `<process-root>/src/arc3_voi/action_qbc_v8_audit.py` to the exact final
`<process-root>/.venv/lib/python3.12/site-packages/arc3_voi/action_qbc_v8_audit.py`,
whose bytes and relative package tree are bound back to frozen repository
`src/arc3_voi`. These are declared administrative packaging changes.

All five authorization Booleans remain false. This document authorizes no
lockbox, sealed evaluation, private-scene access, gameplay, leaderboard
submission, model change, positive mechanism claim, or third scientific start.
O8v5 is a fresh administrative execution of the same unchanged treatment, not
permission to tune using the O8v4 administrative failure.

Registration content/file hashes, P8v8 tree manifest, O8v5 added-file manifest,
source identities, path-derived argv hashes, environment inventories, installed
package identities, and result identities are regenerated from replacement
bytes. Such administrative changes are not scientific or named-schema changes.

## 8. Exact local fast-forward, P8v8 D17+A1, and O8v5 tree boundary

Before staging any P8v8 deletion or addition, the checked-out local
`action-qbc-v8-prereg` branch must advance from O8v4 to its already existing
direct child R8v4 using exactly one local, non-network, fast-forward-only merge:

    ["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-C","D:\\kaggle competitions\\arc3-crosslevel-voi","merge","--ff-only","action-qbc-v8-open-diagnostic-result"]

Pre-merge audits must prove the checked-out branch and remote-tracking
preregistration ref are O8v4; the local result branch and result-v4 tag are
R8v4; R8v4 has sole parent O8v4 and exact A2; HEAD and the index are exactly
O8v4 tree `ae2d8036451807ad5991828463067b09cefc26d0` with 248 entries; and status
contains only the byte-identical untracked P8v8 amendment, with no staged entry
or other drift. Post-merge audits must prove HEAD and the local preregistration
branch are exactly `b1d4c68891f0ecee05363bafe8e12549d9c8430b`; HEAD's tree and
the index are exactly R8v4 tree
`630443b64347d59671a8d6c3fb4f8abaffa1ac5b` with 250 entries; O8v4-to-R8v4
is exact A2; and status contains only the byte-identical untracked P8v8
amendment, with no staged entry or other drift. The merge must create no
commit, invoke no network, and leave every immutable ref at its prior commit.
Failure or ambiguity stops; no reset, force, second merge, or alternate
integration is permitted.

Only after that fast-forward does P8v8 stage deletion of all and only these
seventeen paths:

    artifacts/action_qbc_v8_open_registration.json
    artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json
    docs/action_qbc_v8_open_diagnostic_result.md
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

It adds only:

    docs/experiment_amendment_2026-08-19_action_qbc_v8_open_bounded_remote_verification_v8_environment_relocation_recovery.md

That exact semantic set is binding independent of Git's bytewise display order.
P8v8's direct R8v4 diff is D17+A1. Its tree must equal the P8v7 tree plus only
this P8v8 document by path, mode, Git blob, raw SHA-256, and byte count. The net
P8v7-to-P8v8 diff is exact A1. P8v8 modifies, renames, or adds no other path.

After P8v8 is committed, tagged, completely audited, and successfully
published, O8v5 re-adds all and only the fourteen non-registration source,
runbook, and test paths in the deletion list. Before the producer runs, they
are the only staged paths, each at stage 0 and Git mode `100644`.

Their differences from O8v4 are limited to:

- the non-editable environment build and installed-package validations in
  sections 4 and 5;
- the exact project dependency `editable` value and final installed-module
  origin substitution declared in sections 5 and 7;
- v5 paths, P8v8/O8v5/R8v5 lineage and refs, and the 66-row authority plan;
- regenerated administrative manifests, hashes, identities, and runbook text;
- the exact 14/4 argv-hash partition in section 10; and
- the regression tests in section 13.

Every scientific source and semantic must reverse to the same frozen v7 source
under the incorporated inverse and AST audits.

The registration builder runs once after those fourteen additions are staged:

    ["uv","run","--frozen","--extra","dev","python3","-I","-B","scripts/build_action_qbc_v8_open_registration.py","--repository-root",".","--preregistration-tag","prereg-action-qbc-v8-open-bounded-remote-verification-v8","--output","artifacts/action_qbc_v8_open_registration.json"]

It creates the sole fifteenth O8v5 addition:

    artifacts/action_qbc_v8_open_registration.json

The registration is a no-follow regular worktree file owned by the registered
Linux user, mode `0600`, canonical JSON without final LF, and staged Git mode
`100644`. Reconstruction must be byte-identical. O8v5 is committed only after
every section-13 gate succeeds and is then tagged freeze-v5.

R8v5 may add exactly one outcome-dependent incorporated result path set.

For selected bundle `scientific_result`, exact A3 and 252 tree entries:

    artifacts/action_qbc_v8_open_diagnostic.json
    artifacts/action_qbc_v8_open_diagnostic_receipt.json
    docs/action_qbc_v8_open_diagnostic_result.md

For an ordinary selected `administrative_terminal`, exact A2 and 251 tree
entries:

    artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json
    docs/action_qbc_v8_open_diagnostic_result.md

For the incorporated receipt-finalization or finalizer-process doc-only
override, exact A1 and 250 tree entries:

    docs/action_qbc_v8_open_diagnostic_result.md

The selected bundle alone determines the set. Paths from another set, a union,
an omission, or a stale R8v4 result byte fail closed.

## 9. Authority, preparation-attempt, and ledger plans

The canonical O8v5 authority plan contains exactly 66 argv rows in this order:

1. the incorporated initial local-config query;
2. active freeze-v5 tag-type, tag-resolution, and HEAD rows;
3. four historical rows for each P8v1, P8v2, P8v3, and P8v4: tag type, tag
   resolution, sole-parent relation, and exact registered direct diff;
4. four historical O8v1 rows: tag type, resolution, sole parent P8v4, and A15;
5. four historical P8v5 rows: tag type, resolution, sole parent O8v1, and
   D15+A1;
6. four historical O8v2 rows: tag type, resolution, sole parent P8v5, and A15;
7. four historical P8v6 rows: tag type, resolution, sole parent O8v2, and
   D15+A1;
8. four historical O8v3 rows: tag type, resolution, sole parent P8v6, and A15;
9. four historical P8v7 rows: tag type, resolution, sole parent O8v3, and
   D15+A1;
10. four historical O8v4 rows: tag type, resolution, sole parent P8v7, and A15;
11. four historical R8v4 rows: result-v4 tag type, resolution, sole parent
    O8v4, and A2;
12. four active P8v8 rows: tag type, resolution, sole parent R8v4, and D17+A1;
13. the active P8v8 document `ls-tree` and `cat-file` rows;
14. the O8v5 sole-parent P8v8 row and exact P8v8-to-O8v5 A15 row; and
15. the incorporated post-config, HEAD, tree, batch-object, index, and status
    rows.

The P8v7-to-P8v8 net-A1 relation, tree identity, and exact 234-entry inventory
are independently validated even where not represented by a separate authority
command row. All producer and consumer implementations must generate the same
byte-identical 66-row sequence.

The preparation-attempt plan remains exactly 54 rows for each permitted
preparation attempt. Its commands, ordering, timeouts, caps, cleanup,
atomic-promotion, and evidence semantics remain incorporated except for the
registered v5 path/ref substitutions and exact environment-build argv. At most
two internal preparation attempts remain permitted. They are not retries of
O8v4.

A successful first-attempt O8v5 preparation receipt therefore contains exactly
120 command-ledger rows: the 66-row authority plan followed by one complete
54-row attempt plan. A failed first internal attempt may use only the
incorporated bounded-prefix cleanup semantics. No successful first-attempt
receipt may contain fewer, additional, reordered, or duplicated rows.

The Windows remote verifier's separate maximum of three internal attempts is
unchanged and is not part of either command plan. No internal v5 attempt is a
retry of an O8v4 command, claim, query, or process.

## 10. Exact O8v4-to-O8v5 argv-hash partition

The execution contract retains exactly eighteen argv-hash keys. Compared with
O8v4, these fourteen hashes must derive-change:

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

These four hashes must remain unchanged:

    linux_host_launcher
    preflight
    reconstructor
    tests

Argv hashes cover argv arrays only. `environment_build` changes specifically
because of the two appended option forms, `--no-editable` and
`--link-mode copy`, and must equal the registered hash in section 5. The other
thirteen changed argv families change only because their arrays contain the
declared v5 path, ref, tag, or lineage substitutions. The dependency Boolean,
script bytes, installed-package identities, and final-module-origin contract
regenerate and validate separately; they are not causes of argv-hash changes.
No key may be added, removed, renamed, silently retained, or changed outside
this exact partition.

## 11. Prospective publication and execution order

After the local fast-forward and exact P8v8 D17+A1 commit/tag audits, publish
P8v8 with exactly one non-force atomic Windows Git invocation:

    ["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-C","D:\\kaggle competitions\\arc3-crosslevel-voi","push","--atomic","origin","refs/heads/action-qbc-v8-prereg:refs/heads/action-qbc-v8-prereg","refs/tags/prereg-action-qbc-v8-open-bounded-remote-verification-v8:refs/tags/prereg-action-qbc-v8-open-bounded-remote-verification-v8"]

Because remote `action-qbc-v8-prereg` is O8v4 and R8v4 is its direct child,
this update remains a non-force fast-forward through R8v4 to P8v8. The result
branch remains at R8v4.

After O8v5 and every post-commit audit pass, publish O8v5 with exactly one
non-force atomic Windows Git invocation:

    ["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-C","D:\\kaggle competitions\\arc3-crosslevel-voi","push","--atomic","origin","refs/heads/action-qbc-v8-prereg:refs/heads/action-qbc-v8-prereg","refs/tags/action-qbc-v8-open-diagnostic-freeze-v5:refs/tags/action-qbc-v8-open-diagnostic-freeze-v5"]

Each push is single-use. Failure, partial or non-atomic behavior, uncertainty,
unexpected ref movement, or prospective-tag collision stops before the next
boundary. Exact local absence is required immediately before each sole local
tag creation. Because no pre-push remote/public absence query is authorized,
the corresponding sole non-force push must report the exact `[new tag]` status;
`up to date`, already-existing, rejected, or any other status is a collision and
STOP. Each phase-specific authorized later public query establishes only its
requested post-push ref values, and neither requests prereg-v8. No ref is
forced, deleted, rewound, repointed, or reused. No extra network query is
authorized merely to rehearse creation; collision-safe creation/push behavior
and the incorporated authority checks remain binding.

No remote query, browser refresh used as a protocol check, API query,
authenticated ref query, SSH query, anonymous query, connectivity probe, or
visibility action may occur between the P8v8 push and O8v5 push. The next
protocol network action after successful O8v5 publication is exactly one
credential-disabled anonymous query from the registered neutral WSL cwd and
empty environment for only:

    refs/heads/action-qbc-v8-prereg
    refs/tags/action-qbc-v8-open-diagnostic-freeze-v5

Success requires exactly those two records, branch then tag, each once at the
recorded lowercase 40-hex O8v5 commit, with empty stderr and no peeled,
duplicate, additional, malformed, credential-assisted, or authenticated
record. The query is consumed whether it succeeds or fails and is never
retried. Only exact success authorizes fresh-root bootstrap.

The complete prospective ordering is binding:

1. preserve and audit all O8v4/R8v4 evidence and current refs;
2. perform the sole local O8v4-to-R8v4 fast-forward-only merge;
3. stage, commit, tag, audit, and atomically publish exact P8v8 D17+A1;
4. stage fourteen O8v5 source paths, run the sole producer, stage the
   registration, run every frozen construction gate, commit, tag, audit, and
   atomically publish exact O8v5 A15;
5. consume the sole anonymous branch-plus-freeze-v5 query;
6. run the one-shot authority bootstrap;
7. run bounded preparation and the independent preparation verifier;
8. run the sole Windows supervisor and verifier in the four fresh v5 paths;
9. because the remote lifecycle claim exists, run the sole Linux lifecycle
   regardless of the remote terminal status;
10. finalize and publish the valid administrative or scientific result through
    the registered authority result tag;
11. perform the two incorporated, separately validated result transfers;
12. fast-forward the stable result branch from R8v4 to R8v5 with the first
    non-force result push, then publish result-v5 with the second non-force
    result push; and
13. consume the sole credential-disabled public result branch-plus-tag query.

The final query may request only:

    refs/heads/action-qbc-v8-open-diagnostic-result
    refs/tags/action-qbc-v8-open-diagnostic-result-v5

It must return branch then tag exactly once at R8v5 with empty stderr. PUBLIC
visibility remains unchanged throughout. This amendment authorizes no
visibility query or mutation.

## 12. O8v5 lifecycle and R8v5 result boundary

After the sole O8v5 anonymous freeze check succeeds, the incorporated bootstrap,
preparation, independent verification, remote supervisor, lifecycle, finalizer,
publisher, transfer, and result-verification protocol runs once in the fresh
namespaces from section 7.

Preparation must build both copied no-editable environments within the chosen
attempt parent, validate them, and atomically promote that parent without
modifying the environments afterward. Independent verification must prove each
final root retains the exact four symlinks, no other symlink or special file,
link count one for every recursively visited regular `.venv` file, the sole
exact standard `_virtualenv.pth` bootstrap, a plain installed byte-identical
project package, and no editable `.pth`. Each final process's isolated `-I -B`
Python must import the module only after its own durable claim and from only its
corresponding final installed origin, then repeat those checks.

The Windows verifier must create its fresh lifecycle and verifier-start claims
exactly once. Claim existence makes the Linux lifecycle mandatory regardless of
verifier or supervisor outcome. A canonical failed remote receipt skips both
scientific starts and must still reach a publishable administrative result. A
verified receipt authorizes only the unchanged process-A-then-process-B
scientific sequence. Process B remains conditional on valid process-A payload
validation exactly as incorporated.

If either registered project installation or any registered execution-path
component is stale, editable, missing, extra, mutated, symlinked,
non-byte-identical, wrongly rooted, or importable only through path injection,
the new lifecycle must fail administratively under the registered stage. It may
not repair the environment, switch to repository `src`, add `PYTHONPATH`,
rewrite `.pth` or `RECORD`, or try process B as a fallback. Unused stale
`direct_url.json` or console-script text is not a module source and supplies no
authority; use of either by a registered child fails closed.

If R8v5 is validly created, the authority contains only:

    refs/tags/action-qbc-v8-open-diagnostic-result-v5

The authority result branch remains absent. R8v5 must have sole parent O8v5,
the exact selected A3/252, A2/251, or A1/250 outcome boundary in section 8, and
result bytes that reconstruct the registered commit and tag identically. Only
after independent bundle, path-set, commit, parent, tree, delta, document, and
tag validation may the original repository advance its stable result branch
from R8v4 to R8v5 and acquire result-v5.

A valid administrative terminal remains a valid result publication. A valid
scientific outcome still requires both payloads, both validators, exact payload
byte identity, and every incorporated scientific gate. Neither outcome permits
a positive mechanism claim beyond its registered semantics.

## 13. Required implementation and regression gates

Before O8v5, all incorporated offline tests and frozen gates remain mandatory.
Additional tests must prove:

- P8v7, O8v4, and R8v4 have the exact commits, trees, tags, sole-parent
  relations, A15/A2 deltas, and public terminal facts in sections 1-3;
- P8v8 is R8v4's exact D17+A1 child, its tree equals P8v7 plus only this
  document, P8v7-to-P8v8 is net A1, and its inventory is exactly 234;
- O8v5 is P8v8's exact A15 child with exactly 249 entries and freeze-v5 only at
  O8v5; R8v5, when present, has sole parent O8v5 and exactly the selected
  scientific A3/252, administrative A2/251, or doc-only A1/250 result set;
- the local preregistration branch fast-forwards O8v4 to R8v4 before staging,
  then has exact R8v4 HEAD/tree/index/250-entry state and only the byte-identical
  untracked amendment before staging; it creates no merge commit, invokes no
  network, and permits no reset, force, alternate parent, or staging drift;
- all preserved v4 evidence retains its exact bytes, modes, owners, hashes,
  statuses, cross-links, absences, and consumed state;
- both exact 83-byte no-LF v4 editable `.pth` files retain their registered
  paths, stale contents, and SHA-256 values; both targets remain absent; and
  neither final environment gains an installed package copy;
- the v4 causal regression reports the deterministic sufficient relocation
  defect without asserting any exception text, class, traceback, or discarded
  stream;
- process A's v4 start claim and exit 3 remain explicit, its payload and
  validator artifacts remain absent, process B remains absent, and R8v4 remains
  an administrative rather than scientific result;
- all three post-R8v4 launcher incidents and the exact retained capture
  sizes/hashes are preserved, while no unretained push-2 stream identity is
  invented;
- the environment-build argv is exactly the twelve-token array in section 5
  with SHA-256
  `a815872b8bc76c3b8118e47ddac9e0e36b97820181a81ae28cc1bcddcc9a642c`;
- omission, duplication, reordering, spelling variation, editable fallback,
  omitted or non-copy link mode, changed Python, changed uv, changed offline
  flag, extra argument, or altered environment-build token is rejected;
- the dependencies array retains the same keys, order, names, and versions,
  changes only `arc3-crosslevel-voi.editable` from `true` to `false`, and leaves
  the NumPy and PyYAML entries unchanged;
- `uv.lock` retains exact workspace source `source = { editable = "." }`, and
  neither the lock, `pyproject.toml`, build-backend input, nor optional extras
  change;
- a real offline `uv sync --no-editable --link-mode copy` build occurs beneath
  a temporary `.prepare-attempt-1`, followed by the actual atomic parent
  promotion rather than a mocked path substitution;
- both final promoted process roots then run their real registered `-I -B`
  Python and successfully import from only the final site-packages origins;
- preparation and independent verification require no project editable
  `_editable_impl*.pth`, a plain installed `arc3_voi` tree, exact installed-vs-
  repository path-set equality, and byte equality for every file;
- the O8v5 Git source authority has exactly 45 `src/arc3_voi` blobs, 44 `.py`
  plus `py.typed`, and each installed package has exactly those relative paths
  and bytes with no `__pycache__`, extra, omission, symlink, or special file;
- preserved O8v4 evidence alone is described as directly reporting editable
  `WHEEL` Generator `hatchling 1.31.0`; the real noneditable offline fixture
  must prospectively produce that exact value, and no unobserved cached backend
  artifact identity is asserted;
- the fixture learns and freezes the single project dist-info plus console-
  script common path set/count and all path-invariant bytes, hashes, and sizes
  without an invented count; exact registered-root-derived templates govern
  path-dependent `direct_url.json`, console-script, and corresponding `RECORD`
  bytes separately for the disposable fixture, process A, process B, and live
  staging roots;
- all `RECORD` paths are unique, safely normalized, nonescaping, and complete;
  every non-self row's encoded SHA-256 and size match the descriptor-stable
  direct target, only the `RECORD` self-row has blank hash and size, and
  `direct_url.json` is noneditable;
- every preparation, verifier, runner, and validator gate uses the same exact
  descriptor-relative walker: each child directory uses no-follow pre-stat,
  `O_DIRECTORY|O_NOFOLLOW`, and matching device/inode/type/uid/gid/mode, then
  stable post-traversal `fstat` plus exact sorted-name re-enumeration; each
  regular uses no-follow pre-open `lstat`, `O_NOFOLLOW` open, and two matching
  `fstat` identity tuples including device, inode, mode, uid, gid, link count
  one, size, mtime, and ctime around its bounded read/hash; and each symlink uses
  matching pre/post no-follow `lstat` device/inode/type/mode/uid/gid/link-count/
  size/`mtime_ns`/`ctime_ns` tuples around `readlinkat`, freezes that tuple and
  exact lexical target into the existing materialization rows, and is never
  traversed;
- only the exact hashed standard `_virtualenv.pth`/`_virtualenv.py` pair may
  remain after proof that it cannot supply project code; every other `.pth`
  fails;
- every recursively visited regular file beneath each `.venv`, plus every
  corresponding regular frozen source-parity file, has link count one after
  real promotion and again after exact import;
- the complete symlink inventory is exactly the four registered
  `bin/python3`, `bin/python3.12`, `bin/python`, and `lib64` links with their
  frozen targets, each at uid/gid 1000, no-follow mode `0777`, and link count
  one; ordinary directory link counts and the resolved external base-interpreter
  target are handled only by their exact declared exceptions, and every other
  symlink or special file fails;
- missing, extra, mutated, symlinked, hard-linked, changing, wrong-owner,
  wrong-mode, staging-root, other-process, repository-`src`, user-site,
  arbitrary-`.pth`, environment-injected, or otherwise wrong-origin packages
  fail closed;
- rewriting `.pth`, metadata, or `RECORD` cannot make a nonidentical package
  pass direct path and byte comparison, and no post-promotion rebuild or repair
  is accepted;
- an unused staging URL in `direct_url.json` and an unused staging shebang in
  the generated `arc3-voi` console script are treated as non-authoritative,
  while any registered execution-path use of either is rejected;
- neither scientific runner nor payload validator imports the scientific module
  before its durable start or validator claim; after import, each exact module
  origin is the corresponding final installed file and every anchor remains
  unchanged;
- each real runner/validator `-I -B` gate requires exact final `sys.prefix`, no
  staging/source/other-process/user/injected `sys.path`, no preloaded scientific
  module, exact `__file__` and `__spec__.origin`, one exact package search path,
  and full post-import byte/link revalidation;
- every registered child invokes only final `.venv/bin/python3`; no stale
  generated console script is ever an executable path;
- the 66-row authority plan and 54-row attempt plan are byte-identical across
  producer, reconstructor, preparation, lifecycle, finalizer, runner,
  validators, audit library, and tests;
- a successful first-attempt preparation has exactly 120 ledger rows, while
  bounded failure prefixes preserve the incorporated attempt semantics;
- all v5 Linux and Windows paths are fresh, exact, absent before use, and reject
  every v4 or unsuffixed path;
- prereg-v8, freeze-v5, and result-v5 are absent locally before sole local
  creation; without an unauthorized pre-query, each sole non-force push must
  report exact `[new tag]` status, while `up to date`, an existing tag, or any
  other status stops; the later public query proves only post-push value, and
  result-v5 remains locally absent until a valid selected R8v5 exists;
- the registration retains its v1 schema, exact 70-key execution contract, all
  named evidence schemas and key sets, and every unchanged scientific field;
- the exact fourteen changed and four unchanged argv-hash keys in section 10
  are enforced, with no nineteenth key and no partition drift;
- every O8v4-to-O8v5 executable difference is a declared environment fix,
  path/ref/lineage substitution, regenerated administrative identity, runbook
  change, or regression test, and the scientific inverse and AST audits remain
  exact;
- valid remote failure still skips science and publishes administratively;
  verified remote state reaches the unchanged two-process sequence only if all
  environment gates pass;
- a valid emergency bundle and a valid normal bundle each publish idempotently
  to only result-v5, with the authority result branch absent, and select only
  their exact incorporated A3, A2, or A1 result path set;
- the stable result branch can advance only R8v4 -> P8v8 -> O8v5 -> R8v5 by
  non-force fast-forward and the two result pushes retain their incorporated
  branch-then-tag order;
- the PUBLIC repository permits no visibility action, and each sole anonymous
  query accepts only its registered two refs once at the exact commit; and
- tests are offline, use disposable nonprotocol roots, do not touch the real v4
  evidence or v5 paths, do not mutate a remote ref or visibility, and write no
  real result path.

The builder runs only after the fourteen authored O8v5 additions are staged.
After its output is staged, the sole reconstructor must pass byte-for-byte,
followed in order by the full source/AST invariance gates, frozen pytest suite,
Ruff, strict mypy, and the incorporated raw-byte, tree, index, tool,
environment, and no-premature-science gates in the explicit Ubuntu environment.
O8v5 is committed only after that complete ordered gate sequence passes.

Any failed, partial, timed-out, ambiguous, or repeated one-shot construction,
gate, publication, anonymous verification, bootstrap, claim, lifecycle, or
result operation is not the registered O8v5/R8v5 sequence and requires another
prospective preregistration. Internal bounded attempts remain governed only by
their exact registered ledgers and cleanup rules.

## 14. Claims and actions that remain prohibited

This recovery records an administrative environment-relocation defect observed
after one real process-A start claim. It is not evidence about the Action-QBC
mechanism, model quality, scientific rows, public scenes, hidden generalization,
causality, calibrated inference, runtime efficacy, security, or Kaggle
performance. R8v4 is a valid published administrative result, not a null or
positive scientific result.

The successful freeze-v4 and result-v4 public queries prove only that their
requested refs were publicly readable at those observations. The successful
bounded remote tag attempt proves only the registered freeze-v4 ref response.
None is cryptographic attestation or proof against a malicious same-authority
actor.

No operator may rerun O8v4 preparation, verification, supervisor, verifier,
arm, lifecycle, process A, finalizer, publisher, transfer, result push, or
anonymous query; start process B under O8v4; rebuild or repair either v4
environment; rewrite the stale `.pth` targets; install a missing package copy;
capture a replacement exception; create a second R8v4; or move any historical
tag.

No operator may treat the pre-fetch or pre-push launcher incidents as authority
for another consumed Git operation, treat transformed PowerShell captures as
native command failures, or fabricate the unretained push-2 capture.

No O8v5 implementation may add `PYTHONPATH`, relax `-I -B`, accept editable
installation, compare metadata instead of bytes, trust `RECORD` instead of the
source tree, rebuild after promotion, import before claim, accept repository
`src` as the runtime origin, execute a generated console script, reuse any v4
path, or widen scientific authority.

Outside the exact incorporated maximum-two internal preparation attempts and
maximum-three internal remote attempts, including only their registered cleanup
rules, no operator or external process may retry or clean a failed or incomplete
O8v5 replacement. No cleanup or retry is permitted after a terminal boundary.
No failure may be tuned away or described as scientific evidence. A resulting
R8v5 is publishable only with its exact registered administrative or scientific
meaning.
