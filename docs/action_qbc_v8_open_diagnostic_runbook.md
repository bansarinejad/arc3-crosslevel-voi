# Action-QBC v8 open diagnostic runbook

This runbook operationalizes the frozen v8 amendment through its P8v5 public-visibility
recovery. The preregistration documents are authoritative when this summary and the
protocol differ. The historical O8v1 publication stopped before bootstrap after its sole
anonymous check failed because the repository was PRIVATE; O8v1 and freeze-v1 remain
immutable and may not be retried or executed. V8 is an open public-fixture replication, not a
lockbox, runtime-admission, leaderboard, or positive-mechanism experiment.

## Immutable identities

- Binding preregistration commit: `09f9caea346866a1acf35c20e0c9d937096b5ce3`
- Preregistration tag:
  `prereg-action-qbc-v8-open-bounded-remote-verification-v5`
- Preregistration document SHA-256:
  `cc9d787a64700332a44f543e7a949ee5522c3663b6b0eb54e418840e560cfe6d`
- Preregistration document:
  `docs/experiment_amendment_2026-08-18_action_qbc_v8_open_bounded_remote_verification_v5_public_visibility_recovery.md`
- Preregistration document Git blob: `7c0955a775af89dcfcde4796a9bbb4d470669d10`
- Preregistration document byte count: `25872`
- P8v4 lineage anchor: `e0bff9ffc185196cafa938c8f7c9a7186366258b`
- P8v4 lightweight tag:
  `prereg-action-qbc-v8-open-bounded-remote-verification-v4`
- Historical O8v1 commit: `7685fbdccd41702216b3a3f06d2a0ac699aca7ec`
- Historical O8v1 tree: `9b9ad5ba986afacbcdb1fde3cd69e0f1c94efdf2`
- Immutable historical O8v1 tag: `action-qbc-v8-open-diagnostic-freeze-v1`
- P8v3 direct parent: `996ab2bb5a24143a110673977f63e7d111cf2060`
- P8v3 lightweight tag:
  `prereg-action-qbc-v8-open-bounded-remote-verification-v3`
- P8v2 direct parent: `91c5ba1862fc7701ed2276ddd64b99fdb8b7ad1d`
- P8v2 lightweight tag:
  `prereg-action-qbc-v8-open-bounded-remote-verification-v2`
- Original P8v1 ancestry anchor: `ebf6031a284ecbffb53ba1582124b7e4c9eb3e56`
- Original P8v1 lightweight tag:
  `prereg-action-qbc-v8-open-bounded-remote-verification-v1`
- Frozen R7 parent of P8v1: `6f918e098a9ea97cadbb377027a8eb5caeb9589b`
- Open-freeze tag: `action-qbc-v8-open-diagnostic-freeze-v2`
- Result branch: `action-qbc-v8-open-diagnostic-result`
- Result tag: `action-qbc-v8-open-diagnostic-result-v2`
- Original Windows checkout: `D:\kaggle competitions\arc3-crosslevel-voi`
- Explicit WSL distribution: `Ubuntu`
- Linux execution root: `/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open`

Record the eventual O8v2 commit before any execution command. Every command below is a
single-use command unless the text explicitly calls it publication-only recovery.

The historical O8v1 atomic publication succeeded, then its one credential-disabled
anonymous command was invoked once and failed solely because the repository was PRIVATE.
That invocation returned exit code 128, zero stdout bytes (SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`), and exactly 83
ASCII stderr bytes with a final LF (SHA-256
`2e554a39e2bb4414b5e2c3f5a90ebc87b405b5b8231d692704ec6df4580e8f60`):
`fatal: could not read Username for 'https://github.com': terminal prompts disabled\n`.
No O8v1 bootstrap, execution root, claim, receipt, science, result object, or result ref
exists. This disclosure neither repairs nor authorizes a second check of O8v1.

## Threat model and timing

The protocol detects accidental, partial, stale, cross-run, symlink/path-replacement,
inherited-configuration, duplicate-start, timeout, and crash-residue failures at its stated
check points. It does not claim protection from root/admin, a malicious process with the
same UID that coherently rewrites bytes and hashes between checks, kernel/tool compromise,
SHA collision, malicious clocks, power loss beyond documented fsync semantics, or remote
service compromise. Independent verification means a separate standard-library
implementation recomputes current bytes; it is not a separate trust principal or proof of
historical execution.

All recorded durations are actual, unclamped monotonic intervals. Windows verifier live
admission ends at `V+390s`, its forced cleanup at `V+420s`, and receipt work targets
`V+430s`. The supervisor's immutable main-entry epoch dominates child control at `S+430s`,
cleanup at `S+460s`, and receipt work at `S+480s`. The Linux driver uses one immutable
main-entry epoch, stops new science at `D0+7200s`, and ends at `D0+8400s`. These are
admission/cleanup targets, not claims that blocking filesystem operations can be
interrupted at an exact nanosecond. For `n` persisted remote attempts, validation requires
exactly `total_duration_milliseconds >= sum(attempt.duration_milliseconds) +
15000*max(0,n-1)`; there is no per-attempt flooring addition, clamp, or upper bound.

## 1. Build and freeze O8v2

Perform all pre-O8v2 construction and gates in Ubuntu against the original checkout. The
launcher is `wsl.exe -d Ubuntu --cd 'D:\kaggle competitions\arc3-crosslevel-voi'` and its
resulting WSL cwd must be exactly
`/mnt/d/kaggle competitions/arc3-crosslevel-voi`. Do not run the producer, reconstructor,
tests, Ruff, or mypy as PowerShell-native or Windows-native processes, and do not place an
inner command in a PowerShell command string. Pass every member as a distinct argv token.

The exact outer prefix for each of the five inner argv arrays below is:

```json
["C:\\Windows\\System32\\wsl.exe","-d","Ubuntu","--cd","D:\\kaggle competitions\\arc3-crosslevel-voi","--","/usr/bin/env","-i","GIT_CONFIG_COUNT=0","GIT_CONFIG_GLOBAL=/dev/null","GIT_CONFIG_NOSYSTEM=1","GIT_NO_REPLACE_OBJECTS=1","GIT_TERMINAL_PROMPT=0","HOME=/home/bansarinejad","LANG=C","LC_ALL=C","PATH=/usr/local/bin:/usr/bin:/bin","PYTHONDONTWRITEBYTECODE=1","PYTHONHASHSEED=0","PYTHONNOUSERSITE=1","TZ=UTC","UV_CACHE_DIR=/home/bansarinejad/.cache/uv","UV_NO_PROGRESS=1","UV_OFFLINE=1","UV_PROJECT_ENVIRONMENT=.venv-wsl","UV_PYTHON_DOWNLOADS=never","XDG_CONFIG_HOME=/nonexistent","<INNER_ARGV...>"]
```

Replace only the final placeholder by appending the members of one inner array; the array
is not embedded as one string. The operational pre-O8v2 environment is constructed from an
empty mapping and has exactly this nineteen-member object:

```json
{"GIT_CONFIG_COUNT":"0","GIT_CONFIG_GLOBAL":"/dev/null","GIT_CONFIG_NOSYSTEM":"1","GIT_NO_REPLACE_OBJECTS":"1","GIT_TERMINAL_PROMPT":"0","HOME":"/home/bansarinejad","LANG":"C","LC_ALL":"C","PATH":"/usr/local/bin:/usr/bin:/bin","PYTHONDONTWRITEBYTECODE":"1","PYTHONHASHSEED":"0","PYTHONNOUSERSITE":"1","TZ":"UTC","UV_CACHE_DIR":"/home/bansarinejad/.cache/uv","UV_NO_PROGRESS":"1","UV_OFFLINE":"1","UV_PROJECT_ENVIRONMENT":".venv-wsl","UV_PYTHON_DOWNLOADS":"never","XDG_CONFIG_HOME":"/nonexistent"}
```

This is an operational build/gate environment, not the registered seventeen-key
`preparation_command_environment`. In particular, `PATH`, `UV_OFFLINE`, and
`UV_PROJECT_ENVIRONMENT` distinguish it from preparation. The real DrvFS checkout must use
`.venv-wsl`; it must not let `uv run` discover, reinterpret, or replace the Windows `.venv`.
A disposable ext4 rehearsal clone may use its own `.venv` instead. In both cases the
environment directory is ignored, untracked operator tooling: neither rehearsal nor real
O8v2 tree, index, manifest, registration, or commit identity may depend on its bytes.

When a disposable ext4 rehearsal is populated from a raw DrvFS snapshot, first copy the
exact bytes and record every source file's SHA-256 and byte count. Before `git add`, normalize
every one of the fourteen ordinary source files to filesystem mode `0644`; equivalently, the
rehearsal may stage each already verified exact blob with cacheinfo mode `100644`. Reopen all
fourteen files after normalization, recompute SHA-256 and byte count, and require exact
equality with the pre-normalization records before continuing. The rehearsal index must then
report mode `100644` for all fourteen staged entries.

This mode normalization applies only to the disposable ext4 materialization. It must not
change the authoritative DrvFS checkout: its raw source bytes remain untouched. The real
DrvFS index must independently report mode `100644` for each of the same fourteen paths;
rehearsal normalization is not evidence for, or a repair of, the real index.

Before producing the registration, stage all and only these exact fourteen
non-registration additions:

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

The producer then generates the sole fifteenth addition:

```text
artifacts/action_qbc_v8_open_registration.json
```

Before the producer, the index must contain exactly the fourteen listed paths as additions;
after generation and staging it must contain exactly the fifteen listed paths as additions.
At both points every entry must be an ordinary stage-zero entry with the expected path,
mode, and blob ID. Reject unmerged stages, split-index/link extensions, every
`.git/sharedindex.*` entry, sparse-index directory entries, sparse-checkout state,
`skip-worktree`, `assume-unchanged`, and every other nonordinary cache-entry flag. The
worktree may have no filtered tracked-byte change and no untracked path other than the
ignored environment directory appropriate to the checkout.

Invoke the exact producer once:

```json
["uv","run","--frozen","--extra","dev","python3","-I","-B","scripts/build_action_qbc_v8_open_registration.py","--repository-root",".","--preregistration-tag","prereg-action-qbc-v8-open-bounded-remote-verification-v5","--output","artifacts/action_qbc_v8_open_registration.json"]
```

Stage the generated registration, then invoke the exact reconstructor once:

```json
["uv","run","--frozen","--extra","dev","python3","-I","-B","scripts/reconstruct_action_qbc_v8_open_registration.py","--repository-root",".","--registration","artifacts/action_qbc_v8_open_registration.json"]
```

Run the exact three frozen gate arrays once each, in this order:

```json
["uv","run","--frozen","--extra","dev","pytest","-q","tests/test_action_qbc_v7_audit.py","tests/test_action_qbc_v8_audit.py","tests/test_action_qbc_v8_lifecycle.py","tests/test_action_qbc_v8_registration.py"]
["uv","run","--frozen","--extra","dev","ruff","check","src/arc3_voi/action_qbc_v8_audit.py","scripts/build_action_qbc_v8_open_registration.py","scripts/execute_action_qbc_v8_open_lifecycle.py","scripts/finalize_action_qbc_v8_open_diagnostic.py","scripts/prepare_action_qbc_v8_open.py","scripts/reconstruct_action_qbc_v8_open_registration.py","scripts/run_action_qbc_v8_open_diagnostic.py","scripts/supervise_action_qbc_v8_remote_tag.py","scripts/validate_action_qbc_v8_open_payload.py","scripts/verify_action_qbc_v8_remote_tag.py","tests/test_action_qbc_v8_audit.py","tests/test_action_qbc_v8_lifecycle.py","tests/test_action_qbc_v8_registration.py"]
["uv","run","--frozen","--extra","dev","mypy","--strict","src/arc3_voi/action_qbc_v8_audit.py"]
```

Do not run `--verify-open-freeze` during this construction sequence. Its placement remains
unchanged in section 3: it runs from the detached authority clone only after the one-shot
authority bootstrap.

If the producer, reconstructor, an index/flag check, or any frozen gate fails, times out, or
observes unexpected bytes, stop the one-shot freeze immediately. Do not run a later array,
regenerate the registration, rerun a failed array, commit O8v2, create its tag, publish refs,
bootstrap, or start any v8 process. Preserve the evidence and preregister any corrected
attempt; a partial or failed sequence is not O8v2.

Only after every check passes, commit all and only the fifteen additions as the direct child
of P8v5 and create the new lightweight
`action-qbc-v8-open-diagnostic-freeze-v2` tag at that exact O8v2 commit. The immutable
freeze-v1 tag remains at O8v1 and the reserved result-v1 tag remains absent. While the
repository is still PRIVATE, use one non-force atomic push of the existing branch and new
freeze-v2 tag from the original Windows checkout:

```json
["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-C","D:\\kaggle competitions\\arc3-crosslevel-voi","push","--atomic","origin","refs/heads/action-qbc-v8-prereg:refs/heads/action-qbc-v8-prereg","refs/tags/action-qbc-v8-open-diagnostic-freeze-v2:refs/tags/action-qbc-v8-open-diagnostic-freeze-v2"]
```

The repository must remain PRIVATE through that successful atomic push. A push failure,
non-atomic outcome, unexpected ref, or uncertainty stops O8v2 before any visibility change;
the push is never retried. After success, with no intervening visibility, connectivity, API,
browser, authenticated-ref, SSH, or anonymous-ref query, the interactive repository owner
uses this exact GitHub CLI executable once:

```text
path:        C:\Program Files\GitHub CLI\gh.exe
version:     2.96.0
byte count:  41504056
SHA-256:     cd79f16203f1fbe56937c4c96e2b6eadd10549418dcb241d91576ac77af0ac8b
```

```json
["C:\\Program Files\\GitHub CLI\\gh.exe","repo","edit","bansarinejad/arc3-crosslevel-voi","--visibility","public","--accept-visibility-change-consequences"]
```

This is the sole authorized PRIVATE-to-PUBLIC transition. The invocation counts whether it
succeeds or fails and is never repeated, replaced, queried, or repaired. A nonzero, failed,
timed-out, ambiguous, already-PUBLIC, or uncertain outcome stops before anonymous checking
and bootstrap. After a normal successful return, visibility remains PUBLIC continuously
through anonymous checking, bootstrap, execution, R8v2 publication, and final remote result
verification.

Immediately after that successful visibility mutation, the next protocol network action is
one independent, credential-disabled read of the literal public HTTPS URL from neutral WSL
cwd `/mnt/d/kaggle competitions` using an empty environment:

```json
["C:\\Windows\\System32\\wsl.exe","-d","Ubuntu","--cd","D:\\kaggle competitions","--","/usr/bin/env","-i","GIT_CONFIG_COUNT=0","GIT_CONFIG_GLOBAL=/dev/null","GIT_CONFIG_NOSYSTEM=1","GIT_NO_REPLACE_OBJECTS=1","GIT_TERMINAL_PROMPT=0","HOME=/home/bansarinejad","LANG=C","LC_ALL=C","PATH=/usr/local/bin:/usr/bin:/bin","XDG_CONFIG_HOME=/nonexistent","/usr/bin/git","--no-replace-objects","-c","credential.interactive=never","-c","core.askPass=","-c","credential.helper=","ls-remote","--refs","https://github.com/bansarinejad/arc3-crosslevel-voi.git","refs/heads/action-qbc-v8-prereg","refs/tags/action-qbc-v8-open-diagnostic-freeze-v2"]
```

Parse stdout as records, not presentation order. Its exact set must be the two requested
refs, each once at the same recorded lowercase 40-hex O8v2 commit; stderr must be empty and no
peeled or additional record is accepted. Neither the atomic push nor this independent
read-only check is a frozen scientific command, a remote-rehearsal query, or authorization
to embed an authentication token, password, askpass program, or other secret. Failure stops
before bootstrap and consumes the sole check; it is never retried. Do not execute a v8
supervisor, verifier, lifecycle driver, runner, validator, or finalizer until the exact
two-ref check passes.

## 2. Read-only host preflight

Use only the interactive Windows user context. Verify the registered raw hashes and
versions for `wsl.exe`, Windows Python, Windows Git, `taskkill.exe`, Ubuntu, the kernel, and
all seven Linux tools. Every Windows-to-Linux command must have this outer form:

```json
["C:\\Windows\\System32\\wsl.exe","-d","Ubuntu","--cd","<REGISTERED_LINUX_CWD>","--","<INNER_ARGV...>"]
```

The observed default WSL distribution is not an authorization. Bare `wsl.exe` is
forbidden. Any mismatch stops v8 before bootstrap and requires a new preregistration.
The exact registered `uv --version` stdout is
`uv 0.11.28 (x86_64-unknown-linux-gnu)\n`; the platform suffix and final LF are binding.

## 3. One-shot authority bootstrap

From explicit Ubuntu with cwd `/var/tmp`, execute the registered bootstrap argv arrays in
order. They require the execution root to be absent, create it and the authority destination
mode 0700, clone the O8v2 tag from the fixed local `file:///mnt/d/...` URL, check out detached
O8v2 as untrusted materialization, remove `origin`, install the exact closed seven-key local
Git mapping, rerun raw validation with replacement objects disabled, and print only the
expected O8v2 SHA.

Pass these arrays directly, in order, without shell retokenization; replace only the
registered `<O8_COMMIT>` placeholder with the recorded O8v2 SHA:

```json
["/usr/bin/test","!","-e","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open"]
["/usr/bin/install","-d","-m","700","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open"]
["/usr/bin/install","-d","-m","700","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/authority"]
["/usr/bin/git","--no-replace-objects","clone","--no-local","--no-checkout","--branch","action-qbc-v8-open-diagnostic-freeze-v2","--single-branch","file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/authority"]
["/usr/bin/git","--no-replace-objects","-C","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/authority","config","--local","core.autocrlf","false"]
["/usr/bin/git","--no-replace-objects","-C","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/authority","config","--local","core.eol","lf"]
["/usr/bin/git","--no-replace-objects","-C","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/authority","config","--local","core.safecrlf","true"]
["/usr/bin/git","--no-replace-objects","-C","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/authority","checkout","--detach","<O8_COMMIT>"]
["/usr/bin/git","--no-replace-objects","-C","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/authority","remote","remove","origin"]
["/usr/bin/git","--no-replace-objects","-C","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/authority","rev-parse","HEAD"]
```

There is no bootstrap cleanup or retry. A partial root, unexpected stdout, nonzero exit,
wrong mode, wrong owner, symlink ancestor, or wrong HEAD leaves v8 unarmed and requires a
new preregistration.

Before preparation, from the authority clone run exactly:

```text
/usr/bin/python3 -I -B scripts/reconstruct_action_qbc_v8_open_registration.py --repository-root . --registration artifacts/action_qbc_v8_open_registration.json --verify-open-freeze
```

## 4. One-shot preparation and independent gate

From the authority clone invoke preparation once:

```json
["/usr/bin/python3","-I","-B","scripts/prepare_action_qbc_v8_open.py","prepare","--repository-root",".","--registration","artifacts/action_qbc_v8_open_registration.json","--execution-root","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open","--receipt","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/preparation-receipt.json"]
```

The program owns at most two internal attempts. It must atomically promote both fresh
process clones and both empty output parents together. Do not manually clean, repair, or
repeat preparation. Every child uses the registered empty-built environment and command
policy. The preparation receipt embeds the exact nineteen-key actual command ledger,
compact distribution inventories, complete `.venv` materialization hashes, resolved Python
hashes, and root identities; a digest without its registered preimage is not sufficient.

After a zero exit, authority invokes the independent post-preparation gate once:

```json
["/usr/bin/python3","-I","-B","scripts/reconstruct_action_qbc_v8_open_registration.py","--repository-root",".","--registration","artifacts/action_qbc_v8_open_registration.json","--verify-preparation","--preparation-receipt","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/preparation-receipt.json","--verification-receipt","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/preparation-verification.json"]
```

The Windows supervisor is forbidden unless both commands exit zero and the canonical
preparation-v2 and success-only preparation-verification receipts reopen and validate.
A complete canonical `status=failed` preparation receipt remains retained preclaim evidence
but is not lifecycle-eligible and cannot authorize verification, arming, science, or a
result. If encountered after an already irreversible Windows claim, finalization embeds its
exact readable/hash triple and maps it to `preparation_receipt_invalid`; it is never replaced
with null merely because its status is failed.

## 5. Sole Windows supervisor

Return to the original clean O8v2 Windows checkout. Confirm that all four external Windows
claim/receipt paths are absent. Invoke the exact registered supervisor argv once from
`D:\kaggle competitions\arc3-crosslevel-voi`.

Before accepting any original-checkout Git evidence, both Windows processes independently
enforce the registered fifteen-key `windows_repository_contract`: the exact ancestor/root,
Git/common/index paths, exact 846-byte config and 240-byte info/exclude hashes, exact
nineteen-key normalized local config, ordinary stage-zero O8v2 index, plain non-reparse admin
directories, inactive hooks, and absence of every registered alternate, graft, shallow,
replacement, sparse/worktree/common-dir, lock, or promisor source. Every Windows
original-checkout/local-identity Git argv begins with the frozen executable followed
immediately by `--no-replace-objects --no-optional-locks`. The neutral-cwd online
`ls-remote` attempt retains its separately registered credential-hardened argv and does not
carry `--no-optional-locks`.

```json
["C:\\Users\\User\\anaconda3\\python.exe","-I","-B","scripts\\supervise_action_qbc_v8_remote_tag.py","--repository-root",".","--registration","artifacts\\action_qbc_v8_open_registration.json","--claim","D:\\kaggle competitions\\arc3-crosslevel-voi-action-qbc-v8-remote-verification-claim.json","--verifier-start-claim","D:\\kaggle competitions\\arc3-crosslevel-voi-action-qbc-v8-remote-verifier-start-claim.json","--remote-receipt","D:\\kaggle competitions\\arc3-crosslevel-voi-action-qbc-v8-remote-verification.json","--supervisor-receipt","D:\\kaggle competitions\\arc3-crosslevel-voi-action-qbc-v8-remote-verification-supervisor.json","--verifier-python","C:\\Users\\User\\anaconda3\\python.exe","--git-executable","C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--taskkill-executable","C:\\Windows\\System32\\taskkill.exe","--verifier-child-deadline-seconds","430","--supervisor-deadline-seconds","480","--child-cleanup-timeout-seconds","30"]
```

Claim creation is the irreversible v8 lifecycle boundary. The supervisor starts at most one
verifier child. Do not invoke the verifier directly, repeat the supervisor, remove a claim,
or perform another online rehearsal. If the lifecycle claim was not created, stop at O8v2 and
preregister any later attempt. If it exists after the supervisor returns, continue exactly
once with the Linux driver even when verification failed. A child created before Job
assignment/resume failure is recorded as `post_spawn_initialization_failed` after passed
cleanup, while bounded capture failure after passed cleanup is `stream_capture_failed`;
failed required cleanup takes precedence as `child_cleanup_failed`. Neither new terminal
classification is retryable.

An `overall_deadline` remote attempt records the actual unclamped interval through cleanup
and is canonical only when its nonnegative duration is at least 120,000 milliseconds.
Exactly 120,000 milliseconds and arbitrarily larger cleanup-overrun durations are valid;
there is no configured-deadline addition, clamp, or upper bound.

## 6. Sole Linux lifecycle driver

From Windows, use the explicit Ubuntu launcher and authority cwd to invoke the registered
`execute` argv for `scripts/execute_action_qbc_v8_open_lifecycle.py` once. The driver owns:

```json
["/usr/bin/python3","-I","-B","scripts/execute_action_qbc_v8_open_lifecycle.py","execute","--repository-root",".","--registration","artifacts/action_qbc_v8_open_registration.json","--execution-root","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open","--preparation-receipt","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/preparation-receipt.json","--preparation-verification-receipt","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/preparation-verification.json","--windows-claim","/mnt/d/kaggle competitions/arc3-crosslevel-voi-action-qbc-v8-remote-verification-claim.json","--remote-claim","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/remote-verification-claim.json","--remote-verifier-claim","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/remote-verifier-start-claim.json","--remote-receipt","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/remote-verification.json","--remote-supervisor-receipt","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/remote-verification-supervisor.json","--arm-receipt","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/arm-receipt.json","--driver-claim","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/lifecycle-driver-claim.json","--ledger","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/lifecycle-ledger.json"]
```

The exact outer launcher is
`["C:\\Windows\\System32\\wsl.exe","-d","Ubuntu","--cd","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/authority","--",<the inner array above>]`;
the inner tokens are appended as separate argv members, not embedded as one string.

```text
arm -> A -> validate A -> B -> validate B -> ledger -> one finalizer attempt -> bundle -> first publication attempt
```

It skips dependent children after the first failure and never retries a child. Operators do
not supply exit codes, stages, or sequence facts. After arm, no tests, environment build,
checkout, network request, remote Git operation, source mutation, or manual result edit is
allowed before finalization finishes.

Every driver-owned GNU-timeout wrapper omits `--foreground`. The driver creates and owns a
fresh session/process group for each child class, requires every Python/scientific/Git
descendant to remain in that group, and confirms the group empty—using its bounded
TERM/KILL cleanup when needed—before advancing. A cleanup failure is terminal.
Finalizer return zero or nonzero may truthfully retain `finalizer_child_cleanup_passes=true`
when a lingering same-PGID descendant was conclusively removed. The sole normal/emergency
coexistence override is return zero with a canonical normal bundle and failed outer cleanup:
the driver preserves the normal bytes, creates and selects only a
`child_cleanup_failed` emergency bundle, and starts no publisher or later child.

An exogenous kill, host shutdown, hardware failure, or corruption of the driver itself can
strand v8 after claim creation. That is not recoverable by another driver or scientific
start and requires a separately preregistered disclosure.

## 7. Publication-only recovery

If the driver returned after producing an immutable normal or emergency bundle but did not
finish the authoritative result tag, the only permitted recovery is the registered
`publish` subcommand. It may be repeated. It cannot invoke arm, science, validation,
finalization, rendering, or any network command. It validates owner state, cleans only
verified-owned scratch, reconstructs the exact R8 object, and atomically creates or accepts
the exact lightweight result tag.

From the authority cwd, use this exact inner argv under the explicit Ubuntu launcher:

```json
["/usr/bin/timeout","--signal=TERM","--kill-after=5s","600s","/usr/bin/python3","-I","-B","scripts/execute_action_qbc_v8_open_lifecycle.py","publish","--repository-root",".","--registration","artifacts/action_qbc_v8_open_registration.json","--driver-claim","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/lifecycle-driver-claim.json","--lifecycle-ledger","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/lifecycle-ledger.json","--finalization-bundle","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/finalization-bundle.json","--emergency-bundle","/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/emergency-result-bundle.json","--control-time-seconds","570"]
```

Never move, replace, or delete P8, O8v1, O8v2, R8v2, any claim, any receipt, a bundle, a ledger, or a
tag.

## 8. Transfer and online publication

Only after the authority result tag resolves to the independently reconstructed R8, use the
two registered explicit-Ubuntu local fetch commands to transfer the result branch alias and
tag into the original checkout. Verify both local refs equal R8. Then use Windows Git for
the two registered pushes and the final `ls-remote --refs` check.

```json
["/usr/bin/git","--no-replace-objects","-C","/mnt/d/kaggle competitions/arc3-crosslevel-voi","fetch","--no-tags","file:///var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/authority","refs/tags/action-qbc-v8-open-diagnostic-result-v2:refs/heads/action-qbc-v8-open-diagnostic-result"]
["/usr/bin/git","--no-replace-objects","-C","/mnt/d/kaggle competitions/arc3-crosslevel-voi","fetch","--no-tags","file:///var/tmp/arc3-crosslevel-voi-action-qbc-v8-open/authority","refs/tags/action-qbc-v8-open-diagnostic-result-v2:refs/tags/action-qbc-v8-open-diagnostic-result-v2"]
["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","push","origin","refs/heads/action-qbc-v8-open-diagnostic-result:refs/heads/action-qbc-v8-open-diagnostic-result"]
["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","push","origin","refs/tags/action-qbc-v8-open-diagnostic-result-v2:refs/tags/action-qbc-v8-open-diagnostic-result-v2"]
["C:\\Users\\User\\anaconda3\\Library\\bin\\git.exe","--no-replace-objects","--no-optional-locks","-c","credential.interactive=never","ls-remote","--refs","origin","refs/heads/action-qbc-v8-open-diagnostic-result","refs/tags/action-qbc-v8-open-diagnostic-result-v2"]
```

The expected final remote output has exactly two records—the result branch and result tag—at
the same lowercase 40-hex R8 commit. No result file is copied into a worktree, no checked-out
branch is updated, and no second finalizer or scientific command is permitted.
