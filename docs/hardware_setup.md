# Local CUDA setup

The lock now pins the official PyTorch 2.11 CUDA 13.0 index for the `model` extra. Core tests
still avoid importing Torch, while a full model environment resolves the same CUDA wheels on
Windows and Linux.

The reference environment is Ubuntu 24.04.1 under WSL2 with normal user `bansarinejad`.
Keep the repository and model snapshot under `/mnt/d`, but place the virtual environment on
WSL's native filesystem at `/home/bansarinejad/.venvs/arc3-crosslevel-voi`; putting the venv
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

The fair-v2 WSL remeasurement passes: 3/4 programs are statically valid with no truncation,
28.85 generated tokens/s, and 9.38 GiB peak VRAM. Its frozen-history grounding gate also
passes with three safe, distinct, action-sensitive programs and enforced POSIX data-segment
limits. See `artifacts/model_gate_live8_wsl.json` and
`artifacts/prompt_grounding_bp35_seed11_wsl.json`.

The fair-v2 native-Windows remeasurement also passes. Its model gate has 2/4 statically valid
programs, no truncation, 21.40 generated tokens/s, and 10.78 GiB peak VRAM. Its grounding gate
has two safe, behaviorally distinct, action-sensitive programs, no palette or coordinate
conflicts, 22.87 generated tokens/s, and 8.98 GiB peak VRAM. Native Windows cannot provide
the POSIX `RLIMIT_DATA` data-segment limit, so the artifact records that limit as not required
instead of claiming enforcement. Prompt and perception contract hashes, the compact fixture,
model revision, and weight manifest match the WSL evidence; platform generation itself is not
bit-identical. See `artifacts/model_gate_live8_windows.json` and
`artifacts/prompt_grounding_bp35_seed11_windows.json`.
