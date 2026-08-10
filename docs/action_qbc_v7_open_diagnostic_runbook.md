# Action-QBC v7 open-diagnostic operator runbook

This is the only supported procedure for the irreversible two-process v7 open diagnostic.
Use native Linux or WSL2. Do not begin until the clean open-freeze commit `O` has been tagged
and pushed under the lightweight tag `action-qbc-v7-open-diagnostic-freeze-v1`.

The two scientific processes are observations `A` and `B` of one deterministic treatment.
They run sequentially from separate clones and separately synchronized environments. There
is no third process, retry, repair, alternate command, alternate environment, or post-freeze
source/schema change. A scientific negative or registered scientific fallback is a valid
zero-exit payload. An administrative failure is terminal.

## Fixed identities and paths

```text
repository URL: file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi
GitHub URL: https://github.com/bansarinejad/arc3-crosslevel-voi.git
freeze tag: action-qbc-v7-open-diagnostic-freeze-v1
execution root: /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open
process A clone: /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a
process B clone: /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b
process A output: /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a-output/open/action_qbc_v7_open_diagnostic.json
process B output: /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b-output/open/action_qbc_v7_open_diagnostic.json
finalizer cwd: /mnt/d/kaggle competitions/arc3-crosslevel-voi
```

The scientific compute, CLI wall, and shell hard limits are respectively 2,100, 2,400, and
2,700 seconds. The final 300 seconds inside the CLI are reserved for authoritative assembly,
validation, and publication.

## 1. Verify the remote lightweight tag

From cwd `/var/tmp`, execute this exact argv:

```json
["git","ls-remote","--tags","https://github.com/bansarinejad/arc3-crosslevel-voi.git","refs/tags/action-qbc-v7-open-diagnostic-freeze-v1"]
```

The command must exit zero and emit exactly one line:

```text
<O_COMMIT>\trefs/tags/action-qbc-v7-open-diagnostic-freeze-v1
```

Here `\t` and `\n` denote the one tab and final line-feed bytes. Substitute the observed
lowercase 40-hex commit for every later `<O_COMMIT>`. Reject zero lines, multiple lines, a
non-40-hex commit, or any peeled `^{}` ref. Record lifecycle stage
`tag_verification_failed` on failure and skip every remaining setup/scientific command.

Before setup, `/usr/bin/python3 --version` must identify CPython 3.12. This interpreter is
administrative only; it is not either scientific environment.

## 2. Execute the registered setup steps

Set `umask 077`. Then execute the following eight step objects in order. The objects—not a
shell-variable rendering—are the registered command identities. Every command has cwd
`/var/tmp`; compare stdout exactly with the displayed expectation.

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

Setup steps 1, 2, 7, or 8 map to `execution_root_setup_failed`. Clone and clone-HEAD
steps map to `clone_a_failed` or `clone_b_failed` as applicable. Stop on the first mismatch.
Do not delete a partial root and do not try setup again.

## 3. Build and preflight process A

With cwd `/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a`, execute exactly:

```text
/usr/bin/env UV_OFFLINE=1 uv sync --python 3.12.13 --frozen --no-dev --offline
```

Its canonical argv is:

```json
["/usr/bin/env","UV_OFFLINE=1","uv","sync","--python","3.12.13","--frozen","--no-dev","--offline"]
```

Failure maps to `environment_a_failed`. On success, execute these exact preflight argv lists
in order from the same cwd:

```json
[
  ["git","status","--porcelain=v1","-z","--untracked-files=all"],
  ["git","rev-parse","HEAD"],
  [".venv/bin/python3","--version"],
  ["uv","--version"],
  [".venv/bin/python3","-I","-B","scripts/reconstruct_action_qbc_v7_open_registration.py","--repository-root",".","--registration","artifacts/action_qbc_v7_open_registration.json"]
]
```

Expected results are, in order: an empty status byte string; `<O_COMMIT>\n`;
`Python 3.12.13\n`; `uv 0.11.28\n`; and zero exit with byte equality to the registered JSON.
The reconstructor also enforces the registered Linux platform and exact three-distribution
inventory. Any mismatch maps to `preflight_a_failed` and terminates the lifecycle.

No test, project import, compiler, planner, selector, controller, or scientific evaluator may
run in this clone before its registered scientific process.

## 4. Run process A

From the process-A clone, execute exactly:

```text
/usr/bin/timeout --foreground --signal=TERM --kill-after=15s 2700s \
  .venv/bin/python3 -I -B scripts/run_action_qbc_v7_open_diagnostic.py \
  --repository-root . \
  --registration artifacts/action_qbc_v7_open_registration.json \
  --compute-deadline-seconds 2100 \
  --wall-time-seconds 2400 \
  --output /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a-output/open/action_qbc_v7_open_diagnostic.json
```

The exact argv is:

```json
["/usr/bin/timeout","--foreground","--signal=TERM","--kill-after=15s","2700s",".venv/bin/python3","-I","-B","scripts/run_action_qbc_v7_open_diagnostic.py","--repository-root",".","--registration","artifacts/action_qbc_v7_open_registration.json","--compute-deadline-seconds","2100","--wall-time-seconds","2400","--output","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a-output/open/action_qbc_v7_open_diagnostic.json"]
```

Record the non-negative decimal exit code exactly. Continue only if it is zero and the fixed
output exists; the runner itself publishes only after canonical schema validation and cap
validation. A nonzero exit maps to `process_a_nonzero`; a zero exit without output maps to
`process_a_output_missing`. An invalid payload later maps to `process_a_payload_invalid`.
Do not start B after a nonzero or missing A result.

## 5. Build, preflight, and run process B

Only after A satisfies the preceding boundary, use cwd
`/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b` and execute the same exact
environment-build argv from section 3. Failure maps to `environment_b_failed`. Then execute
the same five exact preflight argv lists from section 3 in this clone. Their expected values
are identical; failure maps to `preflight_b_failed`.

On success, execute exactly:

```text
/usr/bin/timeout --foreground --signal=TERM --kill-after=15s 2700s \
  .venv/bin/python3 -I -B scripts/run_action_qbc_v7_open_diagnostic.py \
  --repository-root . \
  --registration artifacts/action_qbc_v7_open_registration.json \
  --compute-deadline-seconds 2100 \
  --wall-time-seconds 2400 \
  --output /var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b-output/open/action_qbc_v7_open_diagnostic.json
```

The exact argv is:

```json
["/usr/bin/timeout","--foreground","--signal=TERM","--kill-after=15s","2700s",".venv/bin/python3","-I","-B","scripts/run_action_qbc_v7_open_diagnostic.py","--repository-root",".","--registration","artifacts/action_qbc_v7_open_registration.json","--compute-deadline-seconds","2100","--wall-time-seconds","2400","--output","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b-output/open/action_qbc_v7_open_diagnostic.json"]
```

Record B's exit code. A nonzero exit maps to `process_b_nonzero`; a zero exit without output
maps to `process_b_output_missing`; later invalidation maps to `process_b_payload_invalid`.
There is no third scientific command under any outcome.

## 6. Invoke the finalizer exactly once

Return to the original clean checkout at exactly
`/mnt/d/kaggle competitions/arc3-crosslevel-voi`. Do not use either process clone. Invoke the
standard-library-only finalizer once, including a lifecycle that failed before A or B began:

```text
/usr/bin/python3 -I -B scripts/finalize_action_qbc_v7_open_diagnostic.py \
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

The registered template argv is exactly:

```json
["/usr/bin/python3","-I","-B","scripts/finalize_action_qbc_v7_open_diagnostic.py","--repository-root",".","--registration","artifacts/action_qbc_v7_open_registration.json","--process-a","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a-output/open/action_qbc_v7_open_diagnostic.json","--process-b","/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b-output/open/action_qbc_v7_open_diagnostic.json","--process-a-exit-code","<A_EXIT_CODE>","--process-b-exit-code","<B_EXIT_CODE_OR_NULL>","--lifecycle-stage","<STAGE_OR_NULL>","--publish","artifacts/action_qbc_v7_open_diagnostic.json","--receipt","artifacts/action_qbc_v7_open_diagnostic_receipt.json","--administrative-terminal","artifacts/action_qbc_v7_open_diagnostic_administrative_terminal.json"]
```

Use lowercase ASCII `null` for an unstarted process and for no lifecycle failure stage. A
started process uses its decimal non-negative exit code. For a lifecycle failure, use exactly
the first applicable registered stage:

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

The finalizer independently validates registration, any available payloads, exact canonical
bytes, identities, hashes, cap, row inventory, evidence tables, and pair equality. It either
transactionally publishes the byte-identical process-A payload plus receipt, or exclusively
publishes the administrative terminal. It never executes scientific code and never adopts,
overwrites, or removes a foreign destination.

If it reports a result-document-only terminal because even the administrative artifact could
not be created, do not run the finalizer again. Record the exact stage and filesystem outcome
in `docs/action_qbc_v7_open_diagnostic_result.md` as required by the preregistration.

## Irreversible stop rule

Preserve the execution root, both clones, environments, external outputs, and every
repository publication path after the finalizer. Do not clean, repair, rerun, or reinterpret
the lifecycle. Commit only the mutually exclusive result path set permitted by the frozen
amendment, then create and push the lightweight result tag
`action-qbc-v7-open-diagnostic-result-v1`.
