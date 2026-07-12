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
- Frozen: the dated 25-game metadata snapshot, deterministic 15/10 split, and revised
  180-run development matrix under `artifacts/`, with versioned prompt/perception
  contracts and identical 256-action, 12,288-token, and 1,200-second caps.
- Verified pre-grounding engineering smoke: the official anonymous endpoint accepted one
  action through the 4B committee on frozen `ls20-9607627b`, with two-or-more valid
  programs and no fallback/timeouts/errors. It validates lifecycle wiring only; see
  `artifacts/official_model_smoke.json`.
- Verified the WSL reference stack: Ubuntu 24.04.1, Python 3.12.3, Torch 2.11.0+cu130,
  CUDA 13.0, driver 581.15, `sm_89`, bitsandbytes 0.49.2, and Transformers 5.13.1.
  Dependency consistency and a BF16 CUDA operation pass. See `artifacts/wsl_stack_check.json`.
- The v1 WSL eight-frame capacity gate passed from the manifest-verified native model copy:
  4/4 programs statically valid, no truncation, 9.35 GiB peak VRAM, and 26.64 generated
  tokens/s. Its grounding gate then failed because all three safe programs were behavioral
  no-ops. Both artifacts are retained as diagnostics; the v2 diversity contract is pending
  remeasurement before gameplay.
- Preserved earlier official-palette Windows model and grounding checks as diagnostics only;
  their artifacts predate contract-content fingerprints and the checked-in history fixture,
  so they are explicitly marked superseded.
- The first D/S/M/X pilot is retained only as a pre-grounding diagnostic. Its renderer
  disagreed with the official `arc-agi==0.9.9` palette at all 16 indices, so its zero
  scores and mechanism telemetry are excluded from controlled evidence. The superseded
  matrix and gate are preserved with `_pre_grounding` suffixes.
- Not yet completed: all 180 revised development runs, locked confirmation,
  the Kaggle-hardware 27B/9B transfer gate, a private score, and any ARC-AGI-2 evaluation.

The checked-in four-sequence 9B NF4 preflight artifact does **not** pass the declared model
gate and must not be substituted by an earlier single-sequence measurement. The official
The 4B BF16 fallback is the selected local model. There are deliberately no
corrected-contract controlled gameplay scores or positive cross-level performance claims
until the controlled matrices are executed.

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
