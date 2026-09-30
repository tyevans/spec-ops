"""Unit and edge-case tests for backlog protection guardrails."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spec_ops.worker.guardrails import (
    detect_backlog_modifications,
    prepare_guardrailed_commit,
    sanitize_backlog_modifications,
    stage_legitimate_files,
)


@pytest.fixture
def git_guard_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)

    backlog = repo / "docs" / "project" / "backlog"
    backlog.mkdir(parents=True, exist_ok=True)
    (backlog / "PRIORITY.md").write_text("# Priority\n", encoding="utf-8")
    (backlog / "task-1.md").write_text("# Task 1\n", encoding="utf-8")

    src = repo / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "app.py").write_text("def run(): pass\n", encoding="utf-8")

    tests = repo / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_app.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def test_detect_backlog_modifications_empty_when_clean(git_guard_repo: Path):
    detected = detect_backlog_modifications(git_guard_repo)
    assert detected == []


def test_detect_backlog_modifications_finds_unstaged_and_untracked(git_guard_repo: Path):
    backlog = git_guard_repo / "docs" / "project" / "backlog"
    (backlog / "PRIORITY.md").write_text("# Modified\n", encoding="utf-8")
    (backlog / "rogue.md").write_text("# Untracked\n", encoding="utf-8")
    (git_guard_repo / "src" / "app.py").write_text("def run(): return 1\n", encoding="utf-8")

    # With leading/trailing slashes
    detected = detect_backlog_modifications(git_guard_repo, backlog_path="/docs/project/backlog/")
    assert set(detected) == {"docs/project/backlog/PRIORITY.md", "docs/project/backlog/rogue.md"}
    assert not any("src/app.py" in d for d in detected)


def test_detect_backlog_modifications_handles_renames_and_spaces(git_guard_repo: Path):
    backlog = git_guard_repo / "docs" / "project" / "backlog"
    # Create file with spaces
    spaced = backlog / "task name with spaces.md"
    spaced.write_text("# Spaced\n", encoding="utf-8")
    subprocess.run(["git", "add", str(spaced)], cwd=git_guard_repo, check=True, capture_output=True)

    # Rename tracked file
    subprocess.run(
        ["git", "mv", "docs/project/backlog/task-1.md", "docs/project/backlog/task-renamed.md"],
        cwd=git_guard_repo,
        check=True,
        capture_output=True,
    )

    detected = detect_backlog_modifications(git_guard_repo)
    assert "docs/project/backlog/task name with spaces.md" in detected
    assert "docs/project/backlog/task-renamed.md" in detected


def test_sanitize_backlog_modifications_reverts_tracked_and_untracked(git_guard_repo: Path):
    backlog = git_guard_repo / "docs" / "project" / "backlog"
    (backlog / "PRIORITY.md").write_text("# Corrupted\n", encoding="utf-8")
    (backlog / "rogue.md").write_text("# Rogue\n", encoding="utf-8")

    reverted = sanitize_backlog_modifications(git_guard_repo, stage_legitimate=False)
    assert set(reverted) == {"docs/project/backlog/PRIORITY.md", "docs/project/backlog/rogue.md"}
    assert (backlog / "PRIORITY.md").read_text(encoding="utf-8") == "# Priority\n"
    assert not (backlog / "rogue.md").exists()

    status = subprocess.run(["git", "status", "--porcelain", "docs/project/backlog"], cwd=git_guard_repo, capture_output=True, text=True)
    assert status.stdout.strip() == ""


def test_sanitize_backlog_clean_state(git_guard_repo: Path):
    reverted = sanitize_backlog_modifications(git_guard_repo, stage_legitimate=False)
    assert reverted == []


def test_stage_legitimate_files_stages_src_and_tests(git_guard_repo: Path):
    (git_guard_repo / "src" / "app.py").write_text("def run(): return 42\n", encoding="utf-8")
    (git_guard_repo / "tests" / "test_app.py").write_text("def test_ok(): assert 1\n", encoding="utf-8")

    # Accidental stage of backlog
    (git_guard_repo / "docs" / "project" / "backlog" / "PRIORITY.md").write_text("# Staged\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/project/backlog/PRIORITY.md"], cwd=git_guard_repo, check=True)

    staged = stage_legitimate_files(git_guard_repo)
    assert "src/app.py" in staged
    assert "tests/test_app.py" in staged
    assert "docs/project/backlog/PRIORITY.md" not in staged


def test_prepare_guardrailed_commit_success(git_guard_repo: Path):
    (git_guard_repo / "src" / "app.py").write_text("def run(): return 99\n", encoding="utf-8")
    (git_guard_repo / "docs" / "project" / "backlog" / "PRIORITY.md").write_text("# Inadvertent edit\n", encoding="utf-8")

    ok, msg = prepare_guardrailed_commit(git_guard_repo, commit_msg="feat: legitimate change")
    assert ok is True
    assert msg == "Commit created cleanly with zero backlog modifications."

    diff = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], cwd=git_guard_repo, capture_output=True, text=True)
    files = [f.strip() for f in diff.stdout.splitlines() if f.strip()]
    assert files == ["src/app.py"]
    assert not any("docs/project/backlog" in f for f in files)


def test_prepare_guardrailed_commit_no_modifications(git_guard_repo: Path):
    (git_guard_repo / "docs" / "project" / "backlog" / "PRIORITY.md").write_text("# Inadvertent edit\n", encoding="utf-8")

    ok, msg = prepare_guardrailed_commit(git_guard_repo, commit_msg="feat: should fail")
    assert ok is False
    assert msg == "No modifications staged to commit."


def test_prepare_guardrailed_commit_git_failure(git_guard_repo: Path, monkeypatch):
    (git_guard_repo / "src" / "app.py").write_text("def run(): return 100\n", encoding="utf-8")

    # Hook git commit to fail
    hook_dir = git_guard_repo / ".git" / "hooks"
    hook_dir.mkdir(parents=True, exist_ok=True)
    pre_commit = hook_dir / "pre-commit"
    pre_commit.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    pre_commit.chmod(0o755)

    ok, msg = prepare_guardrailed_commit(git_guard_repo, commit_msg="feat: will fail")
    assert ok is False
    assert "Git commit failed:" in msg
