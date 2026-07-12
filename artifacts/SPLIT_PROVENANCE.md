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
  `304f8fcf603ebc18720046fd411b53db48dd4b0b754feb3fc4033e2997e9ea8b`
