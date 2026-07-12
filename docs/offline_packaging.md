# Offline bundle and startup rehearsal

The checked-in source tree is not itself a Kaggle bundle. A final bundle is immutable,
hash-addressed, and contains one selected model snapshot, one project wheel, a complete
Linux wheelhouse, inherited configs, the competition entrypoint, and license provenance.
Weights and wheels are intentionally excluded from Git.

## Build inputs

Build all inputs on a Linux environment matching the live Kaggle image. Never copy the
native-Windows CUDA environment into the submission.

```bash
uv build --wheel
uv pip compile pyproject.toml --extra arc --extra model -o build/kaggle-requirements.txt
python -m pip download -r build/kaggle-requirements.txt -d build/wheelhouse
```

The last command is a preparation-time network operation. The resulting wheelhouse must
contain every transitive dependency; installation inside the Kaggle evaluator must use
`--no-index --find-links` only. Confirm the selected model snapshot contains its own
`README.md` and `LICENSE`. Do not infer a model license from its family name or from a
different parameter size.

Assemble without any downloads:

```bash
python scripts/build_offline_bundle.py \
  --project-wheel dist/arc3_crosslevel_voi-0.1.0-py3-none-any.whl \
  --wheelhouse build/wheelhouse \
  --model /path/to/exact/model-snapshot \
  --model-id Qwen/Qwen3.5-9B \
  --config configs/kaggle_9b_bf16.yaml \
  --output build/kaggle-bundle
```

The script refuses an existing output directory. It also reads each wheel's own METADATA
and extracts embedded license/NOTICE files under `provenance/wheel-licenses`; a missing
embedded license remains visible in the manifest and must be resolved before release.
`manifest.json` records SHA-256 and byte size for every payload, the project wheel and lock
hashes, wheel hashes and license fields, selected config, and model ID/revision/license
evidence observed inside the supplied snapshot. Assembly fails if the model card has no
license declaration or the local Hugging Face metadata does not identify one consistent
immutable revision; neither value is guessed. `manifest.sha256` protects the manifest
itself. This is an integrity check, not a signature: publish the expected manifest digest
in the frozen repository/notebook or another independently trusted record.

## Network-disabled smoke

Run the lightweight import/config check first:

```bash
python build/kaggle-bundle/scripts/offline_startup_smoke.py build/kaggle-bundle
```

This validates all hashes, sets the Hugging Face/Transformers offline flags, blocks Python
socket connects, imports the exact project wheel and entrypoint, requires
`model.offline: true`, and loads the model configuration with `local_files_only=True`. It
does not allocate the model weights and is not a VRAM or throughput test.

For the submission rehearsal, add an operating-system network boundary and install only
from the bundle. For example, in a compatible Linux container:

```bash
docker run --rm --network none --gpus all -v "$PWD/build/kaggle-bundle:/bundle:ro" IMAGE \
  bash -lc 'python -m pip install --no-index --find-links=/bundle/wheelhouse \
  /bundle/code/*.whl && python /bundle/runtime/entrypoint.py'
```

Replace `IMAGE` with the recorded Kaggle-compatible image and supply the official gateway
environment. The Python socket guard is defense in depth, not proof that native libraries
cannot connect; `--network none` (or the Kaggle sandbox) is the real boundary.

## Acceptance record

Archive the following together before selecting a submission:

- `manifest.json` and `manifest.sha256`;
- the exact notebook and repository commit hash;
- stdout/stderr and exit code from the network-disabled full rehearsal;
- runtime distribution, peak VRAM, CUDA/driver/package versions, and hardware;
- model card and license copied from the exact packaged snapshot;
- the current official starter/gateway cell, copied rather than reimplemented.

Passing startup does not pass the model gate. The selected Kaggle target additionally
needs at least 20% p95 runtime headroom on the actual competition hardware.
