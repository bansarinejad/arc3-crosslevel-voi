# Action-QBC v5 sealed-audit operator runbook

This runbook is the only supported procedure for the irreversible two-start audit.
It applies after the registration commit and tag exist. The exact ref preflight and two
canonical clone commands may perform only opaque Git ref advertisement, object transport,
and checkout. Apart from that narrow mechanical exception, no operator or other tool may
directly inspect, stat, independently hash, search, parse, execute, or semantically access
the registered lockbox outside the two permit-bound commands.

## Fixed values

```sh
set -eu
export AUDIT_ROOT='/var/tmp/arc3-crosslevel-voi'
export REPOSITORY_URL='file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi'
export FREEZE_TAG='action-qbc-v5-audit-freeze-v1'
export PRIMARY_ROOT='/var/tmp/arc3-crosslevel-voi/action-qbc-v5-primary'
export REPLICA_ROOT='/var/tmp/arc3-crosslevel-voi/action-qbc-v5-replica'
export PERMIT_ROOT='/var/tmp/arc3-crosslevel-voi/action-qbc-v5-audit-permits-v1'
export PRIMARY_OUTPUT_ROOT='/var/tmp/arc3-crosslevel-voi/action-qbc-v5-primary-output'
export REPLICA_OUTPUT_ROOT='/var/tmp/arc3-crosslevel-voi/action-qbc-v5-replica-output'
export PRIMARY_OUTPUT='/var/tmp/arc3-crosslevel-voi/action-qbc-v5-primary-output/sealed/action_qbc_v5_scientific_payload.json'
export REPLICA_OUTPUT='/var/tmp/arc3-crosslevel-voi/action-qbc-v5-replica-output/sealed/action_qbc_v5_scientific_payload.json'
```

Use native Linux or WSL2, CPython 3.12, and exactly `uv 0.11.28`. This machine uses a
credential-free `file://` transport from the already-pushed, freeze-tagged normal
repository. The transport source is the sole `/mnt/*` exception: under WSL2, the common
root, both cloned object stores and worktrees, virtual environments, outputs, permits,
and every evidentiary file must remain on the Linux filesystem under `/var/tmp`.
Stop if any fixed root, permit directory, output, repository result, or receipt already
exists. Never delete, replace, repair, or recreate permit, marker, ledger, proof,
raw-output, or receipt state.

Before creating any canonical Linux state, the freeze tag must already be pushed to
GitHub and independently verified there. In the trusted Windows repository, obtain the
single commit hash with `git ls-remote origin refs/tags/action-qbc-v5-audit-freeze-v1`
and export that exact value into the WSL shell as `GITHUB_FREEZE_COMMIT`. The freeze tag
must be lightweight; annotated tags are rejected. Confirm that the read-only local
transport publishes the identical lowercase 40-hex ref. This reads Git objects, not the
sealed working-tree artifact:

```sh
: "${GITHUB_FREEZE_COMMIT:?export the independently verified GitHub freeze commit}"
test "${#GITHUB_FREEZE_COMMIT}" -eq 40
case "$GITHUB_FREEZE_COMMIT" in
  *[!0-9a-f]*) exit 1 ;;
esac
set -- $(git ls-remote "$REPOSITORY_URL" \
  "refs/tags/$FREEZE_TAG" "refs/tags/$FREEZE_TAG^{}")
test "$#" -eq 2
test "$2" = "refs/tags/$FREEZE_TAG"
test "${#1}" -eq 40
case "$1" in
  *[!0-9a-f]*) exit 1 ;;
esac
test "$1" = "$GITHUB_FREEZE_COMMIT"
export FREEZE_COMMIT="$1"
```

Create the common root once, before cloning. It must be a new, plain directory owned
by the invoking uid, mode `0700`, and empty. This step deliberately does **not**
precreate the permit directory:

```sh
umask 077
test ! -e "$AUDIT_ROOT"
test ! -L "$AUDIT_ROOT"
install -d -m 700 "$AUDIT_ROOT"
test -d "$AUDIT_ROOT"
test ! -L "$AUDIT_ROOT"
test "$(stat -c '%u:%a' "$AUDIT_ROOT")" = "$(id -u):700"
test -z "$(find "$AUDIT_ROOT" -mindepth 1 -maxdepth 1 -print -quit)"
test ! -e "$PERMIT_ROOT"
test ! -L "$PERMIT_ROOT"
```

Stop if the canonical path or its backing mount can be redirected, is shared with
another uid, or is not a local Linux filesystem. Keep the same trusted administrator,
mount namespace, and path namespace continuously through pair promotion.

## 1. Create two fresh frozen worktrees

```sh
git clone --branch "$FREEZE_TAG" --single-branch "$REPOSITORY_URL" "$PRIMARY_ROOT"
git clone --branch "$FREEZE_TAG" --single-branch "$REPOSITORY_URL" "$REPLICA_ROOT"
test "$(git -C "$PRIMARY_ROOT" rev-parse HEAD)" = "$FREEZE_COMMIT"
test "$(git -C "$REPLICA_ROOT" rev-parse HEAD)" = "$FREEZE_COMMIT"
test "$(git -C "$PRIMARY_ROOT" rev-parse "$FREEZE_TAG^{commit}")" = "$FREEZE_COMMIT"
test "$(git -C "$REPLICA_ROOT" rev-parse "$FREEZE_TAG^{commit}")" = "$FREEZE_COMMIT"

cd "$PRIMARY_ROOT"
UV_VERSION_OUTPUT="$(uv --version)"
case "$UV_VERSION_OUTPUT" in
  'uv 0.11.28'|'uv 0.11.28 '*) ;;
  *) exit 1 ;;
esac
uv sync --frozen --no-dev

cd "$REPLICA_ROOT"
UV_VERSION_OUTPUT="$(uv --version)"
case "$UV_VERSION_OUTPUT" in
  'uv 0.11.28'|'uv 0.11.28 '*) ;;
  *) exit 1 ;;
esac
uv sync --frozen --no-dev
```

Both uv identity checks must report the exact leading version tokens `uv 0.11.28`;
the platform/build suffix may differ and the launcher binds the actual executable.
Each ignored `.venv`
must contain exactly these installed distributions: editable
`arc3-crosslevel-voi==0.1.0`, `numpy==2.5.1`, and `PyYAML==6.0.3`. Its
`.venv/bin/python3` must be the expected symlink chain to the trusted CPython 3.12
base interpreter, and must resolve identically to `.venv/bin/python` and
`.venv/bin/python3.12`. The site-packages bootstrap layout must contain exactly the
editable-project `_editable_impl_arc3_crosslevel_voi.pth`, whose sole path is that
clone's literal `src` directory, plus the pinned `_virtualenv.pth` and
`_virtualenv.py`; no other `.pth` or bootstrap hook is allowed. `_virtualenv.pth`
must contain only its pinned `import _virtualenv` line, and `_virtualenv.py` must
match the pinned base-environment content.

Stop on `sitecustomize.py`, `usercustomize.py`, any unregistered executable `.pth`
line, cached bytecode, a symbolic source path, an unexpected distribution, a dirty
registered source, a tag mismatch, a changed base interpreter or uv/git executable,
or any dependency/layout difference between the clones. Do not repair an environment;
failure is terminal for this registered audit.

Do not run tests or import project modules in either clone. Precreate only the two
external output roots and their `sealed` parents. Every created component must be a
plain, empty directory owned by the invoking uid with mode `0700`, and both fixed
final outputs must remain absent:

```sh
test ! -e "$PRIMARY_OUTPUT_ROOT"
test ! -e "$REPLICA_OUTPUT_ROOT"
test ! -L "$PRIMARY_OUTPUT_ROOT"
test ! -L "$REPLICA_OUTPUT_ROOT"
install -d -m 700 "$PRIMARY_OUTPUT_ROOT"
install -d -m 700 "$REPLICA_OUTPUT_ROOT"
test -d "$PRIMARY_OUTPUT_ROOT" && test ! -L "$PRIMARY_OUTPUT_ROOT"
test -d "$REPLICA_OUTPUT_ROOT" && test ! -L "$REPLICA_OUTPUT_ROOT"
test "$(stat -c '%u:%a' "$PRIMARY_OUTPUT_ROOT")" = "$(id -u):700"
test "$(stat -c '%u:%a' "$REPLICA_OUTPUT_ROOT")" = "$(id -u):700"
test -z "$(find "$PRIMARY_OUTPUT_ROOT" -mindepth 1 -maxdepth 1 -print -quit)"
test -z "$(find "$REPLICA_OUTPUT_ROOT" -mindepth 1 -maxdepth 1 -print -quit)"
install -d -m 700 "$PRIMARY_OUTPUT_ROOT/sealed"
install -d -m 700 "$REPLICA_OUTPUT_ROOT/sealed"
test -d "$PRIMARY_OUTPUT_ROOT/sealed" && test ! -L "$PRIMARY_OUTPUT_ROOT/sealed"
test -d "$REPLICA_OUTPUT_ROOT/sealed" && test ! -L "$REPLICA_OUTPUT_ROOT/sealed"
test "$(stat -c '%u:%a' "$PRIMARY_OUTPUT_ROOT/sealed")" = "$(id -u):700"
test "$(stat -c '%u:%a' "$REPLICA_OUTPUT_ROOT/sealed")" = "$(id -u):700"
test -z "$(find "$PRIMARY_OUTPUT_ROOT/sealed" -mindepth 1 -maxdepth 1 -print -quit)"
test -z "$(find "$REPLICA_OUTPUT_ROOT/sealed" -mindepth 1 -maxdepth 1 -print -quit)"
test ! -e "$PRIMARY_OUTPUT"
test ! -e "$REPLICA_OUTPUT"
test ! -L "$PRIMARY_OUTPUT"
test ! -L "$REPLICA_OUTPUT"
test ! -e "$PERMIT_ROOT"
test ! -L "$PERMIT_ROOT"
```

The production audit entry point enforces the registered fixed primary or replica
output path before permit consumption and scientific exposure; no alternate output
token, symlink, bind mount, or namespace substitute is valid.

All lint, type, unit, and Linux integration checks must already have passed in the
normal development repository. From this point onward, a failed prerequisite is a
terminal stop—not permission to edit a bound clone or create a replacement start.

## 2. Publish the singleton two-start permit set

Run from the primary clone. This command must be the first creator of the fixed
permit directory and must report exactly the `primary` and `replica` issuance.

```sh
cd "$PRIMARY_ROOT"
uv run --frozen --no-sync python3 -I -B scripts/build_action_qbc_audit_registration.py \
  --repository-root "$PRIMARY_ROOT" \
  --prepare-permits "$PERMIT_ROOT" \
  --replica-repository-root "$REPLICA_ROOT"
```

After publication, do not run tests, synchronization, checkout, pull, cleanup, or
incidental project imports in either clone. Preserve the permit directory exactly.

## 3. Execute the primary start

The following token sequence must equal the registered command exactly:

```sh
cd "$PRIMARY_ROOT"
uv run --frozen --no-sync python3 -I -B scripts/audit_action_qbc_lockbox.py \
  --repository-root . \
  --registration artifacts/action_qbc_v5_audit_registration.json \
  --permit-record "$PERMIT_ROOT/primary.permit.json" \
  --permit-marker "$PERMIT_ROOT/primary.available" \
  --output "$PRIMARY_OUTPUT"
```

The literal `python3` token is part of the canonical registered command. `python`, an
absolute interpreter path, an alias, or any wrapper is not an equivalent substitution.

Stop unless the command exits zero and the durable execution ledger contains exactly
one canonical `primary` row. Do not inspect or edit the scientific output. A failed,
partial, or missing primary ledger row permanently blocks the replica; never create a
replacement primary or proceed speculatively.

## 4. Execute the replica start

Only after the primary row is durable:

```sh
cd "$REPLICA_ROOT"
uv run --frozen --no-sync python3 -I -B scripts/audit_action_qbc_lockbox.py \
  --repository-root . \
  --registration artifacts/action_qbc_v5_audit_registration.json \
  --permit-record "$PERMIT_ROOT/replica.permit.json" \
  --permit-marker "$PERMIT_ROOT/replica.available" \
  --output "$REPLICA_OUTPUT"
```

Stop unless the command exits zero and the ledger now contains exactly two ordered
rows plus a byte-identity pair attestation. There is no third start under any outcome.

## 5. Promote and validate without changing the bound clone

Promotion occurs in the permit-bound primary clone while its HEAD remains exactly at
the freeze tag:

```sh
cd "$PRIMARY_ROOT"
uv run --frozen --no-sync python3 -I -B scripts/build_action_qbc_audit_registration.py \
  --repository-root "$PRIMARY_ROOT" \
  --promote-pair
```

This must create and validate both:

- `artifacts/action_qbc_v5_sealed_audit.json`
- `artifacts/action_qbc_v5_sealed_audit_receipt.json`

If an earlier promotion process was killed between staging and publication, this
same command may remove only its exact owner-only, non-evidentiary staging-temp
namespace while holding the promotion lock. The operator must never delete or edit
those staging files manually.

Leave the primary and replica clones at the freeze tag with all external permits,
markers, ledger rows, proofs, and raw outputs preserved. Never commit in either bound
clone: changing its HEAD makes receipt revalidation impossible. The receipt loader
remains bound to the permit-bound primary root and must only be run there.

Prepare the normal result repository as a separate clean checkout whose `HEAD` is
exactly the freeze-tag commit. The post-audit result commit must be a direct child of
that commit. Before copying, require a completely empty `git status`, absent result
destinations, and the exact freeze-tag identity. Copy only these two byte-exact files
from the bound primary clone:

- `artifacts/action_qbc_v5_sealed_audit.json`
- `artifacts/action_qbc_v5_sealed_audit_receipt.json`

The only additional path allowed in that direct-child commit is one explicitly new
result document: `docs/action_qbc_v5_sealed_audit_result.md`. Do not edit the README,
source, tests, registration, lockbox, runbook, or hash-frozen
`docs/experiment_protocol.md`. With `NORMAL_RESULT_ROOT` already set to that separate
checkout, perform the copy and byte/hash checks without invoking project code:

```sh
: "${NORMAL_RESULT_ROOT:?set NORMAL_RESULT_ROOT to the clean result checkout}"
cd "$NORMAL_RESULT_ROOT"
FREEZE_COMMIT="$(git rev-list -n 1 "$FREEZE_TAG")"
test "$(git rev-parse HEAD)" = "$FREEZE_COMMIT"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
test ! -e artifacts/action_qbc_v5_sealed_audit.json
test ! -e artifacts/action_qbc_v5_sealed_audit_receipt.json
test ! -e docs/action_qbc_v5_sealed_audit_result.md
test ! -L artifacts/action_qbc_v5_sealed_audit.json
test ! -L artifacts/action_qbc_v5_sealed_audit_receipt.json
test ! -L docs/action_qbc_v5_sealed_audit_result.md
cp --no-clobber "$PRIMARY_ROOT/artifacts/action_qbc_v5_sealed_audit.json" \
  artifacts/action_qbc_v5_sealed_audit.json
cp --no-clobber "$PRIMARY_ROOT/artifacts/action_qbc_v5_sealed_audit_receipt.json" \
  artifacts/action_qbc_v5_sealed_audit_receipt.json
cmp --silent "$PRIMARY_ROOT/artifacts/action_qbc_v5_sealed_audit.json" \
  artifacts/action_qbc_v5_sealed_audit.json
cmp --silent "$PRIMARY_ROOT/artifacts/action_qbc_v5_sealed_audit_receipt.json" \
  artifacts/action_qbc_v5_sealed_audit_receipt.json
sha256sum "$PRIMARY_ROOT/artifacts/action_qbc_v5_sealed_audit.json" \
  artifacts/action_qbc_v5_sealed_audit.json
sha256sum "$PRIMARY_ROOT/artifacts/action_qbc_v5_sealed_audit_receipt.json" \
  artifacts/action_qbc_v5_sealed_audit_receipt.json
```

In the normal repository, use only those byte and SHA-256 comparisons against the
bound-primary copies; do not invoke the bound receipt loader there. After creating
the optional exact result-document path and committing only the two artifacts plus
that document, verify `git rev-parse HEAD^` equals `$FREEZE_COMMIT` and inspect
`git diff-tree --no-commit-id --name-only -r HEAD` before any push. A mismatch or
extra path is a terminal stop, not permission to amend or rewrite the audit history.

Scientific acceptance and pair integrity are separate. A byte-identical promoted
negative payload remains negative evidence and does not enable runtime-v5. Runtime-v5
stays disabled until all later admission gates, including the separate trusted live
`RunContractExpectation`, pass.

## Trust boundary

The exact-two claim assumes one continuously trusted Linux host and administrator
from common-root creation through successful pair promotion. Throughout that entire
interval, only the exact ref preflight and two canonical clone commands may perform
opaque Git ref advertisement, object transport, and checkout that mechanically
materializes committed bytes. They must perform no direct path-oriented operator/tool
inspection, stat, independent hash, search, parse, execution, or semantic access. Outside
that narrow transport exception and the two permit-and-capability-bound starts, all
registered-lockbox content access is forbidden. There must also be no deletion, rollback,
modification, forgery, replacement, repair, time-of-check/time-of-use swap, mount or
path-namespace substitution, or same-process injection affecting either worktree; either
`.venv`; the trusted base interpreter; the uv or git executable; registered source, tag,
or configuration; permits and availability/consumption markers; ledgers, capabilities,
attestations, and launcher proofs; raw outputs and their parent directories; promoted
artifacts; or receipts. Ownership, modes, symlink targets, executable identities, process
ancestry, and namespace bindings must remain stable through promotion.

The mechanism is procedural integrity evidence, not protection against a hostile
local administrator, compromised host, or same-process code injection.
