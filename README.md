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
- Retained the v1 WSL capacity pass and failed grounding gate as diagnostics: its safe
  programs collapsed to one behavioral no-op class, so it did not authorize gameplay.
- Passed the fair-v2 WSL model gate: 3/4 valid programs, no truncation, 28.85 tokens/s,
  and 9.38 GiB peak. The original one-frame grounding pass is now explicitly superseded:
  the seed-11 pilot exposed that its absolute 256 MiB `RLIMIT_DATA` ceiling was below the
  trusted NumPy runtime's existing data segment. The runtime now hard-limits allocation
  headroom to 256 MiB above a measured baseline and records both values. The old evidence is
  retained at `artifacts/prompt_grounding_bp35_seed11_wsl_pre_worker_memory_fix.json`. The
  schema-v3 remeasurement passes with 3 safe, distinct, action-sensitive programs, exact
  +256 MiB verified ceilings, no conflicts, 29.91 tokens/s, and 8.84 GiB peak. See
  `artifacts/prompt_grounding_bp35_seed11_wsl.json`.
- Passed the same fair-v2 gates on native Windows. The model preflight produced 2/4 valid
  programs with no truncation at 21.40 tokens/s and 10.78 GiB peak. The frozen-history gate
  produced 2 safe, 2 distinct, action-sensitive programs with no palette or coordinate
  conflicts at 22.81 tokens/s and 8.98 GiB peak. Windows has no POSIX `RLIMIT_DATA`, so hard
  data-segment enforcement is transparently reported as not required. The frozen contracts,
  fixture, model revision, and weight manifest match WSL; generated source is not claimed to
  be bit-identical across platforms. See `artifacts/model_gate_live8_windows.json` and
  `artifacts/prompt_grounding_bp35_seed11_windows.json`.
- Completed the corrected fair-v2 seed-11 D/S/M/X pilot from one clean post-fix commit.
  It is valid negative engineering evidence: every variant exhausted 256 actions without
  completing a level. The committee retained at least two programs throughout M/X, but its
  best prequential loss improved only 7.87% over S, below the 15% mechanism gate. All 241
  M/X planning rows had action-invariant cost vectors, so EVSI was zero and X was exactly
  equivalent to M after timing and variant labels were removed. The remaining 176 runs stay
  locked while goal-function invalidation, probe telemetry, and planning cost collapse are
  corrected. Exact run hashes and audits are in
  `artifacts/pilot_bp35_seed11_fair_v2.json`; the preceding worker-memory incident remains in
  `artifacts/pilot_seed11_worker_memory_incident.json`.
- The first D/S/M/X pilot is retained only as a pre-grounding diagnostic. Its renderer
  disagreed with the official `arc-agi==0.9.9` palette at all 16 indices, so its zero
  scores and mechanism telemetry are excluded from controlled evidence. The superseded
  matrix and gate are preserved with `_pre_grounding` suffixes.
- Not yet completed: the remaining 176 revised development runs, locked confirmation,
  the Kaggle-hardware 27B/9B transfer gate, a private score, and any ARC-AGI-2 evaluation.

The checked-in four-sequence 9B NF4 preflight artifact does **not** pass the declared model
gate and must not be substituted by an earlier single-sequence measurement. The official
4B BF16 fallback is the selected local model. There are deliberately no
development aggregate or positive cross-level performance claim until a corrected pilot
passes the preregistered scale-up gates and the controlled matrices are executed.

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
