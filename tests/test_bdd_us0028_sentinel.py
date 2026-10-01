"""Executable BDD scenarios using pytest-bdd for Supply-Chain Lockfile Mutation Sentinel (US-0028, TASK-0127)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project
from spec_ops.security.lockfile_sentinel import (
    PROTECTED_LOCKFILES,
    LockfileSentinelResult,
    detect_lockfile_mutations,
    inspect_lockfile_sentinel,
)

scenarios("features/us_0028_sentinel.feature")


@pytest.fixture
def bdd_sentinel_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "sentinel_bdd_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="SentinelBDDApp", target_dir=repo)

    # Git init
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "BDD Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "bdd@example.com"], cwd=repo, check=True, capture_output=True)

    # Initial baseline commit with standard lockfile
    (repo / "uv.lock").write_text("# Initial uv.lock baseline\n", encoding="utf-8")
    (repo / "package-lock.json").write_text('{"name": "initial"}\n', encoding="utf-8")
    (repo / "requirements.txt").write_text("# Initial requirements\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: baseline commit"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "result": None,
        "modified_file": None,
    }


@given("an isolated worktree with protected lockfiles")
def worktree_with_protected_lockfiles(bdd_sentinel_context: dict[str, Any]):
    repo = bdd_sentinel_context["repo"]
    assert (repo / "uv.lock").is_file()
    assert (repo / "package-lock.json").is_file()


@given("an isolated worktree with an approved waiver")
def worktree_with_approved_waiver(bdd_sentinel_context: dict[str, Any]):
    repo = bdd_sentinel_context["repo"]
    waiver_dir = repo / "docs" / "project" / "compliance" / "waivers"
    waiver_dir.mkdir(parents=True, exist_ok=True)
    (waiver_dir / "WAIVER-0028.md").write_text(
        "---\n"
        "id: WAIVER-0028\n"
        "package: requirements.txt\n"
        "signer: Sasha\n"
        "expires: 2030-12-31\n"
        "signature: valid\n"
        "status: Approved\n"
        "reason: Authorized dependencies update\n"
        "---\n# Waiver 0028\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: add waiver"], cwd=repo, check=True, capture_output=True)


@when(parsers.parse('an autonomous worker modifies "{filename}" without an approved waiver'))
def worker_modifies_lockfile_unauthorized(bdd_sentinel_context: dict[str, Any], filename: str):
    repo = bdd_sentinel_context["repo"]
    target = repo / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Malicious / hallucinated lockfile mutation\n", encoding="utf-8")
    bdd_sentinel_context["modified_file"] = filename


@when(parsers.parse('an autonomous worker modifies "{filename}"'))
def worker_modifies_lockfile(bdd_sentinel_context: dict[str, Any], filename: str):
    repo = bdd_sentinel_context["repo"]
    target = repo / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Authorized updated requirements\n", encoding="utf-8")
    bdd_sentinel_context["modified_file"] = filename


@when("and the sentinel checks the worktree state", target_fixture="sentinel_check")
@when("the sentinel checks the worktree state")
def check_worktree_state(bdd_sentinel_context: dict[str, Any]):
    repo = bdd_sentinel_context["repo"]
    res = inspect_lockfile_sentinel(repo, fix=False)
    bdd_sentinel_context["result"] = res
    return res


@when('the sentinel runs with "--fix"')
def check_worktree_with_fix(bdd_sentinel_context: dict[str, Any]):
    repo = bdd_sentinel_context["repo"]
    res = inspect_lockfile_sentinel(repo, fix=True)
    bdd_sentinel_context["result"] = res
    return res


@then("the lockfile sentinel blocks the execution with a violation")
def sentinel_blocks_execution(bdd_sentinel_context: dict[str, Any]):
    res: LockfileSentinelResult = bdd_sentinel_context["result"]
    assert res.ok is False
    assert res.valid is False
    assert len(res.violations) > 0


@then(parsers.parse('identifies "{filename}" as an unauthorized mutation'))
def sentinel_identifies_unauthorized(bdd_sentinel_context: dict[str, Any], filename: str):
    res: LockfileSentinelResult = bdd_sentinel_context["result"]
    assert filename in res.modified_lockfiles
    assert any(filename in v for v in res.violations)


@then("the unauthorized mutation is reverted")
def unauthorized_mutation_reverted(bdd_sentinel_context: dict[str, Any]):
    res: LockfileSentinelResult = bdd_sentinel_context["result"]
    assert res.ok is True
    assert bdd_sentinel_context["modified_file"] in res.remediated


@then("the worktree returns to a clean valid state")
def worktree_clean_state(bdd_sentinel_context: dict[str, Any]):
    repo = bdd_sentinel_context["repo"]
    mutations = detect_lockfile_mutations(repo)
    assert len(mutations) == 0


@then("the lockfile sentinel allows the modification")
def sentinel_allows_modification(bdd_sentinel_context: dict[str, Any]):
    res: LockfileSentinelResult = bdd_sentinel_context["result"]
    assert res.ok is True
    assert res.valid is True
    assert len(res.violations) == 0


@then("reports that the waiver was applied")
def reports_waiver_applied(bdd_sentinel_context: dict[str, Any]):
    res: LockfileSentinelResult = bdd_sentinel_context["result"]
    assert res.waiver_applied is True
    assert res.waiver_details is not None
    assert "WAIVER-0028" in res.waiver_details
