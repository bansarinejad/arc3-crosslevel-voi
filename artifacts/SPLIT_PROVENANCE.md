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
- Active runtime-v1 matrix `development_matrix.json` SHA-256:
  `b207c451e81ef6f6b815fbd9dc557a7149d221f8af3f7d4034f6d79325580fc7`

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

The active matrix freezes prompt contract `grounded-actions-palette-graded-goals-v3`,
perception contract `arc-agi-0.9.9-color-map-scale8-grid-v1`, and implementation contract
`crosslevel-voi-runtime-v1`. It contains 180 pending rows: 15 development games, seeds
`11`, `23`, and `47`, and variants D/S/M/X. No active-matrix gameplay has run. The active
variant configuration hashes are D
`189a399c2405f28ee81884db3e7f2bd64ed30c2c517d3c24de7adbb4d1467d6f`, S
`9fe7776c7d9effad7a143d04f2d581d6eb7aaa6a23e2daac8db0bca2418dfa0e`, M
`1f444c4170dd38fd172dae17d806434b5fe50eb1da9f2a00a7473b4bb9816919`, and X
`5e8515c81db38475798a15d76f4379dd8a524d87a753d8bc972f6df364158c4a`.
The JSON manifests use explicit LF line endings, so these digests are stable across
Windows and Linux.
