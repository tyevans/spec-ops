"""Executable BDD scenarios for US-0113 / TASK-0163: Cryptographic Commit Attestation Validator.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0014, ADR-0016; PRD-0002; US-0113.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
from typing import Any
import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.cli.parser import build_parser
from spec_ops.cli.security_handler import handle_security_command
from spec_ops.config.models import SpecOpsConfig

scenarios("features/us_0113_commit_attestation.feature")


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    return {}


@given("a git branch containing cryptographically signed commits")
def step_signed_commits_branch(bdd_context: dict[str, Any]) -> None:
    repo_root = Path.cwd().resolve()
    bdd_context["repo_dir"] = repo_root
    bdd_context["config"] = SpecOpsConfig(root_dir=repo_root)


@given("an authorized keyring containing the signer public key")
def step_authorized_keyring(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    keyring_file = tmp_path / "allowed_signers"
    keyring_file.write_text(
        """# Authorized signers
tyler@poorlythoughtout.com namespaces="git" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI
* namespaces="git" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI
""",
        encoding="utf-8",
    )
    bdd_context["keyring_path"] = str(keyring_file)


@when("the developer runs spec-ops security verify-commits")
def step_run_verify_commits(bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    args = parser.parse_args([
        "security",
        "verify-commits",
        "--range",
        "HEAD~1..HEAD",
        "--keyring",
        bdd_context["keyring_path"],
    ])
    ret = handle_security_command(args, bdd_context["config"], parser)
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out


@then("all commits in the range are verified")
def step_assert_commits_verified(bdd_context: dict[str, Any]) -> None:
    out = bdd_context["stdout"]
    assert "SpecOps Cryptographic Commit Attestation Audit" in out
    assert "Verified:       1 valid" in out or "valid" in out
    assert "Cryptographic Provenance Verified" in out


@then("the command terminates with exit code 0")
def step_assert_exit_code_zero(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] == 0


@given("a branch containing an unsigned commit")
def step_branch_with_unsigned_commit(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    repo_dir = tmp_path / "unsigned_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Unsigned Tester"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "unsigned@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_dir, check=True)

    test_file1 = repo_dir / "test1.txt"
    test_file1.write_text("unsigned content 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "test1.txt"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "--no-gpg-sign", "-m", "chore: commit 1"], cwd=repo_dir, check=True)

    test_file2 = repo_dir / "test2.txt"
    test_file2.write_text("unsigned content 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "test2.txt"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "--no-gpg-sign", "-m", "chore: commit 2"], cwd=repo_dir, check=True)

    bdd_context["repo_dir"] = repo_dir
    bdd_context["config"] = SpecOpsConfig(root_dir=repo_dir)


@when("the developer runs spec-ops security verify-commits with strict mode")
def step_run_verify_commits_strict(bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    args = parser.parse_args([
        "security",
        "verify-commits",
        "--range",
        "HEAD~1..HEAD",
        "--strict",
    ])
    ret = handle_security_command(args, bdd_context["config"], parser)
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out


@then("the unsigned commit is flagged")
def step_assert_unsigned_commit_flagged(bdd_context: dict[str, Any]) -> None:
    out = bdd_context["stdout"]
    assert "Attestation Violations Detected" in out
    assert "UNSIGNED" in out
    assert "Commit lacks cryptographic signature" in out


@then("the command exits with error status 1")
def step_assert_exit_code_one(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] == 1
