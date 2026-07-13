# Action-QBC v6 open-gate result

Date: 14 July 2026

The preregistered three-family open matrix completed its compiler/planner work, row
accumulation, and authoritative finite-grid revalidation, then failed the required all-visual
acceptance condition. This is negative engineering evidence. Under the frozen v6 amendment,
v2 lockbox generation and every sealed v6 path are permanently cancelled.

## Frozen identity and execution

- Treatment: `action-qbc-v6-finite-grid-evidence-v1`
- Runtime identity: `crosslevel-voi-runtime-v6`
- Preregistration commit: `a7f4da2d1e4773c3396243b12e983df910941c0c`
- Preregistration tag: `prereg-action-qbc-v6-finite-grid-evidence-v1`
- Platform: WSL2 Debian, CPython 3.12.13, x86-64
- Frozen dependencies: synchronized from `uv.lock` with the development extra
- First combined Linux run: 48 tests passed and the open matrix failed in 283.94 seconds
- Authoritative diagnostic rerun: the same matrix failed in 352.07 seconds and emitted the
  exact canonical failure vector

The machine-readable result is preserved in
[`action_qbc_v6_open_gate_result.json`](../artifacts/action_qbc_v6_open_gate_result.json).

As a compatibility check, the frozen v5 suite reported 60 passes, 2 platform/environment
skips, and 2 fail-closed registration rejections because its exact 39-file source inventory
correctly refuses the two newly preregistered v6 package files. No v5 source, registration,
artifact, tag, or bound state was changed to suppress that closed-treatment guard.

## Scientific disposition

All three scenes completed five compiler/planner snapshots and ten registered scene rows.
The accumulator retained ten new indices per family, left all other placeholders unchanged,
and passed complete-inventory authoritative revalidation after each batch. Twenty controls
also completed. There was no pipeline, grid-table, transform-contract, action-map, or parity
terminal in the observed matrix.

Only 3 of 12 visual rows passed: the palette-bijection row in each family. The other nine
were ordinary `evaluated` scientific negatives:

| Family | Transform | Overflow | Canonical reasons |
|---|---|---:|---|
| homologue | translate +3,+5 | 54 | translation overflow; grid mismatch |
| homologue | translate -3,-5 | 0 | grid mismatch; selector rank; M/X utility sets |
| homologue | scale 2x | 0 | selector rank; M/X utility sets |
| containment | translate +3,+5 | 29 | translation overflow; grid mismatch; selector rank |
| containment | translate -3,-5 | 0 | grid mismatch |
| containment | scale 2x | 0 | selector rank; M/X utility sets |
| reflection | translate +3,+5 | 24 | translation overflow; grid mismatch |
| reflection | translate -3,-5 | 0 | grid mismatch |
| reflection | scale 2x | 0 | M/X utility sets |

The three positive translations recorded 107 out-of-original-frame non-background
prediction-cell occurrences over ordered action/hypothesis pairs. The negative translations
did not overflow, but their transformed predictions still differed from the padded
finite-grid relation. Scale avoided grid mismatches; M/X utility-set invariance failed in
every family, while selector/rank invariance failed in homologue and containment.

## Independent implementation audit

An independent read-only review found additional safeguards that were not complete when the
scientific gate failed:

- arbitrary addressable schema defects are not yet replaced by identity-bound
  `scientific_record_schema_invalid` rows while retaining valid siblings;
- exact 140-placeholder global fallbacks and the 67,108,863/864/865-byte cap boundaries are
  not constructed or tested end to end;
- completed visual rows do not yet have a comprehensive exact top-level schema validator;
- registration/source/fixture binding still requires a separately frozen v6 registration;
- the two-process byte-identity diagnostic, registered CLI, and open-gate attestation do not
  exist.

These gaps block a mechanism freeze independently. They do not weaken or explain away the
observed scientific negatives, which were finalized `evaluated` comparisons after successful
authoritative revalidation.

## Decision

Do not create `action-qbc-v6-mechanism-freeze-v1`. Do not implement or invoke a v2 lockbox
generator, issue a v6 permit, read a sealed fixture, or run sealed v6 evidence. No positive
finite-grid or cross-level-QBC claim may be made from v6. Any revised treatment requires a new
v7 preregistration and must address both the nine-row scientific failure vector and the
outstanding audit-boundary safeguards before evidence generation.
