from __future__ import annotations

from arc3_voi.provenance import inspect_model_artifact


def test_model_artifact_manifest_uses_hugging_face_etags(tmp_path) -> None:
    weight = tmp_path / "model-00001.safetensors"
    weight.write_bytes(b"weights")
    metadata = tmp_path / ".cache" / "huggingface" / "download"
    metadata.mkdir(parents=True)
    (metadata / "model-00001.safetensors.metadata").write_text(
        f"revision-1\n{'a' * 64}\n0\n",
        encoding="utf-8",
        newline="\n",
    )

    result = inspect_model_artifact(tmp_path)

    assert result.revision == "revision-1"
    assert result.weight_manifest_sha256 is not None
    assert result.weight_files[0].size_bytes == len(b"weights")
    assert result.weight_files[0].etag_sha256 == "a" * 64
