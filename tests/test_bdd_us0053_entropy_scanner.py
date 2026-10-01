"""BDD tests for US-0053: Shannon Entropy Secret Scanner Rule Plugin Engine."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/us_0053_entropy_scanner.feature")

# A 48-character high-entropy string for test fixtures
SAMPLE_HIGH_ENTROPY_TOKEN = "g7X2kP9mQ4vL1wR8tY5cB3dF6hJ0nS2uV4zW7xY9aB1cD3eF"  # pragma: allowlist secret


@pytest.fixture
def bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Security Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.test"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "target_file": None,
        "last_res": None,
    }


# --- Scenario 1: Detecting high-entropy tokens exceeding custom threshold ---


@given("a staged source file containing an unannotated 48-character high-entropy secret token")
def staged_file_with_unannotated_secret(bdd_ctx: dict[str, Any]):
    repo = bdd_ctx["repo"]
    src_file = repo / "config.py"
    # Unannotated secret in the staged file
    src_file.write_text(
        f'API_SECRET_TOKEN = "{SAMPLE_HIGH_ENTROPY_TOKEN}"\n',  # pragma: allowlist secret
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "config.py"], cwd=repo, check=True, capture_output=True)
    bdd_ctx["target_file"] = src_file


@when("the security scanner evaluates the file using Shannon entropy analysis")
def scan_evaluated_with_entropy(bdd_ctx: dict[str, Any]):
    repo = bdd_ctx["repo"]
    src_file = bdd_ctx["target_file"]
    cmd = [
        sys.executable,
        "-m",
        "spec_ops.cli.main",
        "security",
        "scan",
        "--entropy",
        "--threshold",
        "4.5",
        "--path",
        str(src_file),
    ]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    bdd_ctx["last_res"] = res


@then("the token is flagged as a credential leak risk")
def token_flagged_as_risk(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["last_res"]
    combined_output = f"{res.stdout}\n{res.stderr}"
    assert "credential leak risk" in combined_output or "credential leaks detected" in combined_output
    assert "Shannon entropy" in combined_output or "default-entropy" in combined_output


@then("the security check exits with code 1")
def check_exits_code_1(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["last_res"]
    assert res.returncode == 1


# --- Scenario 2: Respecting custom project allowlists and pragma annotations ---


@given('a test fixture token annotated with "# pragma: allowlist secret"')
def fixture_token_with_pragma(bdd_ctx: dict[str, Any]):
    repo = bdd_ctx["repo"]
    fixture_file = repo / "test_fixture.py"
    fixture_file.write_text(
        f'MOCK_SECRET = "{SAMPLE_HIGH_ENTROPY_TOKEN}"  # pragma: allowlist secret\n',  # pragma: allowlist secret
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "test_fixture.py"], cwd=repo, check=True, capture_output=True)
    bdd_ctx["target_file"] = fixture_file


@when("the security scanner runs in strict entropy mode")
def scan_runs_in_strict_entropy_mode(bdd_ctx: dict[str, Any]):
    repo = bdd_ctx["repo"]
    fixture_file = bdd_ctx["target_file"]
    cmd = [
        sys.executable,
        "-m",
        "spec_ops.cli.main",
        "security",
        "scan",
        "--entropy",
        "--threshold",
        "4.5",
        "--path",
        str(fixture_file),
    ]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    bdd_ctx["last_res"] = res


@then("the annotated token is safely ignored")
def annotated_token_safely_ignored(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["last_res"]
    combined_output = f"{res.stdout}\n{res.stderr}"
    assert "Security Invariant Met: 0 credential leaks detected" in combined_output


@then("the security check passes with exit code 0")
def check_passes_code_0(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["last_res"]
    assert res.returncode == 0, f"Expected 0 but got {res.returncode}:\n{res.stderr}\n{res.stdout}"
