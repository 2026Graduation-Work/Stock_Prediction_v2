import hashlib

import pytest
import yaml
from experiments.run_inference import parse_args, resolve_model_path


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


@pytest.mark.parametrize(
    "arguments",
    [
        ["--threshold", "-0.1"],
        ["--threshold", "1.1"],
        ["--threshold", "nan"],
        ["--workers", "0"],
        ["--workers", "-1"],
        ["--top-n", "0"],
        ["--top-n", "-1"],
    ],
)
def test_parse_args_rejects_invalid_numeric_contract(arguments):
    with pytest.raises(SystemExit):
        parse_args(arguments)


def test_parse_args_accepts_numeric_boundaries():
    assert parse_args(["--threshold", "0", "--workers", "1", "--top-n", "1"]).threshold == 0
    assert parse_args(["--threshold", "1"]).threshold == 1
