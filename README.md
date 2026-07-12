# Learn Early, Exploit Late

Research code for **cross-level value of information over a persistent executable
version space** in ARC-AGI-3. The system keeps several transition-and-goal programs,
uses their counterfactual disagreement to value probes, and increases the value of
early information when it can reduce action cost on more heavily weighted later levels.

This repository is an independent implementation against the official ARC toolkit. It
does not contain code from Duck or other competition entries.

## Current status

- Implemented: core types, restricted persistent program workers, prequential Gibbs
  weighting and refresh, behavioral deduplication, candidate generation, depth-four
  beam planning, D/S/M/X controllers, direct fallback, trace replay, RHAE/statistics,
  competition lifecycle, and lazy Qwen backends.
- Frozen: the dated 25-game metadata snapshot, deterministic 15/10 split, and 180-run
  development matrix under `artifacts/`, with identical 256-action, 12,288-token, and
  1,200-second per-game caps across variants.
- Verified engineering smoke: the official anonymous endpoint accepted one action through
  the selected 4B committee on frozen `ls20-9607627b`, with two-or-more valid programs,
  no fallback/timeouts/errors, and 12.43 GiB peak. This is neither a game result nor
  leaderboard evidence; see `artifacts/official_model_smoke.json`.
- Passed the corrected eight-frame local model gate: official Qwen3.5-4B revision
  `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` in BF16 generated four logical candidates
  as deterministic single-sequence microbatches (10.12 GiB peak, 22.81 tokens/s, and
  2/4 statically valid programs). See `artifacts/model_gate_live8.json`.
- Completed the first frozen paired pilot cell (`bp35-0a0ad940`, seed 11): all D/S/M/X
  rows terminated cleanly under their shared budgets, but every variant completed zero
  levels. M and X maintained at least two valid programs at 255/256 decision points and
  improved best-program prequential loss by 24.6% versus S. M and X nevertheless chose
  identical actions with zero probes because agreement stayed at 1.0, so this cell is not
  evidence for cross-level VOI. See `artifacts/pilot_bp35_seed11.json`.
- Not yet completed: the remaining 176 controlled development runs, locked confirmation,
  the Kaggle-hardware 27B/9B transfer gate, a private score, and any ARC-AGI-2 evaluation.

The checked-in four-sequence 9B NF4 preflight artifact does **not** pass the declared model
gate and must not be substituted by an earlier single-sequence measurement. The official
4B BF16 fallback does pass. There are deliberately no gameplay scores or positive
cross-level performance claims until the controlled matrices are executed.

## Quick start

Linux/WSL2 and Python 3.12 are the reference environment.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --extra dev
uv run pytest
uv run arc3-voi config-check configs/local_4b.yaml
```

Install optional runtime groups only on the machine that needs them:

```bash
uv sync --extra dev --extra arc --extra model --extra stats
```

The core test suite imports neither Torch nor the ARC SDK. Heavy model loading is lazy.

## Reproducible workflow

1. `arc3-voi snapshot` records official public game IDs, versions, tags, level counts,
   and human baselines before tuning.
2. `arc3-voi split` freezes the 15/10 development/confirmation partition using seed
   `20260712`.
3. `arc3-voi matrix development` creates the 180-run preregistered development matrix.
4. `arc3-voi preflight` checks model fit, throughput, and projected hidden workload.
5. `arc3-voi run-matrix` validates and resumably executes frozen manifest rows, writing
   canonical summaries and replayable JSONL traces.
6. `arc3-voi analyze` averages seeds within game and applies paired game-level tests.

See [the experiment protocol](docs/experiment_protocol.md) and
[submission checklist](docs/submission_checklist.md) before producing any reported result.
The formal assumptions and proofs are in [theory](docs/theory.md). Offline release
assembly, hashing, and network-disabled startup are specified in
[offline packaging](docs/offline_packaging.md); exact license evidence is tracked in
[provenance](docs/provenance.md).

## Method at a glance

For each candidate action, programs predict a next observation and a plan cost. Their
predicted observations partition the version space. Expected value of sample information
is the reduction in optimal expected plan cost after observing that partition. The full
controller multiplies this value by remaining level weight and estimated cross-level rule
persistence, then subtracts the action and predicted game-over costs.

The implementation calls its weights **MDL-regularized Gibbs weights**, not a calibrated
Bayesian posterior. Its theory is scoped to deterministic observable or eight-step
finite-history environments.

## Licensing

Submitter-authored source is available under **MIT-0 OR CC-BY-4.0**. Paper text and media
are CC-BY-4.0. Third-party model and toolkit licenses remain their own. See `LICENSE`,
`LICENSES/`, and `NOTICE`.
