# Action-QBC v7 open-diagnostic result

Date: 11 August 2026

The preregistered v7 lifecycle terminated at its first administrative boundary, before
either scientific process began. The exact WSL2 remote-tag verification command produced no
stdout before the host command supervisor terminated it with exit code 124 after approximately
64 seconds. The frozen protocol maps that outcome to `tag_verification_failed`, forbids a
retry, and requires every remaining setup and scientific command to be skipped.

This is an administrative terminal, not scientific evidence about action-conditional QBC,
cross-level value of information, or the v7 failure decomposition.

## Known frozen identity

The following values were established at the freeze and independently observed before the
registered lifecycle. They are contextual identities, not fields validated or populated by
the administrative-terminal artifact.

- Treatment: `action-qbc-v7-open-failure-decomposition-v1`
- Preregistration commit: `f4a267757a7abbd72bc1aeb86e98811c521bf574`
- Preregistration tag: `prereg-action-qbc-v7-open-failure-decomposition-v1`
- Open-freeze commit: `851fb6dadc851d17ba9540165f48570ee4203ded`
- Open-freeze tag: `action-qbc-v7-open-diagnostic-freeze-v1`
- Registration content SHA-256: `b09f9ee3b778222afd474645e64512ddc5abc3b6b326a2af9619ee016452a825`
- Registration file SHA-256: `69520f0aa1eeb8ee38e744669a66e443c3e0637e4448200331f9ae6099ae499f`
- Platform used for the attempted lifecycle boundary: WSL2 Ubuntu 24.04.1, x86-64

Before the irreversible lifecycle began, the freeze branch and lightweight freeze tag were
published to GitHub and independently observed from the Windows checkout at the same commit.
That earlier observation cannot replace, repair, or justify retrying the separately registered
WSL2 verification step.

The finalizer left `open_freeze_commit_sha` and `registration_content_sha256` null. Its
original-checkout source-manifest validation encountered four tracked JSON files materialized
with CRLF bytes even though Git reported a clean worktree, while the registered manifest binds
their LF bytes:

- `artifacts/model_gate_live8.json`
- `artifacts/model_gate_live8_pre_grounding.json`
- `artifacts/prompt_grounding_bp35_seed11.json`
- `artifacts/public_games.snapshot.json`

LF-normalizing each file reproduces its registered byte count and SHA-256. This checkout-byte
mismatch does not change the already selected `tag_verification_failed` stage, which has
precedence, and the frozen lifecycle permits neither repair nor another finalizer invocation.

## Lifecycle disposition

- First terminal stage: `tag_verification_failed`
- Process A: not started; exit code `null`; no output
- Process B: not started; exit code `null`; no output
- Execution root: not created
- Per-process environments and preflights: not started
- Scientific evaluator starts: zero
- Third scientific start: zero and permanently prohibited
- Finalizer invocations: exactly one; exit code 0
- Canonical payload: absent
- Receipt: absent
- Runtime, lockbox, sealed-execution, and final-admission authorization: all false

The one-shot standard-library finalizer created only
[`action_qbc_v7_open_diagnostic_administrative_terminal.json`](../artifacts/action_qbc_v7_open_diagnostic_administrative_terminal.json).
The artifact is 1,030 bytes with SHA-256
`90826498333079cfe7640c21b618fc03f0ee32e53ea5e80ba1b8b72f542792ba`.
Its registered stage is `tag_verification_failed`; both process records contain null exit
codes and absent payloads.

## Scientific interpretation and decision

V7 produced no observations, so it cannot confirm, reject, weaken, or rescue any mechanism
claim. The frozen v6 negative remains the latest scientific evidence. No leaderboard,
paper, mechanism-freeze, runtime-admission, or sealed-evidence claim may treat this terminal
as a completed v7 diagnostic.

The v7 lifecycle must not be repaired or rerun. Any further attempt requires a newly
preregistered treatment and new immutable Git boundaries; it must explicitly register the
remote-verification supervision policy before scientific execution.
