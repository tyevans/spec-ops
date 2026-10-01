"""Executable BDD tests for US-0111: Supply-Chain Lockfile Integrity Sentinel and Attestation Audit."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.cli.main import main
from spec_ops.security.supply_chain_daemon import SupplyChainSentinel

scenarios("features/us_0111_lockfile_integrity.feature")


@pytest.fixture
def bdd_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "pyproject.toml").write_text('[project]\nname="test-project"\nversion="0.1.0"\n', encoding="utf-8")
    (repo / "uv.lock").write_text(
        'version = 1\nrevision = 1\n\n[[package]]\nname = "requests"\nversion = "2.31.0"\n'
        'sdist = { hash = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" }\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(repo)

    return {
        "repo": repo,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "attestation": None,
        "report": None,
    }


@given("a verified repository with an intact uv.lock file")
def verified_repository_intact_lockfile(bdd_context: dict[str, Any]):
    repo = bdd_context["repo"]
    attestation = SupplyChainSentinel.generate_attestation(repo)
    SupplyChainSentinel.record_attestation(repo, attestation)
    bdd_context["attestation"] = attestation


@given("a lockfile modified with unauthorized dependency alterations")
def repository_with_unauthorized_alterations(bdd_context: dict[str, Any]):
    repo = bdd_context["repo"]
    attestation = SupplyChainSentinel.generate_attestation(repo)
    SupplyChainSentinel.record_attestation(repo, attestation)
    bdd_context["attestation"] = attestation

    lock_file = repo / "uv.lock"
    content = lock_file.read_text(encoding="utf-8")
    tampered_content = (
        content
        + '\n[[package]]\nname = "malicious-unapproved-package"\nversion = "0.0.1"\n'
        'sdist = { hash = "sha256:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210" }\n'
    )
    lock_file.write_text(tampered_content, encoding="utf-8")


@when("the security lockfile auditor runs verification")
def auditor_runs_verification(bdd_context: dict[str, Any], capsys: pytest.CaptureFixture):
    exit_code = main(["security", "audit-lockfile", "--verify"])
    captured = capsys.readouterr()
    bdd_context["exit_code"] = exit_code
    bdd_context["stdout"] = captured.out
    bdd_context["stderr"] = captured.err
    repo = bdd_context["repo"]
    bdd_context["report"] = SupplyChainSentinel.verify_integrity(repo)


@then("the calculated digest matches the recorded attestation")
def digest_matches_attestation(bdd_context: dict[str, Any]):
    report = bdd_context["report"]
    assert report.is_clean is True
    assert report.attested_digest is not None
    assert report.current_digest == report.attested_digest
    assert len(report.discrepancies) == 0


@then("the command exits with status 0")
def command_exits_status_0(bdd_context: dict[str, Any]):
    assert bdd_context["exit_code"] == 0


@then("the discrepancy is flagged as an unauthorized supply-chain modification")
def discrepancy_flagged_as_unauthorized_modification(bdd_context: dict[str, Any]):
    report = bdd_context["report"]
    assert report.is_clean is False
    assert len(report.discrepancies) > 0
    full_output = bdd_context["stderr"] + bdd_context["stdout"]
    flagged = any("unauthorized supply-chain modification" in d.lower() for d in report.discrepancies) or (
        "unauthorized supply-chain modification" in full_output.lower()
    )
    assert flagged is True


@then("the command terminates with exit code 1")
def command_terminates_status_1(bdd_context: dict[str, Any]):
    assert bdd_context["exit_code"] == 1
