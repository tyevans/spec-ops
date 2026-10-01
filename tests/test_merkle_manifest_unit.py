"""Blackbox unit tests for Merkle tree compliance manifest generator and verifier (ADR-0003, ADR-0016)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from spec_ops.cli.security_handler import handle_audit_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.security.merkle_manifest import (
    EMPTY_ROOT_HASH,
    MerkleManifest,
    MerkleVerificationResult,
    build_merkle_manifest,
    collect_project_artifacts,
    generate_file_proof,
    generate_merkle_manifest,
    verify_file_proof,
    verify_merkle_manifest,
)


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Creates a sample repository layout with docs/project/ and src/ directories."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # docs/project
    docs = repo / "docs" / "project" / "adrs"
    docs.mkdir(parents=True)
    (docs / "adr-0001.md").write_text("# ADR 0001\nContent A", encoding="utf-8")
    (docs / "adr-0002.md").write_text("# ADR 0002\nContent B", encoding="utf-8")

    # src
    src = repo / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "app.py").write_text("def run(): pass\n", encoding="utf-8")

    # Non-deterministic files that should be ignored
    pycache = src / "__pycache__"
    pycache.mkdir()
    (pycache / "app.cpython-313.pyc").write_bytes(b"compiled")
    (src / ".hidden_file").write_text("hidden", encoding="utf-8")
    (docs / "temp.tmp").write_text("tmp", encoding="utf-8")

    return repo


def test_collect_project_artifacts_filters_caches_and_hidden(sample_repo: Path):
    """Verifies collect_project_artifacts collects only version-locked files, ignoring caches and dotfiles."""
    artifacts = collect_project_artifacts(sample_repo)

    assert "docs/project/adrs/adr-0001.md" in artifacts
    assert "docs/project/adrs/adr-0002.md" in artifacts
    assert "src/pkg/app.py" in artifacts

    # Non-versioned files must NOT be present
    for path in artifacts:
        assert "__pycache__" not in path
        assert not path.endswith(".pyc")
        assert not path.endswith(".tmp")
        assert not Path(path).name.startswith(".")


def test_collect_project_artifacts_missing_directories(tmp_path: Path):
    """Verifies collect_project_artifacts handles repos without docs/project or src without error."""
    empty_repo = tmp_path / "empty"
    empty_repo.mkdir()
    artifacts = collect_project_artifacts(empty_repo)
    assert artifacts == {}


def test_build_merkle_manifest_schema_and_types():
    """Verifies build_merkle_manifest generates a compliant manifest with RFC 8785 / RFC 6962 fields."""
    artifacts = {
        "docs/project/a.md": b"Hello A",
        "src/b.py": b"Hello B",
    }
    manifest = build_merkle_manifest(artifacts, standard="soc2")

    assert manifest.version == "1.0.0"
    assert manifest.standard == "soc2"
    assert manifest.algorithm == "sha256"
    assert manifest.serialization == "RFC8785"
    assert manifest.leaf_prefix == "00"
    assert manifest.node_prefix == "01"
    assert manifest.tree_size == 2
    assert len(manifest.leaves) == 2

    # Check leaves
    leaf_a = manifest.leaves[0]
    assert leaf_a["index"] == 0
    assert leaf_a["entity_id"] == "docs/project/a.md"
    assert leaf_a["data"]["path"] == "docs/project/a.md"
    assert leaf_a["data"]["sha256"] == hashlib.sha256(b"Hello A").hexdigest()
    assert leaf_a["data"]["size"] == len(b"Hello A")

    # JSON export
    data = json.loads(manifest.to_json())
    assert data["root_hash"] == manifest.root_hash
    assert data["tree_size"] == 2


def test_generate_merkle_manifest_file_writing(sample_repo: Path):
    """Verifies generate_merkle_manifest writes the manifest to output_path."""
    out_file = sample_repo / "dist" / "merkle-manifest.json"
    manifest = generate_merkle_manifest(sample_repo, output_path=out_file)

    assert out_file.is_file()
    saved_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved_data["root_hash"] == manifest.root_hash
    assert saved_data["tree_size"] == manifest.tree_size


def test_inclusion_proof_generation_and_verification(sample_repo: Path):
    """Verifies generating and verifying an inclusion proof for a single specification file."""
    manifest = generate_merkle_manifest(sample_repo)
    target = "docs/project/adrs/adr-0001.md"

    proof = generate_file_proof(manifest, target)
    assert proof["file_path"] == target
    assert proof["root_hash"] == manifest.root_hash
    assert verify_file_proof(proof) is True

    # Unknown file raises KeyError
    with pytest.raises(KeyError):
        generate_file_proof(manifest, "non_existent_file.md")


def test_verify_merkle_manifest_success_on_clean_repo(sample_repo: Path):
    """Verifies verify_merkle_manifest returns ok=True on an untampered repository."""
    manifest = generate_merkle_manifest(sample_repo)
    result = verify_merkle_manifest(manifest, repo_root=sample_repo)

    assert result.ok is True
    assert len(result.tampered_files) == 0
    assert len(result.errors) == 0
    assert result.artifacts_checked == manifest.tree_size
    assert result.root_hash == manifest.root_hash


def test_verify_merkle_manifest_detects_content_tampering(sample_repo: Path):
    """Verifies verify_merkle_manifest detects when a specification file is modified."""
    manifest = generate_merkle_manifest(sample_repo)
    target_p = sample_repo / "docs" / "project" / "adrs" / "adr-0001.md"
    target_p.write_text("TAMPERED CONTENT", encoding="utf-8")

    result = verify_merkle_manifest(manifest, repo_root=sample_repo)
    assert result.ok is False
    assert "docs/project/adrs/adr-0001.md" in result.tampered_files
    assert any("Digest mismatch" in err for err in result.errors)
    assert result.corrupted_entity_id == "docs/project/adrs/adr-0001.md"


def test_verify_merkle_manifest_detects_missing_file(sample_repo: Path):
    """Verifies verify_merkle_manifest detects when an artifact is deleted."""
    manifest = generate_merkle_manifest(sample_repo)
    target_p = sample_repo / "src" / "pkg" / "app.py"
    target_p.unlink()

    result = verify_merkle_manifest(manifest, repo_root=sample_repo)
    assert result.ok is False
    assert "src/pkg/app.py" in result.tampered_files
    assert any("File missing on disk" in err for err in result.errors)


def test_verify_merkle_manifest_detects_untracked_new_file(sample_repo: Path):
    """Verifies verify_merkle_manifest detects unauthorized new files added to docs/project or src."""
    manifest = generate_merkle_manifest(sample_repo)
    new_file = sample_repo / "docs" / "project" / "adrs" / "adr-unauthorized.md"
    new_file.write_text("unauthorized", encoding="utf-8")

    result = verify_merkle_manifest(manifest, repo_root=sample_repo)
    assert result.ok is False
    assert "docs/project/adrs/adr-unauthorized.md" in result.tampered_files
    assert any("Untracked or unauthorized" in err for err in result.errors)


def test_verify_merkle_manifest_detects_root_corruption(sample_repo: Path):
    """Verifies verify_merkle_manifest flags a corrupted root hash in the manifest JSON."""
    manifest_dict = generate_merkle_manifest(sample_repo).to_dict()
    manifest_dict["root_hash"] = "00" * 32

    result = verify_merkle_manifest(manifest_dict, repo_root=sample_repo)
    assert result.ok is False
    assert any("Root hash mismatch" in err for err in result.errors)


def test_verify_merkle_manifest_file_not_found(tmp_path: Path):
    """Verifies verify_merkle_manifest handles non-existent manifest file path."""
    result = verify_merkle_manifest(tmp_path / "non_existent.json", repo_root=tmp_path)
    assert result.ok is False
    assert any("Manifest file not found" in err for err in result.errors)


def test_cli_handle_audit_merkle_generate(sample_repo: Path, capsys: pytest.CaptureFixture):
    """Verifies CLI execution of spec-ops audit merkle generates output without error."""
    parser = argparse.ArgumentParser()
    config = SpecOpsConfig(root_dir=sample_repo)
    args = argparse.Namespace(audit_action="merkle", verify=None, output=None, json=False)

    code = handle_audit_command(args, config, parser)
    assert code == 0
    captured = capsys.readouterr()
    assert "Generated Merkle compliance manifest:" in captured.out
    assert "Merkle Root:" in captured.out


def test_cli_handle_audit_merkle_json(sample_repo: Path, capsys: pytest.CaptureFixture):
    """Verifies CLI execution of spec-ops audit merkle --json outputs valid manifest JSON."""
    parser = argparse.ArgumentParser()
    config = SpecOpsConfig(root_dir=sample_repo)
    args = argparse.Namespace(audit_action="merkle", verify=None, output=None, json=True)

    code = handle_audit_command(args, config, parser)
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "root_hash" in data
    assert "tree_size" in data
    assert len(data["leaves"]) >= 3


def test_cli_handle_audit_merkle_verify_success(sample_repo: Path, capsys: pytest.CaptureFixture):
    """Verifies CLI execution of spec-ops audit merkle --verify on untampered repo returns code 0."""
    manifest_path = sample_repo / "manifest.json"
    generate_merkle_manifest(sample_repo, output_path=manifest_path)

    parser = argparse.ArgumentParser()
    config = SpecOpsConfig(root_dir=sample_repo)
    args = argparse.Namespace(audit_action="merkle", verify=str(manifest_path), output=None, json=False)

    code = handle_audit_command(args, config, parser)
    assert code == 0
    captured = capsys.readouterr()
    assert "Merkle Compliance Manifest PASSED" in captured.out


def test_cli_handle_audit_merkle_verify_failure(sample_repo: Path, capsys: pytest.CaptureFixture):
    """Verifies CLI execution of spec-ops audit merkle --verify on tampered repo returns code 1."""
    manifest_path = sample_repo / "manifest.json"
    generate_merkle_manifest(sample_repo, output_path=manifest_path)

    # Tamper with file
    (sample_repo / "src" / "pkg" / "app.py").write_text("tampered_code()", encoding="utf-8")

    parser = argparse.ArgumentParser()
    config = SpecOpsConfig(root_dir=sample_repo)
    args = argparse.Namespace(audit_action="merkle", verify=str(manifest_path), output=None, json=False)

    code = handle_audit_command(args, config, parser)
    assert code == 1
    captured = capsys.readouterr()
    assert "digest mismatch detected" in captured.err
    assert "src/pkg/app.py" in captured.err
