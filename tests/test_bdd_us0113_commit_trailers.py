"""Executable BDD scenarios for US-0113 / TASK-0168: Commit Trailer Sanitizer Pre-Gate.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0014, ADR-0016; PRD-0002; US-0113; TASK-0168.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any
import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.cli.parser import build_parser
from spec_ops.cli.security_handler import handle_security_command
from spec_ops.config.models import SpecOpsConfig

scenarios("features/us_0113_commit_trailers.feature")


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    return {}


def _git(repo_dir: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=repo_dir, capture_output=True, text=True, check=True)
    return res.stdout.strip()


@given("a git branch with conventional commit messages and valid SpecOps trailers")
def step_given_compliant_git_branch(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "commit.gpgsign", "false")

    # Initial base commit on main
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "chore: initial commit\n\nSpecOps-Task: TASK-0001")
    _git(tmp_path, "branch", "-M", "main")

    # Feature branch with compliant commit
    _git(tmp_path, "checkout", "-b", "feat/test")
    (tmp_path / "feature.py").write_text("print('feat')\n", encoding="utf-8")
    _git(tmp_path, "add", "feature.py")
    msg = """feat(security): implement trailer sanitizer pre-gate

SpecOps-Task: TASK-0168
SpecOps-Story: US-0113
SpecOps-PRD: PRD-0002
SpecOps-ADR: ADR-0001, ADR-0016
Provenance: spec-ops-worker (autonomous)"""
    _git(tmp_path, "commit", "-m", msg)

    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)


@when("the trailer sanitizer validates the commit range")
def step_when_validate_commit_range(
    bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    parser = build_parser()
    args = parser.parse_args(["security", "check-trailers", "--range", "main..HEAD"])
    ret = handle_security_command(args, bdd_context["config"], parser)
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out
    bdd_context["stderr"] = captured.err


@then("all commits pass validation")
def step_then_all_commits_pass(bdd_context: dict[str, Any]) -> None:
    assert "All commits comply" in bdd_context["stdout"] or "Compliant:     1/1" in bdd_context["stdout"]


@then("the command terminates with exit code 0")
def step_then_exit_zero(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] == 0


@given('a git commit lacking the required "SpecOps-Task" trailer')
def step_given_non_compliant_commit(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "commit.gpgsign", "false")

    (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
    _git(tmp_path, "add", "base.txt")
    _git(tmp_path, "commit", "-m", "chore: base commit\n\nSpecOps-Task: TASK-0001")
    _git(tmp_path, "branch", "-M", "main")

    _git(tmp_path, "checkout", "-b", "feat/missing-trailer")
    (tmp_path / "code.py").write_text("print('code')\n", encoding="utf-8")
    _git(tmp_path, "add", "code.py")
    # Commit missing SpecOps-Task
    bad_msg = """feat(security): commit missing required trailer

SpecOps-Story: US-0113"""
    _git(tmp_path, "commit", "-m", bad_msg)

    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)


@when("the trailer sanitizer runs with strict mode")
def step_when_validate_strict(
    bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    parser = build_parser()
    args = parser.parse_args(["security", "check-trailers", "--range", "main..HEAD", "--strict"])
    ret = handle_security_command(args, bdd_context["config"], parser)
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out
    bdd_context["stderr"] = captured.err


@then("the non-compliant commit is flagged with missing trailer details")
def step_then_flagged_with_missing_details(bdd_context: dict[str, Any]) -> None:
    err = bdd_context["stderr"] + bdd_context["stdout"]
    assert "Missing required trailer 'SpecOps-Task'" in err
    assert "failed" in err.lower()


@then("the command terminates with exit code 1")
def step_then_exit_one(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] == 1
