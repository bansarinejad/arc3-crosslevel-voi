# Public split provenance

`public_split.json` was frozen from `public_games.snapshot.json` with seed
`20260712`, a 15/10 development/confirmation allocation, and the
`iterative-multilabel-v1` splitter. The splitter balances action modality, exact
level count, and human-baseline action quartile using iterative multilabel
stratification.

The current manifest supersedes the pre-experiment greedy draft whose SHA-256 was
`032d00a7e5cb0d0f3baaaa6c7806fab39f67d56d1c8f27df14e7431c3c66eca7`.
No tuning or score results existed when it was replaced. The current manifest
embeds every full game version and the immutable metadata snapshot hash.

- Current `public_split.json` SHA-256:
  `0edf4f937be4ed391eb477343fd4fdee32cf6cd255092ae4f1ea617872ab1614`
- Historical fair-v2 matrix `development_matrix_fair_v2.json` SHA-256:
  `76bcfd53547b4cf4c376bff45fab5511dad4bc30ccf778f2f90e07da88bef495`
- Historical goal-v3 pilot matrix `development_matrix_goal_v3_pilot.json` SHA-256:
  `7bf39d2c1ea7c986e7c473069a8647ae8d8677b66ab5a2a510576d00b4bd3816`
- Historical runtime-v1 matrix `development_matrix_runtime_v1.json` SHA-256:
  `b207c451e81ef6f6b815fbd9dc557a7149d221f8af3f7d4034f6d79325580fc7`
- Historical evidence-first-v4 matrix `development_matrix_visible_causal_v4.json` SHA-256:
  `6f7f5b9f6748cd06335eb269d6afa1277bb9b5d690feba5c082dc609d7e471d9`
- Active repair-enabled-v5 matrix `development_matrix.json` SHA-256:
  `ea2dbc2eec0159e63452ab805545021d5101a17882402dd3bc9869fc39241147`

The unchanged split first fed the fair-v2 manifest. Its corrected four-row seed-11
D/S/M/X pilot is retained as negative engineering evidence; the other 176 fair-v2 rows
were superseded and abandoned when the goal contract changed. They are not pending.
An earlier palette-invalid matrix remains diagnostic only at
`development_matrix_pre_grounding.json`, SHA-256
`45f3c2c9e8693d23cbf63c4bf12c765785429b084ac30dbf8ba9be5243c28c25`.

The historical goal-v3 matrix completed its seed-11 bp35 D/S/M/X pilot. All four
variants completed zero levels and scored zero RHAE; M's best-loss improvement over S
was 13.2913%, below the 15% mechanism gate, and X/M runtime was 1.00133x. M and X were
semantically identical and selected no probes. The audit at
`pilot_bp35_seed11_goal_v3.json` also records the live-pool grounding-selection defect.
The remaining 176 historical goal-v3 rows are abandoned and superseded, not pending.
Its variant configuration hashes were D
`18d8bbf79d3fc63b1f894fba0e9312e84687ba0fc37f1b55b385d029fdb4c7d6`, S
`533bd83496f475d022fdb13c6a29ec65550d02a6be36af39e2ba0d394ff6e446`, M
`8054a950f7215ba13c28628b45eac0b49e0f7bd9b513b4194dab416176155f16`, and X
`21a2fb16fc2865527f50efa1cf7d729c46b9689bb4eda6d8daf1c1e18434cb3c`.

The superseded zero-run runtime-v1 matrix preserved the goal-v3 prompt contract and the
post-audit admission-order/telemetry fixes. Both historical source committees then failed
the offline runtime-admission decision-diversity gate, so all 180 rows were abandoned
without gameplay and preserved at `development_matrix_runtime_v1.json`.

The zero-run evidence-first-v4 matrix was superseded after its first Windows grounding
smoke produced no eligible program. The retained artifact also has an invalid concurrent
throughput measurement and is not gate evidence. Its matrix is preserved at
`development_matrix_visible_causal_v4.json` without gameplay.

The active matrix freezes prompt contract `evidence-first-visible-causal-alternatives-v5`,
perception contract `arc-agi-0.9.9-color-map-scale8-grid-v1`, and implementation contract
`crosslevel-voi-runtime-v2`. It contains 180 pending rows: 15 development games, seeds
`11`, `23`, and `47`, and variants D/S/M/X. No active-matrix gameplay has run. The active
matrix is locked: repair-enabled v5 grounding rejected both the 4B and serial 9B local
profiles on program quality, despite both passing their current compute limits. The active
variant configuration hashes are D
`e56fe0e2a55e344edc53bd0d5f09c448305da3b07825c8d12798c935e51a68e6`, S
`e254bbf925180ac197696913250cbbbab1b454a3f163391b470912e270bb0ded`, M
`bd35d59f73baa0fe09d3e00aa6d4541c05505135da620fbe2556ccf1533bf13f`, and X
`6e84fd03aea5012a8360410dc9386913d7767dd71377c2d5bdde6e374aa79c0e`.
The JSON manifests use explicit LF line endings, so these digests are stable across
Windows and Linux.
