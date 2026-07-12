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
- Derived `development_matrix.json` SHA-256:
  `76bcfd53547b4cf4c376bff45fab5511dad4bc30ccf778f2f90e07da88bef495`

The unchanged split now feeds a revised prompt/perception manifest. A four-row pilot
revealed that the local renderer disagreed with the pinned official palette at every
symbol, so those rows are diagnostic only and no performance claim is retained. The
superseded matrix is preserved as `development_matrix_pre_grounding.json` with SHA-256
`45f3c2c9e8693d23cbf63c4bf12c765785429b084ac30dbf8ba9be5243c28c25`. Both files use
explicit LF line endings, so these digests are stable across Windows and Linux. The revised
manifest freezes `grounded-actions-palette-diverse-v2` and
`arc-agi-0.9.9-color-map-scale8-grid-v1` before any corrected gameplay run.

The final pre-run variant configuration hashes are D
`2fdf174a8b1cda9fbb0b9e0e4a0ea532e972bd71bad907989b3d3f470760de03`, S
`e9cfb883b32db54b589748668fb3f79889b18d922775a8d5694b0500806f55f3`, M
`6601a0313657213c5df67a4ccafb43632f22309d6382b1563b04c94a2488f95a`, and X
`dac5979877702ce1b2b78d783cc7811b9013a69b7602abfe0860d6045014b363`.
