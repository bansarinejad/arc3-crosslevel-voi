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
  `175699c4e3c8fbf2cbf934a77764624cfaee523151749cf52d1e626a2e380047`

The unchanged split now feeds a revised prompt/perception manifest. A four-row pilot
revealed that the local renderer disagreed with the pinned official palette at every
symbol, so those rows are diagnostic only and no performance claim is retained. The
superseded matrix is preserved as `development_matrix_pre_grounding.json` with SHA-256
`45f3c2c9e8693d23cbf63c4bf12c765785429b084ac30dbf8ba9be5243c28c25`. Both files use
explicit LF line endings, so these digests are stable across Windows and Linux. The revised
manifest freezes `grounded-actions-palette-v1` and
`arc-agi-0.9.9-color-map-scale8-grid-v1` before any corrected gameplay run.

The final pre-run variant configuration hashes are D
`864dfdd303a94a1e26976a2c3f0659334df9ebd4382f39d7014d0841f031f2d2`, S
`c172c1a20d617c9a748b558678e693f868faea64f1e2df8bc470b3168513f44b`, M
`47608453b95b34a2f0911b3c269055457eb630ab4edb3222cc3e31968a4fdf95`, and X
`11b42cf6d1adc3c6e4f0771705723c4f376d174e77d9c8f1d620e8f1bc04b514`.
