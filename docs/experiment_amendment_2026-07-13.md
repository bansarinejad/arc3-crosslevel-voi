# Proposal-source experiment amendment — 13 July 2026

Status: frozen before any template-source environment action or performance run.

## Reason for the amendment

The original Qwen proposal path remains negative evidence and is not rewritten. Under the
repair-enabled v5 grounding contract, the local 4B profile retained two safe, behaviorally
distinct programs but no eligible graded-role program. The serial 9B NF4 profile passed its
compute limits at 14.20 generated tokens/second and 8.58 GiB peak VRAM, but retained no
grounded-safe program. Historical corrected committees also failed runtime admission: the
audited WSL and Windows pools had agreement 1.0, maximum EVSI 0.0, and maximum X probe
utility -1.0. The fixed-prior diagnostic remained below admission with agreement 0.84758,
maximum EVSI 0.00572 actions, and maximum X utility -0.86841.

The pre-amendment Qwen manifest at `artifacts/development_matrix.json` is byte-frozen at
SHA-256 `ea2dbc2eec0159e63452ab805545021d5101a17882402dd3bc9869fc39241147`.
It contains 180 pending rows and zero completed or active executions. It remains locked and
is neither overwritten nor silently reclassified by this amendment. Because implementation
and candidate-policy code changes in this amendment, `legacy-v1` matrices are audit-only;
`run-matrix` requires a newly hashed `source-v2` manifest.

## Frozen proposal-source factor and identities

`hypothesis_source` is a typed configuration factor with exactly these values:

- `qwen`: executable programs proposed by the frozen Qwen prompt/generation path.
- `template_v1`: deterministic scene-conditioned compiler proposals.
- `qwen_then_template_v1`: a reserved hybrid value. It is validated for M/X only, but no
  hybrid experiment is registered because its selection and budget contract is not yet
  scientifically defensible.

New manifests use source-aware identity version `source-v2`. Each run ID contains the
explicit arm label, complete source name, and the first eight hexadecimal characters of a
configuration hash that includes `hypothesis_source`, candidate-policy identity, and the
scene-compiler contract identity. Runtime v3 content-addresses the behavior-bearing source
of both deterministic contracts, not only their human-readable version labels. Pre-amendment rows load only through
the `legacy-v1` implicit-Qwen projection, which reproduces their original hashes and run IDs.
Legacy identity is invalid for any non-Qwen source.

The separate template-v1 development manifest contains 15 frozen development games,
seeds `11`, `23`, and `47`, and these 180 paired rows:

| Arm | Controller | Proposal source | Role |
|---|---|---|---|
| `D-Q` | direct (`D`) | Qwen | contextual direct baseline |
| `S-T` | single (`S`) | template v1 | single-program template comparator |
| `M-T` | myopic (`M`) | template v1 | controlled myopic comparator |
| `X-T` | cross-level (`X`) | template v1 | controlled treatment |

The manifest is `artifacts/development_matrix_template_v1.json`, SHA-256
`6878b39d2379d6ffc11d45953db046883a8622ac529e3702efb679b3d9f6978b`.
Its arm configuration hashes are:

| Arm | Configuration SHA-256 |
|---|---|
| `D-Q` | `18f6efe5ce4feab4b42ac67b917f4cb84c2ea9be603d4321d86bb00c230b1ee7` |
| `S-T` | `d41c6e726ffa2716d278e18ebfb2d14dabbc466ec63543612c297de85a10f3c7` |
| `M-T` | `79ad8a0332109f9e87fe095cf8eb47c35f588fdc3fa4d972520c8053fd2a2530` |
| `X-T` | `aa33d464cc7cae07607689e351bcbc9aadba61c9990d5150441dc5f31e367708` |

It is registration-only: `run-matrix` fails closed if any row has a non-Qwen source. No
environment action is authorized until the template compiler, generic candidate policy,
metamorphic safeguards, and offline runtime-admission gate are all implemented and pass.

## Claim and comparison limits

The registered intended template-source mechanism contrast is `M-T` versus `X-T`. These arms share the
same compiler, perception, action frontier, histories, seeds, controller budgets, and
proposal source; only myopic versus remaining-level-weighted VOI differs. `S-T` is a
single-program mechanism comparator. `D-Q` supplies context but is not a same-backbone or
same-proposal-source ablation against a template arm.

No result may pool Qwen and template arms or claim that proposal-source differences isolate
cross-level VOI. In particular, `M-Q` versus `M-T`, `X-Q` versus `X-T`, and any direct-Qwen
versus template comparison are cross-source engineering comparisons, not controlled
same-backbone evidence. The original Qwen arms retain the explicit labels `D-Q`, `S-Q`,
`M-Q`, and `X-Q` when a new source-v2 Qwen manifest is generated; the locked legacy manifest
itself remains unchanged.

This amendment changes the proposal substrate and run identity only. It does not change the
frozen public split, seeds, action/token/wall-time budgets, controller equations, statistical
unit, score gates, or the negative status of existing results.

## Post-amendment admission result — 13 July 2026

The canonical offline Linux audit subsequently ran from clean commit
`46bf052cd9254a8837f27db9119ffdc34c46cb65`. Four eligible, behaviorally distinct programs
and all three graded roles passed the structural checks, with exact hard 256 MiB allocation
headroom on every selected persistent worker. The decision gate blocked because agreement
and indifference were 1.0, all hypothesis cost vectors were action-flat, maximum EVSI was
0.0, both maximum M and X utilities were -1.0, and there was no X-only probe. The report at
`artifacts/template_v1_runtime_admission_v2_bp35_seed11.json` has SHA-256
`546cf508fa36e1d0ddd39b16e79c35f79fc597577609b3350add8f1c146e1033`. This result does not
alter the frozen amendment or matrix and authorizes no environment action.
