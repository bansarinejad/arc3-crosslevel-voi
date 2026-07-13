# Action-QBC v5 sealed-audit result

Date: 13 July 2026

The registered two-start audit completed, reproduced byte-for-byte, and failed its
scientific mechanism gate. This is negative evidence. It does not authorize runtime-v5,
development-matrix execution, model use, gameplay, or any positive cross-level-QBC claim.

## Frozen identity and pair integrity

- Freeze commit: `c7c9c9bc4475a54fc325ce9c9104c4188889221f`
- Freeze tag: `action-qbc-v5-audit-freeze-v1`
- Registration content SHA-256:
  `978e3ed2e2eecda623a03b21792ba67af280a4573ebbafbb43a53b666e523c89`
- Registration file SHA-256:
  `1d13a85df3a49a8eb4805b6ad2ee8d1b285148b33f4e1e1b681b33605609f4ff`
- Frozen 48-file source manifest SHA-256:
  `421b618c0ddedfdd0187cb8927bd20c8ddfe554cf636ff5f6467e0fad0b74328`
- Permit issuance:
  `c9c3ff2d53420b185cf456732fe90c7efab8a1f2043a560aaf223c391c4f9faf`
- Starts consumed: exactly two, ordered `primary` then `replica`; both exited zero.
- Pair disposition: `verified-positive-byte-identical-pair`, scoped to pair integrity only.
- Scientific payload SHA-256, identical in both starts:
  `7bc157bd820449f09e81fbf33926e21d6be09056cdf8c729d50eb60e51b1040c`
- Scientific payload size: 164,191 bytes.
- Promotion receipt SHA-256:
  `936044a48438ea8c7ba3197128b7a1036b5a8a7016fef3c244001353d6aa46dc`
- Two-row ledger SHA-256:
  `7ae73a3b7ab3a78a0b1249f5c427aafc6386a2d193f7cf1d96bb9fd196b6d06d`

The validated evidence is preserved in
[`action_qbc_v5_sealed_audit.json`](../artifacts/action_qbc_v5_sealed_audit.json) and
[`action_qbc_v5_sealed_audit_receipt.json`](../artifacts/action_qbc_v5_sealed_audit_receipt.json).

## Scientific disposition

Both starts independently produced
`mechanism_capability_failed_runtime_v5_frozen`. The authoritative acceptance record has
`acceptance_passes=false`, `final_admission_claimed=false`, and
`runtime_v5_enabled=false`.

Evidence that completed successfully:

- Exact 140-record inventory, registered exposure, wall-time limit, and all resource
  counters matched.
- All 20 fixed controls passed.
- The evaluator performed the registered 60 compiler/planner snapshots, 48 candidate
  builds, 96 controller replays, 12 v4 counterfactuals, 235 pure-selector calls, and 480
  isolated worker starts.
- Model calls, generated tokens, GPU operations, environment actions, network calls,
  reward observations, and RHAE observations were all zero.

Failure shape:

- Each of the 12 scene blocks recorded one `ValueError` at
  `scientific_record_finalization_failed`, followed by
  `scientific_rows_not_completed`.
- The 12 base, 48 visual-transform, and 60 order-transform records were therefore frozen
  as incomplete; all 60 pipeline-bearing rows report `not_completed`.
- Positive and causal totals are zero in every registered family.
- Structural, visual, order, causal-minimum, positive-minimum, and finalization checks
  failed. No exception message was exposed by the preregistered redaction contract, so
  this result establishes the failure boundary but not a more specific root cause.

## Decision

Runtime-v5 remains hard-disabled. There is no third registered start and the frozen
primary/replica worktrees, permits, markers, ledger, raw outputs, promoted files, and
receipt must remain untouched. Any diagnosis must use open fixtures only. Any revised
mechanism must receive a new preregistration, new treatment identity, and new independent
evidence; this audit cannot be reinterpreted or repaired into a positive result.
