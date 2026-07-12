# Model, dependency, and license provenance

This register distinguishes checked evidence from planned artifacts. It must be updated
from the exact bytes selected for a release; configuration names alone are not license or
revision evidence.

## Checked local artifacts — 12 July 2026

| Artifact | Observed evidence | Release treatment |
|---|---|---|
| [`Qwen/Qwen3.5-9B`](https://huggingface.co/Qwen/Qwen3.5-9B) | Local Hugging Face metadata reports revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`; `README.md` declares `apache-2.0`; its bundled `LICENSE` is Apache License 2.0, names Copyright 2026 Alibaba Cloud, and hashes to `bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a`. | May be bundled only with that `LICENSE`, model card, revision, and all file hashes preserved. |
| [`Qwen/Qwen3.5-4B`](https://huggingface.co/Qwen/Qwen3.5-4B) | Selected local fallback at revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`. Its bundled Apache-2.0 `LICENSE` hashes to `bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a`. The two weight shards are `26a93f066e1916adb13453dae5a0c707c0fbc71299ed98779571a907b8e74c61` and `cb544bd9bfae93dc59b0f22b292f5933573854a7f9b97835c67060d7d910e188`. | Selected after the measured 9B rejection; bundle exact revision, model card, license, and byte manifest. |
| `arc-agi==0.9.9` | Installed distribution metadata declares MIT; official repository license text is preserved in `LICENSES/ARC-AGI-Toolkit-MIT.txt`. | Preserve upstream license and pin/hash its wheel in the offline manifest. |
| `arcengine==0.9.3` | Installed distribution metadata declares MIT. | Preserve the exact wheel's license metadata/file in the final wheelhouse notices. |
| Python dependencies | Exact resolver state is `uv.lock`; native CUDA PyTorch uses the explicit official-wheel overlay in `requirements/torch-cu130.txt`. | Final Linux wheels, including CUDA variants, are individually hashed by the bundle manifest. Do not cite the Windows environment as Kaggle parity. |

## Referenced but not yet locally verified

| Artifact | Status |
|---|---|
| `Qwen/Qwen3.6-27B-FP8` | Configured as a conditional Kaggle target. No license assertion is made here until the exact snapshot's own model card and license are present locally. It also remains subject to the Kaggle fit/runtime gate. |

The root `NOTICE` intentionally does not relicense any of these works. The authored source
license (`MIT-0 OR CC-BY-4.0`) applies only to submitter-authored code. Paper text and media
use CC-BY-4.0. Model weights, toolkit code, wheels, and bundled assets retain their own
terms. The final release must include a generated inventory of every distributed third-
party file rather than relying on this human-readable register alone.

## Finalization checklist

1. Record the immutable model revision from the downloaded snapshot metadata.
2. Compare the model card's declared license with the included license text; stop on any
   mismatch or missing file.
3. Hash every model shard, wheel, config, entrypoint, notice, and repository wheel.
4. Extract license/NOTICE files from every distributed wheel into a third-party notice
   archive; do not assume a package's license from its name.
5. Record the Kaggle image, Python, CUDA, Torch, Transformers, bitsandbytes, ARC toolkit,
   and driver versions in the rehearsal artifact.
6. Recheck competition-specific redistribution wording and retain the organizer response
   before making the public release.
