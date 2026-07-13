# Local CUDA setup

The lock now pins the official PyTorch 2.11 CUDA 13.0 index for the `model` extra. Core tests
still avoid importing Torch, while a full model environment resolves the same CUDA wheels on
Windows and Linux.

The repository is at `D:\kaggle competitions\arc3-crosslevel-voi` on Windows and
`/mnt/d/kaggle competitions/arc3-crosslevel-voi` under WSL; quote the WSL path because it
contains a space. The reference environment is Ubuntu 24.04.1 under WSL2 with normal user
`bansarinejad`. Keep the repository and model snapshot under `/mnt/d`, but place the
virtual environment on WSL's native filesystem at
`/home/bansarinejad/.venvs/arc3-crosslevel-voi`; putting the venv
on `/mnt/d` made Python imports and spawned-worker startup spend minutes in the `p9` bridge.

Native Windows fallback for the current 581.15/CUDA 13.0 driver:

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements\torch-cu130.txt
python -c "import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name())"
```

`requirements/torch-cu130.txt` remains a small auditable overlay reference, but the same exact
Torch and torchvision versions are now represented in `pyproject.toml` and `uv.lock`. The
preflight schema and newly generated artifacts record the OS/kernel, Python, driver,
Torch/CUDA, key package versions, model revision, and Hugging Face weight ETags. Exact wheel
hashes belong in the final offline bundle manifest. Kaggle uses its own frozen Linux
wheelhouse and must be rehearsed separately.

Archived pre-grounding native-Windows capacity evidence selected official Qwen3.5-4B BF16
with physical microbatch size one: 12.52 GiB peak and 15.80 generated tokens/s for four
logical candidates. The 9B NF4 four-sequence profile was rejected at 23.28 GiB allocated peak
and 5.32 tokens/s. These numbers are diagnostic only; see `artifacts/model_gate.json`.

The WSL stack check passes with Python 3.12.3, Torch 2.11.0+cu130, CUDA runtime 13.0,
bitsandbytes 0.49.2, Transformers 5.13.1, driver 581.15, and compute capability `sm_89`.
Dependency consistency and a BF16 CUDA matrix multiplication both pass. Model and grounding
gate evidence is recorded separately. The machine-readable stack evidence is
`artifacts/wsl_stack_check.json`. Close GPU-heavy desktop applications
because the 4090 Laptop GPU has only 16 GiB physical VRAM.

The v1 WSL eight-frame capacity preflight passed with 4/4 statically valid programs, no
truncation, 9.35 GiB peak VRAM, and 26.64 generated tokens/s, but its grounding gate failed
on behavioral diversity and is retained as `artifacts/model_gate_live8_wsl_v1.json`.
Loading the model directly
from `/mnt/d` was aborted after three minutes at 6% because safetensors tensor mappings were
dominated by the `p9` bridge. Copying the manifest-verified snapshot to
`/home/bansarinejad/models/Qwen3.5-4B` reduced weight loading to about one second. See
`artifacts/model_gate_live8_wsl_v1.json`.

The fair-v2 WSL model remeasurement passes: 3/4 programs are statically valid with no
truncation, 28.85 generated tokens/s, and 9.38 GiB peak VRAM. Its original one-frame
grounding pass is retained only as a superseded diagnostic at
`artifacts/prompt_grounding_bp35_seed11_wsl_pre_worker_memory_fix.json`. The first corrected
pilot showed why: NumPy/OpenBLAS had already reserved about 1.3 GiB of `VmData`, so Linux
accepted an absolute 256 MiB `RLIMIT_DATA` that made a later pipe-buffer allocation fail.

The corrected worker compiles the validated program, measures the trusted Linux `VmData`
baseline, and verifies a hard `RLIMIT_DATA` ceiling exactly 256 MiB above it. This is a
kernel-enforced incremental worker-lifetime allocation budget, not a claim that the entire
Python/NumPy process occupies 256 MiB. Metadata records the limit kind, measured baseline,
effective ceiling, enforcement status, and diagnostic. The full eight-frame 64x64 `int16`
transport and a generated allocation above the budget are regression-tested. Incident details
are in `artifacts/pilot_seed11_worker_memory_incident.json`. The clean schema-v3 WSL rerun
passes with three safe, behaviorally distinct, action-sensitive programs, no palette or
coordinate conflicts, 29.91 generated tokens/s, and 8.84 GiB peak VRAM. Every eligible
program records an enforced ceiling exactly 256 MiB above its measured baseline. See
`artifacts/prompt_grounding_bp35_seed11_wsl.json`.

The fair-v2 native-Windows remeasurement also passes. Its model gate has 2/4 statically valid
programs, no truncation, 21.40 generated tokens/s, and 10.78 GiB peak VRAM. Its grounding gate
has two safe, behaviorally distinct, action-sensitive programs, no palette or coordinate
conflicts, 22.81 generated tokens/s, and 8.98 GiB peak VRAM. Native Windows cannot provide
the POSIX `RLIMIT_DATA` data-segment limit, so the artifact records that limit as not required
instead of claiming enforcement. Prompt and perception contract hashes, the compact fixture,
model revision, and weight manifest match the WSL evidence; platform generation itself is not
bit-identical. See `artifacts/model_gate_live8_windows.json` and
`artifacts/prompt_grounding_bp35_seed11_windows.json`.

Those schema-v3 fair-v2 artifacts remain historical evidence for the runtime and memory
fixes. The historical schema-v4 goal-v3 gate passed on both platforms. WSL produced 2
eligible programs in 2 distinct behavior classes, including 1 action-conditioned graded
goal program, and verified the hard +256 MiB allocation ceiling for both eligible workers.
Native Windows produced 3 eligible programs in 3 distinct classes, including 2 conditioned
graded programs; POSIX `RLIMIT_DATA` is unavailable and therefore not required there. The
shared contracts and fixed inputs establish functional parity only: stochastic platform
generation is not claimed to be bit-identical. See
`artifacts/prompt_grounding_bp35_seed11_goal_v3_wsl.json` and
`artifacts/prompt_grounding_bp35_seed11_goal_v3_windows.json`.

The subsequent historical goal-v3 pilot exposed an admission-order defect: behavioral
deduplication could replace a role-eligible program with a smaller behaviorally equivalent
but role-ineligible program. The current runtime filters role grounding before starting
persistent workers or deduplicating candidates. This source-level correction has not yet passed a
fresh gameplay pilot and does not authorize gameplay by itself. Deterministic offline
admission audits over the historical WSL and Windows source batches verified clean
eligible-only selection and zero planner failures, but both blocked on decision diversity:
agreement was 1.0, EVSI was 0.0, and cross-level probe utility was -1.0. See
`artifacts/runtime_admission_goal_v3_wsl.json` and
`artifacts/runtime_admission_goal_v3_windows.json`. Scale-up remains locked; subsequent
v5 and path-deficit-v2 evidence below supersedes the earlier pending-gate sequence.

The repair-enabled v5 native-Windows gates separate compute capacity from program quality.
Qwen3.5-4B BF16 used two batches, 3,665 output tokens, 163.17 generation seconds,
22.46 tokens/s, and 9.65 GiB peak; repair improved the pool to two safe distinct programs,
but neither was an eligible graded role. The current serial Qwen3.5-9B NF4 path used two
batches, 1,933 tokens, 136.09 seconds, 14.20 tokens/s, and 8.58 GiB peak. This supersedes
the old 9B four-simultaneous-sequence compute rejection for the serial profile, but all
eight 9B candidates failed grounding. Neither result authorizes gameplay. See
`artifacts/prompt_grounding_bp35_seed11_visible_causal_v5_windows.json` and
`artifacts/prompt_grounding_bp35_seed11_visible_causal_v5_9b_windows.json`.

The topology-v1 canonical synthetic audit was subsequently blocked on decision diversity.
The separately frozen path-deficit-v2 treatment then failed its fixed Linux synthetic gate
before a canonical audit, model call, or gameplay: weighted agreement was
`0.8417629130389278`, maximum EVSI was `0.048123650158264475`, and no X-only probe existed.
That treatment and its zero-run matrix are permanently frozen. There is no active or
pending experiment matrix; another attempt requires a separately preregistered treatment.
