"""Unit and blackbox frontdoor tests for Lockfile Mutation Sentinel (TASK-0127, ADR-0018)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.cli.main import main
from spec_ops.config.models import SecuritySettings, SpecOpsConfig
from spec_ops.security.lockfile_sentinel import (
    PROTECTED_LOCKFILES,
    detect_lockfile_mutations,
    inspect_lockfile_sentinel,
    is_lockfile_mutation_waived,
    is_protected_lockfile,
    remediate_lockfile_mutations,
)
from spec_ops.scaffold.init import init_project
from spec_ops.worker.guardrails import (
    prepare_guardrailed_commit,
    sanitize_unauthorized_lockfile_mutations,
)
from spec_ops.worker.hooks import PreCommitHookEvaluator


@pytest.fixture
def git_worktree(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="LockfileApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Security Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "security@specops.dev"], cwd=repo, check=True, capture_output=True)

    # Initial baseline commit with standard lockfile
    (repo / "uv.lock").write_text("# Initial uv.lock\n", encoding="utf-8")
    (repo / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text('[project]\nname="test"\nversion="0.1.0"\n', encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: baseline commit"], cwd=repo, check=True, capture_output=True)

    return repo


def test_is_protected_lockfile():
    for name in PROTECTED_LOCKFILES:
        assert is_protected_lockfile(name) is True
        assert is_protected_lockfile(f"subdir/{name}") is True
        assert is_protected_lockfile(f"a/b/c/{name}") is True

    assert is_protected_lockfile("pyproject.toml") is False
    assert is_protected_lockfile("package.json") is False
    assert is_protected_lockfile("Cargo.toml") is False
    assert is_protected_lockfile("README.md") is False


def test_detect_lockfile_mutations_unstaged(git_worktree: Path):
    (git_worktree / "uv.lock").write_text("# Altered content\n", encoding="utf-8")
    detected = detect_lockfile_mutations(git_worktree)
    assert detected == ["uv.lock"]


def test_detect_lockfile_mutations_staged(git_worktree: Path):
    (git_worktree / "package-lock.json").write_text('{"name": "modified"}\n', encoding="utf-8")
    subprocess.run(["git", "add", "package-lock.json"], cwd=git_worktree, check=True, capture_output=True)

    detected = detect_lockfile_mutations(git_worktree)
    assert detected == ["package-lock.json"]


def test_detect_lockfile_mutations_untracked(git_worktree: Path):
    (git_worktree / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    detected = detect_lockfile_mutations(git_worktree)
    assert detected == ["requirements.txt"]


def test_detect_lockfile_mutations_nested_paths(git_worktree: Path):
    sub = git_worktree / "frontend"
    sub.mkdir()
    (sub / "package-lock.json").write_text('{"nested": true}\n', encoding="utf-8")

    detected = detect_lockfile_mutations(git_worktree)
    assert "frontend/package-lock.json" in detected


def test_inspect_sentinel_blocks_unauthorized(git_worktree: Path):
    (git_worktree / "uv.lock").write_text("# Unauthorized mutation\n", encoding="utf-8")

    res = inspect_lockfile_sentinel(git_worktree)
    assert res.ok is False
    assert res.valid is False
    assert "uv.lock" in res.modified_lockfiles
    assert len(res.violations) == 1
    assert "ADR-0018" in res.violations[0]
    assert res.waiver_applied is False


def test_inspect_sentinel_remediates_with_fix(git_worktree: Path):
    lock_file = git_worktree / "uv.lock"
    lock_file.write_text("# Bad modification\n", encoding="utf-8")
    subprocess.run(["git", "add", "uv.lock"], cwd=git_worktree, check=True, capture_output=True)

    # Also add untracked lockfile
    untracked = git_worktree / "Cargo.lock"
    untracked.write_text("[[package]]\nname='bad'\n", encoding="utf-8")

    res = inspect_lockfile_sentinel(git_worktree, fix=True)
    assert res.ok is True
    assert set(res.remediated) == {"uv.lock", "Cargo.lock"}
    assert lock_file.read_text(encoding="utf-8") == "# Initial uv.lock\n"
    assert not untracked.exists()


def test_waiver_via_task_frontmatter(git_worktree: Path):
    subprocess.run(["git", "checkout", "-b", "task/0099-dependency-update"], cwd=git_worktree, check=True, capture_output=True)
    task_dir = git_worktree / "docs" / "project" / "backlog" / "refined"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "0099-dependency-update.md").write_text(
        "---\nid: '0099'\ntitle: Dep Update\nstatus: Refined\nallows_dependencies: true\n---\n# Task\n",
        encoding="utf-8",
    )

    (git_worktree / "uv.lock").write_text("# Authorized change\n", encoding="utf-8")
    res = inspect_lockfile_sentinel(git_worktree)
    assert res.ok is True
    assert res.waiver_applied is True
    assert "allows_dependencies: true" in (res.waiver_details or "")


def test_waiver_not_applied_outside_task_branch(git_worktree: Path):
    task_dir = git_worktree / "docs" / "project" / "backlog" / "refined"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "0099-dependency-update.md").write_text(
        "---\nid: '0099'\ntitle: Dep Update\nstatus: Refined\nallows_dependencies: true\n---\n# Task\n",
        encoding="utf-8",
    )

    (git_worktree / "uv.lock").write_text("# Unauthorized change\n", encoding="utf-8")
    res = inspect_lockfile_sentinel(git_worktree)
    assert res.ok is False
    assert res.waiver_applied is False


def test_waiver_via_specops_toml(git_worktree: Path):
    (git_worktree / "specops.toml").write_text(
        '[project]\nname="test"\n[security]\nallow_lockfile_mutation = true\n',
        encoding="utf-8",
    )
    (git_worktree / "poetry.lock").write_text("[metadata]\n", encoding="utf-8")

    res = inspect_lockfile_sentinel(git_worktree)
    assert res.ok is True
    assert res.waiver_applied is True
    assert "specops.toml" in (res.waiver_details or "")


def test_waiver_via_architectural_waiver(git_worktree: Path):
    waiver_dir = git_worktree / "docs" / "project" / "compliance" / "waivers"
    waiver_dir.mkdir(parents=True, exist_ok=True)
    (waiver_dir / "WAIVER-0042.md").write_text(
        "---\n"
        "id: WAIVER-0042\n"
        "package: uv.lock\n"
        "signer: Sasha\n"
        "expires: 2030-01-01\n"
        "signature: valid\n"
        "status: Approved\n"
        "---\n# Waiver 42\n",
        encoding="utf-8",
    )

    (git_worktree / "uv.lock").write_text("# Waived modification\n", encoding="utf-8")
    res = inspect_lockfile_sentinel(git_worktree)
    assert res.ok is True
    assert res.waiver_applied is True
    assert "WAIVER-0042" in (res.waiver_details or "")


def test_expired_architectural_waiver_rejected(git_worktree: Path):
    waiver_dir = git_worktree / "docs" / "project" / "compliance" / "waivers"
    waiver_dir.mkdir(parents=True, exist_ok=True)
    (waiver_dir / "WAIVER-0010.md").write_text(
        "---\n"
        "id: WAIVER-0010\n"
        "package: uv.lock\n"
        "signer: Sasha\n"
        "expires: 2020-01-01\n"
        "signature: valid\n"
        "status: Approved\n"
        "---\n# Expired Waiver\n",
        encoding="utf-8",
    )

    (git_worktree / "uv.lock").write_text("# Unauthorized mutation\n", encoding="utf-8")
    res = inspect_lockfile_sentinel(git_worktree)
    assert res.ok is False
    assert res.waiver_applied is False


def test_cli_sentinel_clean(git_worktree: Path, monkeypatch, capsys):
    monkeypatch.chdir(git_worktree)
    ret = main(["security", "sentinel"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Lockfile Sentinel passed" in out


def test_cli_sentinel_violation(git_worktree: Path, monkeypatch, capsys):
    monkeypatch.chdir(git_worktree)
    (git_worktree / "uv.lock").write_text("# Bad lockfile edit\n", encoding="utf-8")

    ret = main(["security", "sentinel"])
    assert ret == 1
    err = capsys.readouterr().err
    assert "Supply-Chain Lockfile Mutation Sentinel Violation" in err
    assert "uv.lock" in err


def test_cli_sentinel_json_output(git_worktree: Path, monkeypatch, capsys):
    monkeypatch.chdir(git_worktree)
    (git_worktree / "Cargo.lock").write_text("# cargo lock\n", encoding="utf-8")

    ret = main(["security", "sentinel", "--json"])
    assert ret == 1
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["ok"] is False
    assert "Cargo.lock" in data["modified_lockfiles"]
    assert len(data["violations"]) == 1


def test_cli_sentinel_fix(git_worktree: Path, monkeypatch, capsys):
    monkeypatch.chdir(git_worktree)
    (git_worktree / "uv.lock").write_text("# Tampered\n", encoding="utf-8")

    ret = main(["security", "sentinel", "--fix"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Remediated unauthorized lockfile modification" in out
    assert (git_worktree / "uv.lock").read_text(encoding="utf-8") == "# Initial uv.lock\n"


def test_worker_guardrails_lockfile_sanitization(git_worktree: Path):
    (git_worktree / "uv.lock").write_text("# Dirty\n", encoding="utf-8")

    remediated = sanitize_unauthorized_lockfile_mutations(git_worktree, allows_dependencies=False)
    assert "uv.lock" in remediated
    assert (git_worktree / "uv.lock").read_text(encoding="utf-8") == "# Initial uv.lock\n"


def test_pre_commit_hook_evaluator_catches_lockfile_mutation(git_worktree: Path):
    evaluator = PreCommitHookEvaluator(root_dir=git_worktree)

    # Clean check
    clean_res = evaluator.evaluate()
    assert clean_res.success is True

    # Dirty lockfile
    (git_worktree / "package-lock.json").write_text('{"hacked": true}\n', encoding="utf-8")
    dirty_res = evaluator.evaluate()
    assert dirty_res.success is False
    assert "Supply-Chain Lockfile Sentinel Violations" in dirty_res.output
