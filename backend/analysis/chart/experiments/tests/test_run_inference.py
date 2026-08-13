import hashlib

import pytest
import yaml

from experiments.run_inference import resolve_model_path


def test_resolve_model_path_from_registry(tmp_path):
    model_path = tmp_path / "model.txt"
    model_path.write_bytes(b"model")
    sha256 = hashlib.sha256(b"model").hexdigest()
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(
            {"models": {"aggressive": {"model_file": "model.txt", "sha256": sha256}}}
        ),
        encoding="utf-8",
    )

    assert resolve_model_path("aggressive", registry_path=registry_path) == str(model_path)


def test_resolve_model_path_rejects_sha_mismatch(tmp_path):
    (tmp_path / "model.txt").write_bytes(b"model")
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(
            {"models": {"stable": {"model_file": "model.txt", "sha256": "wrong"}}}
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="SHA-256 불일치"):
        resolve_model_path("stable", registry_path=registry_path)
