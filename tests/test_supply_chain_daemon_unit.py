"""Unit tests for supply-chain lockfile integrity sentinel and attestation logger (TASK-0157)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from spec_ops.cli.main import main
from spec_ops.security.supply_chain_daemon import (
    LockfileAttestation,
    LockfileIntegrityReport,
    SupplyChainSentinel,
    compute_file_sha256,
    handle_audit_lockfile,
)


@pytest.fixture
def repo_dir(tmp_path: Path) -> Path:
    repo = tmp_path / "test_repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname="unit-test"\nversion="1.0.0"\n', encoding="utf-8")
    (repo / "uv.lock").write_text(
        'version = 1\nrevision = 1\n\n[[package]]\nname = "demo-pkg"\nversion = "1.0.0"\n'
        'sdist = { hash = "sha256:1111111111111111111111111111111111111111111111111111111111111111" }\n',
        encoding="utf-8",
    )
    return repo


def test_compute_sha256_missing_file(tmp_path: Path):
    assert compute_file_sha256(tmp_path / "nonexistent.file") == ""


def test_compute_sha256_existing_file(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello world\n")
    expected = hashlib.sha256(b"hello world\n").hexdigest()
    assert compute_file_sha256(f) == expected


def test_compute_digests(repo_dir: Path):
    lock_sha, pyp_sha = SupplyChainSentinel.compute_digests(repo_dir)
    assert len(lock_sha) == 64
    assert len(pyp_sha) == 64
    assert lock_sha == compute_file_sha256(repo_dir / "uv.lock")
    assert pyp_sha == compute_file_sha256(repo_dir / "pyproject.toml")


def test_generate_attestation_valid(repo_dir: Path):
    sentinel = SupplyChainSentinel(repo_dir)
    att = sentinel.generate_attestation(repo_dir)
    assert att.is_valid is True
    assert att.package_count == 1
    assert len(att.discrepancies) == 0
    assert len(att.lockfile_sha256) == 64
    assert len(att.pyproject_sha256) == 64


def test_generate_attestation_missing_uv_lock(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    att = SupplyChainSentinel.generate_attestation(empty_dir)
    assert att.is_valid is False
    assert att.package_count == 0
    assert any("uv.lock" in d or "Lockfile not found" in d for d in att.discrepancies)


def test_generate_attestation_malformed_toml(tmp_path: Path):
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "pyproject.toml").write_text('[project]\nname="bad"\n', encoding="utf-8")
    (bad_dir / "uv.lock").write_text("invalid [[ toml content", encoding="utf-8")

    att = SupplyChainSentinel.generate_attestation(bad_dir)
    assert att.is_valid is False
    assert any("Failed to parse lockfile" in d for d in att.discrepancies)


def test_record_attestation(repo_dir: Path):
    sentinel = SupplyChainSentinel(repo_dir)
    log_file = sentinel.record_attestation(repo_dir)
    assert log_file.is_file()
    assert log_file.name == "lockfile_attestations.jsonl"
    assert log_file.parent.name == ".specops"

    content = log_file.read_text(encoding="utf-8").strip()
    records = [json.loads(line) for line in content.splitlines()]
    assert len(records) == 1
    assert records[0]["package_count"] == 1
    assert records[0]["is_valid"] is True

    # Record second attestation - must append
    sentinel.record_attestation(repo_dir)
    content2 = log_file.read_text(encoding="utf-8").strip()
    records2 = [json.loads(line) for line in content2.splitlines()]
    assert len(records2) == 2


def test_verify_integrity_clean(repo_dir: Path):
    sentinel = SupplyChainSentinel(repo_dir)
    sentinel.record_attestation(repo_dir)

    report = sentinel.verify_integrity(repo_dir)
    assert report.is_clean is True
    assert report.attested_digest == report.current_digest
    assert len(report.discrepancies) == 0
    assert "verified" in report.summary().lower()


def test_verify_integrity_missing_uv_lock(tmp_path: Path):
    sentinel = SupplyChainSentinel(tmp_path)
    report = sentinel.verify_integrity(tmp_path)
    assert report.is_clean is False
    assert any("uv.lock not found" in d for d in report.discrepancies)


def test_verify_integrity_no_baseline(repo_dir: Path):
    sentinel = SupplyChainSentinel(repo_dir)
    report = sentinel.verify_integrity(repo_dir)
    assert report.is_clean is False
    assert report.attested_digest is None
    assert any("no baseline attestation" in d for d in report.discrepancies)


def test_verify_integrity_empty_attestation_file(repo_dir: Path):
    log_file = repo_dir / ".specops" / "lockfile_attestations.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("\n\n   \n", encoding="utf-8")

    sentinel = SupplyChainSentinel(repo_dir)
    report = sentinel.verify_integrity(repo_dir)
    assert report.is_clean is False
    assert any("no attestation entries" in d for d in report.discrepancies)


def test_verify_integrity_corrupted_json_entry(repo_dir: Path):
    log_file = repo_dir / ".specops" / "lockfile_attestations.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("{corrupt json\n", encoding="utf-8")

    sentinel = SupplyChainSentinel(repo_dir)
    report = sentinel.verify_integrity(repo_dir)
    assert report.is_clean is False
    assert any("corrupted attestation record" in d for d in report.discrepancies)


def test_verify_integrity_digest_mismatch(repo_dir: Path):
    sentinel = SupplyChainSentinel(repo_dir)
    sentinel.record_attestation(repo_dir)

    # Tamper with uv.lock
    (repo_dir / "uv.lock").write_text("# tampered\n", encoding="utf-8")

    report = sentinel.verify_integrity(repo_dir)
    assert report.is_clean is False
    assert report.current_digest != report.attested_digest
    assert any("digest mismatch" in d for d in report.discrepancies)
    assert "tampering detected" in report.summary()


def test_verify_integrity_invalid_baseline(repo_dir: Path):
    sentinel = SupplyChainSentinel(repo_dir)
    att = LockfileAttestation(
        timestamp="2026-10-01T00:00:00Z",
        lockfile_sha256=compute_file_sha256(repo_dir / "uv.lock"),
        pyproject_sha256=compute_file_sha256(repo_dir / "pyproject.toml"),
        package_count=1,
        is_valid=False,
        discrepancies=["Baseline was unpinned"],
    )
    sentinel.record_attestation(repo_dir, att)

    report = sentinel.verify_integrity(repo_dir)
    assert report.is_clean is False
    assert "Baseline was unpinned" in report.discrepancies


def test_cli_audit_lockfile_record(repo_dir: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(repo_dir)
    code = main(["security", "audit-lockfile", "--record"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Recorded lockfile attestation" in captured.out


def test_cli_audit_lockfile_record_json(
    repo_dir: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(repo_dir)
    code = main(["security", "audit-lockfile", "--record", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["is_valid"] is True
    assert "lockfile_sha256" in data


def test_cli_audit_lockfile_verify_clean(
    repo_dir: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(repo_dir)
    main(["security", "audit-lockfile", "--record"])
    capsys.readouterr()

    code = main(["security", "audit-lockfile", "--verify"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Lockfile integrity verified" in captured.out


def test_cli_audit_lockfile_verify_tampered(
    repo_dir: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(repo_dir)
    main(["security", "audit-lockfile", "--record"])
    capsys.readouterr()

    # Tamper
    (repo_dir / "uv.lock").write_text("# altered\n", encoding="utf-8")

    code = main(["security", "audit-lockfile", "--verify"])
    assert code == 1
    captured = capsys.readouterr()
    assert "tampering detected" in captured.err


def test_cli_audit_lockfile_verify_json(
    repo_dir: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(repo_dir)
    main(["security", "audit-lockfile", "--record"])
    capsys.readouterr()

    code = main(["security", "audit-lockfile", "--verify", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["is_clean"] is True
    assert "current_digest" in data


def test_cli_audit_lockfile_default_is_verify(
    repo_dir: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(repo_dir)
    main(["security", "audit-lockfile", "--record"])
    capsys.readouterr()

    # Running with no flags defaults to verification
    code = main(["security", "audit-lockfile"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Lockfile integrity verified" in captured.out
