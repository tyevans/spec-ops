"""Unit tests for rescue lifecycle, pruning, and sandboxing to maximize mutmut kill rate."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from spec_ops.backlog.queue import write_task_file
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.rescue.lifecycle import (
    cleanup_worktree,
    create_worktree,
    get_worktree_branch,
    init_worktree_environment,
    is_worktree_dirty,
    prune_git_worktrees,
)
from spec_ops.rescue.prune import (
    calculate_directory_size,
    format_bytes,
    is_prune_candidate,
    prune_worktrees,
    scan_worktree_candidates,
)
from spec_ops.rescue.sandbox import finish_human_worktree, start_human_worktree
from spec_ops.scaffold.init import init_project


@pytest.fixture
def unit_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="UnitApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, check=True, capture_output=True)
    return repo


def test_format_bytes():
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(1024 * 1024) == "1.0 MB"
    assert format_bytes(int(2.5 * 1024 * 1024)) == "2.5 MB"
    assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"
    assert format_bytes(int(1.2 * 1024 * 1024 * 1024)) == "1.2 GB"


def test_calculate_directory_size(tmp_path: Path):
    non_existent = tmp_path / "ghost"
    assert calculate_directory_size(non_existent) == 0

    d = tmp_path / "calc_dir"
    d.mkdir()
    assert calculate_directory_size(d) == 0

    f1 = d / "file1.txt"
    f1.write_bytes(b"12345")
    f2 = d / "subdir" / "file2.txt"
    f2.parent.mkdir()
    f2.write_bytes(b"67890abcde")

    symlink_file = d / "sym.txt"
    try:
        os.symlink(f1, symlink_file)
    except OSError:
        pass

    size = calculate_directory_size(d)
    assert size == 15


def test_is_worktree_dirty_edge_cases(tmp_path: Path, unit_repo: Path):
    non_existent = tmp_path / "ghost"
    assert not is_worktree_dirty(non_existent)

    regular_file = tmp_path / "not_a_dir.txt"
    regular_file.write_text("hello", encoding="utf-8")
    assert not is_worktree_dirty(regular_file)

    no_git_dir = tmp_path / "plain_dir"
    no_git_dir.mkdir()
    assert not is_worktree_dirty(no_git_dir)

    wt_dir = unit_repo / ".worktrees" / "task-0001"
    create_worktree(unit_repo, branch="feat/task-0001", worktree_dir=wt_dir)
    assert not is_worktree_dirty(wt_dir)

    (wt_dir / "dirty.txt").write_text("change", encoding="utf-8")
    assert is_worktree_dirty(wt_dir)


def test_get_worktree_branch(unit_repo: Path, tmp_path: Path):
    assert get_worktree_branch(tmp_path / "ghost") == ""

    wt_dir = unit_repo / ".worktrees" / "task-0002"
    create_worktree(unit_repo, branch="feat/custom-branch", worktree_dir=wt_dir)
    assert get_worktree_branch(wt_dir) == "feat/custom-branch"


def test_create_worktree_dirty_raises(unit_repo: Path):
    wt_dir = unit_repo / ".worktrees" / "task-0003"
    create_worktree(unit_repo, branch="feat/task-0003", worktree_dir=wt_dir)
    (wt_dir / "human_change.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="worktree contains uncommitted human rescue work"):
        create_worktree(unit_repo, branch="feat/task-0003", worktree_dir=wt_dir, check_dirty=True)


def test_create_worktree_invalid_ref_raises(unit_repo: Path):
    wt_dir = unit_repo / ".worktrees" / "task-0004"
    with pytest.raises(RuntimeError, match="Failed to create worktree"):
        create_worktree(unit_repo, branch="feat/task-0004", worktree_dir=wt_dir, base_ref="non_existent_ref_999")


def test_cleanup_worktree_and_ephemeral_files(unit_repo: Path):
    wt_dir = unit_repo / ".worktrees" / "task-0005"
    branch = "feat/task-0005"
    create_worktree(unit_repo, branch=branch, worktree_dir=wt_dir)

    (wt_dir / ".task-prompt.md").write_text("prompt", encoding="utf-8")
    (wt_dir / ".pytest_cache").mkdir()
    (wt_dir / ".pytest_cache" / "cache.json").write_text("{}", encoding="utf-8")

    cleanup_worktree(unit_repo, wt_dir, branch=branch, delete_branch=True)
    assert not wt_dir.exists()

    chk = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=unit_repo)
    assert chk.returncode != 0


def test_init_worktree_environment(unit_repo: Path):
    wt_dir = unit_repo / ".worktrees" / "task-0006"
    create_worktree(unit_repo, branch="feat/task-0006", worktree_dir=wt_dir)

    (unit_repo / ".venv").mkdir()
    (unit_repo / ".env").write_text("FOO=BAR\n", encoding="utf-8")

    initialized = init_worktree_environment(unit_repo, wt_dir)
    assert ".venv" in initialized
    assert ".env" in initialized
    assert (wt_dir / ".venv").exists()
    assert (wt_dir / ".env").exists()


def test_scan_and_prune_empty_and_skip(unit_repo: Path):
    cfg = load_config(unit_repo)
    candidates, warnings = scan_worktree_candidates(unit_repo, cfg.backlog_dir)
    assert candidates == []
    assert warnings == []

    # Create refined task and dirty worktree
    refined_dir = cfg.backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    task_file = refined_dir / "0007-refined.md"
    task = Task(id="0007", title="Refined Task", status="Refined", file_path=task_file)
    write_task_file(task)

    wt_dir = unit_repo / ".worktrees" / "task-0007"
    create_worktree(unit_repo, branch="feat/TASK-0007", worktree_dir=wt_dir)
    (wt_dir / "edit.txt").write_text("human change", encoding="utf-8")

    cands, warns = scan_worktree_candidates(unit_repo, cfg.backlog_dir)
    assert len(cands) == 1
    assert not cands[0].is_eligible
    assert len(warns) == 1
    assert "Skipping .worktrees/task-0007" in warns[0]
    assert "Run 'spec-ops rescue reset TASK-0007' to force discard." in warns[0]


def test_prune_worktrees_execution(unit_repo: Path):
    cfg = load_config(unit_repo)
    complete_dir = cfg.backlog_dir / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)

    task_file = complete_dir / "0008-complete.md"
    task = Task(id="0008", title="Complete Task", status="Complete", file_path=task_file)
    write_task_file(task)

    wt_dir = unit_repo / ".worktrees" / "task-0008"
    branch = "feat/TASK-0008"
    create_worktree(unit_repo, branch=branch, worktree_dir=wt_dir)

    # Dry run
    pruned_dry, _ = prune_worktrees(unit_repo, cfg.backlog_dir, dry_run=True)
    assert len(pruned_dry) == 1
    assert wt_dir.exists()

    # Actual prune
    pruned_act, _ = prune_worktrees(unit_repo, cfg.backlog_dir, dry_run=False)
    assert len(pruned_act) == 1
    assert not wt_dir.exists()
    chk = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=unit_repo)
    assert chk.returncode != 0


def test_human_sandbox_start_and_finish(unit_repo: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = load_config(unit_repo)
    cfg.quality.preflight = []

    # Non-existent task fails
    ok, msg, wt = start_human_worktree(cfg, "TASK-9999")
    assert not ok
    assert wt is None
    assert "not found in backlog" in msg

    # Create task in refined
    refined_dir = cfg.backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    task_file = refined_dir / "0010-human.md"
    task = Task(id="0010", title="Human Feature", status="Refined", file_path=task_file)
    write_task_file(task)

    # Start human worktree
    ok, msg, wt = start_human_worktree(cfg, "TASK-0010")
    assert ok
    assert wt is not None
    assert wt.exists()
    assert "cd .worktrees/task-0010" in msg

    # Finish from outside without task_id fails
    ok, msg = finish_human_worktree(cfg)
    assert not ok
    assert "Not inside an active task worktree" in msg

    # Implement inside worktree
    (wt / "code.py").write_text("x = 42\n", encoding="utf-8")
    monkeypatch.chdir(wt)

    ok, msg = finish_human_worktree(cfg)
    assert ok
    assert "successfully verified, merged to main" in msg
    assert not wt.exists()
    assert (cfg.backlog_dir / "complete" / "0010-human.md").exists()
