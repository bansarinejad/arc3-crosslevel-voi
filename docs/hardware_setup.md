# Local CUDA setup

The locked default PyPI environment is CPU-safe so tests work everywhere. Model preflight
requires an official CUDA PyTorch overlay.

Preferred path: initialize a normal, non-root Ubuntu WSL2 user and run the Linux CUDA 13.0
wheel against the repository mounted under `/mnt/d`. Do not configure a persistent root WSL
account.

Native Windows fallback for the current 581.15/CUDA 13.0 driver:

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements\torch-cu130.txt
python -c "import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name())"
```

This overlay intentionally sits outside the platform-neutral `uv.lock`; record the exact
wheel hash in every model preflight artifact. Kaggle uses its own frozen Linux wheelhouse and
must be rehearsed separately.

The native-Windows gate selected official Qwen3.5-4B BF16 with physical microbatch size
one: 12.52 GiB peak and 15.80 generated tokens/s for four logical candidates. The 9B NF4
four-sequence profile was rejected at 23.28 GiB allocated peak and 5.32 tokens/s. Exact
artifacts and revisions are in `artifacts/model_gate.json`.

WSL2 is enabled but no normal Ubuntu user distribution was initialized during setup. Native
Windows is therefore the measured development path; Linux/WSL remains the required parity
rehearsal before Kaggle packaging. Close GPU-heavy desktop applications before either
profile because the 4090 Laptop GPU has only 16 GiB physical VRAM.
