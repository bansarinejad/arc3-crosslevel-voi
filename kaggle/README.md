# Kaggle packaging

`entrypoint.py` is the offline system entrypoint. The final Kaggle notebook must preserve
the official competition starter's install/gateway cells and invoke this module after
mounting:

- this repository wheel and locked wheelhouse;
- the selected Qwen model artifact;
- `configs/kaggle_27b.yaml`, or `configs/kaggle_9b_bf16.yaml` after the target gate
  rejects 27B FP8. The Kaggle fallback is BF16, not the local NF4 profile.

Required environment variables:

- `ARC3_CONFIG`
- `ARC3_MODEL_PATH`
- `ARC3_OUTPUT`
- `ARC3_GLOBAL_WALL_SECONDS` from the live competition limit
- `ARC3_GAME_IDS`, populated by the copied official gateway's workload manifest

The entrypoint fails closed when no gateway manifest is supplied; it never substitutes the
public catalogue for a hidden workload. It opens one competition client, makes every
stable game ID once, never calls `get_scorecard`, and uses only level resets. Before
submission, copy—not reimplement—the current official gateway cell because Kaggle's
evaluator interface may change.

The sequential reference runner is correctness-first. Enable any later concurrency only
after a same-output replay test and the 20% p95 runtime-headroom gate; never issue concurrent
calls to a non-batching model backend merely to increase nominal throughput.

Assemble the exact wheel, Linux wheelhouse, model snapshot, configs, entrypoint, and notices
with `scripts/build_offline_bundle.py`. It creates a byte-level `manifest.json` plus
`manifest.sha256`; it does not download anything. Before submission, run
`scripts/offline_startup_smoke.py` and a complete evaluator rehearsal under an operating-
system network boundary such as `docker --network none`. The lightweight smoke verifies
hashes and local-only imports but does not substitute for full model loading or the p95
runtime gate. See `docs/offline_packaging.md`.
