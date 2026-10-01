"""Comprehensive unit tests for WorktreeStashResetter and stash recovery engine (US-0081)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from spec_ops.cli.main import main
from spec_ops.rescue.lifecycle import is_worktree_dirty
from spec_ops.rescue.stash_reset import (
    RescueStashMetadata,
    StashResetResult,
    WorktreeStashResetter,
    apply_rescue_stash,
    clean_reset,
    create_rescue_stash,
    list_rescue_stashes,
    resolve_repo_root,
)
from spec_ops.scaffold.init import init_project


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="UnitApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.test"], cwd=repo, check=True, capture_output=True)

    (repo / "README.md").write_text("# Unit Test\n", encoding="utf-8")
    (repo / "src" / "code.py").parent.mkdir(parents=True, exist_ok=True)
    (repo / "src" / "code.py").write_text("initial = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)
    return repo


@pytest.fixture
def git_worktree(git_repo: Path) -> Path:
    wt_dir = git_repo / ".worktrees" / "task-0159"
    subprocess.run(
        ["git", "worktree", "add", "-b", "feat/TASK-0159", str(wt_dir), "main"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )
    return wt_dir


def test_rescue_stash_metadata_serialization():
    meta = RescueStashMetadata(
        stash_id="stash_123",
        task_id="TASK-0159",
        timestamp="2026-10-01T12:00:00Z",
        branch="feat/TASK-0159",
        patch_file="/tmp/stash.patch",
        modified_files=["file1.py", "file2.py"],
        diff_summary="2 files changed",
    )
    data = meta.to_dict()
    assert data["stash_id"] == "stash_123"
    assert data["task_id"] == "TASK-0159"
    assert data["modified_files"] == ["file1.py", "file2.py"]

    restored = RescueStashMetadata.from_dict(data)
    assert restored.stash_id == meta.stash_id
    assert restored.modified_files == meta.modified_files
    assert restored.diff_summary == meta.diff_summary


def test_stash_reset_result_to_dict_and_summary():
    res = StashResetResult(
        success=True,
        stash_id="stash_001",
        is_clean=True,
        reset_commit="abcdef123456",
        message="Worktree reset to HEAD.",
    )
    d = res.to_dict()
    assert d["success"] is True
    assert d["stash_id"] == "stash_001"
    assert d["is_clean"] is True
    assert d["reset_commit"] == "abcdef123456"

    summary = res.summary()
    assert "[SUCCESS]" in summary
    assert "abcdef1" in summary
    assert "stash_001" in summary

    res_fail = StashResetResult(
        success=False,
        stash_id=None,
        is_clean=False,
        reset_commit="",
        message="git reset failed",
    )
    summary_fail = res_fail.summary()
    assert "[FAILED]" in summary_fail


def test_resolve_repo_root_from_worktree_and_main(git_repo: Path, git_worktree: Path):
    root_from_wt = resolve_repo_root(git_worktree)
    assert root_from_wt.resolve() == git_repo.resolve()

    root_from_main = resolve_repo_root(git_repo)
    assert root_from_main.resolve() == git_repo.resolve()


def test_create_rescue_stash_clean_worktree(git_worktree: Path):
    assert not is_worktree_dirty(git_worktree)
    meta = create_rescue_stash(git_worktree, task_id="TASK-0159")
    assert meta is None


def test_create_rescue_stash_dirty_worktree_and_stashing(git_worktree: Path, git_repo: Path):
    (git_worktree / "src" / "code.py").write_text("modified = 2\n", encoding="utf-8")
    (git_worktree / "src" / "untracked.py").write_text("new = True\n", encoding="utf-8")

    meta = create_rescue_stash(git_worktree, task_id="TASK-0159")
    assert meta is not None
    assert meta.task_id == "TASK-0159"
    assert meta.branch == "feat/TASK-0159"
    assert "src/code.py" in meta.modified_files or any("code.py" in f for f in meta.modified_files)
    assert Path(meta.patch_file).exists()

    stashes = list_rescue_stashes(git_repo, task_id="TASK-0159")
    assert len(stashes) >= 1
    assert stashes[0].stash_id == meta.stash_id


def test_clean_reset_with_and_without_stash(git_worktree: Path):
    # Case 1: Already clean
    res1 = clean_reset(git_worktree, stash=True, task_id="TASK-0159")
    assert res1.success is True
    assert res1.is_clean is True
    assert res1.stash_id is None
    assert "already clean" in res1.message

    # Case 2: Dirty, stash=True
    (git_worktree / "src" / "code.py").write_text("dirty content\n", encoding="utf-8")
    (git_worktree / "src" / "tmp.txt").write_text("scratch\n", encoding="utf-8")
    assert is_worktree_dirty(git_worktree)

    res2 = clean_reset(git_worktree, stash=True, task_id="TASK-0159")
    assert res2.success is True
    assert res2.is_clean is True
    assert res2.stash_id is not None
    assert not is_worktree_dirty(git_worktree)
    assert not (git_worktree / "src" / "tmp.txt").exists()
    assert (git_worktree / "src" / "code.py").read_text(encoding="utf-8") == "initial = 1\n"

    # Case 3: Dirty, stash=False
    (git_worktree / "src" / "code.py").write_text("another dirty content\n", encoding="utf-8")
    res3 = clean_reset(git_worktree, stash=False, task_id="TASK-0159")
    assert res3.success is True
    assert res3.is_clean is True
    assert res3.stash_id is None
    assert (git_worktree / "src" / "code.py").read_text(encoding="utf-8") == "initial = 1\n"


def test_list_and_apply_rescue_stash(git_worktree: Path, git_repo: Path):
    (git_worktree / "src" / "code.py").write_text("stashed line\n", encoding="utf-8")
    meta = create_rescue_stash(git_worktree, task_id="TASK-0159")
    assert meta is not None

    # Reset worktree
    clean_reset(git_worktree, stash=False)

    # Filter stashes
    all_stashes = list_rescue_stashes(git_repo)
    assert len(all_stashes) >= 1
    task_stashes = list_rescue_stashes(git_repo, task_id="TASK-0159")
    assert len(task_stashes) >= 1
    empty_filter = list_rescue_stashes(git_repo, task_id="TASK-9999")
    assert len(empty_filter) == 0

    # Apply stash
    ok, msg = apply_rescue_stash(git_worktree, meta.stash_id)
    assert ok is True
    assert "Successfully applied" in msg
    assert (git_worktree / "src" / "code.py").read_text(encoding="utf-8") == "stashed line\n"

    # Apply non-existent stash
    ok_fail, msg_fail = apply_rescue_stash(git_worktree, "non_existent_stash_id")
    assert ok_fail is False
    assert "not found" in msg_fail


def test_apply_rescue_stash_conflict(git_worktree: Path):
    (git_worktree / "src" / "code.py").write_text("version A\n", encoding="utf-8")
    meta = create_rescue_stash(git_worktree, task_id="TASK-0159")
    assert meta is not None

    # Commit different changes to create conflicting patch target
    (git_worktree / "src" / "code.py").write_text("version B that conflicts violently\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/code.py"], cwd=git_worktree, check=True)
    subprocess.run(["git", "commit", "-m", "conflict setup"], cwd=git_worktree, check=True)

    ok, msg = apply_rescue_stash(git_worktree, meta.stash_id)
    assert ok is False
    assert "failed" in msg.lower() or "error" in msg.lower()


def test_cli_rescue_reset_flags(git_worktree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.chdir(git_worktree)

    # Make dirty
    (git_worktree / "src" / "code.py").write_text("cli dirty\n", encoding="utf-8")
    code = main(["rescue", "reset", "--stash", "--task-id", "TASK-0159", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    data = json.loads(captured.out)
    assert data["success"] is True
    assert data["stash_id"] is not None
    stash_id = data["stash_id"]

    # Test list stashes json
    code_list = main(["rescue", "reset", "--list-stashes", "--json"])
    captured_list = capsys.readouterr()
    assert code_list == 0
    stashes_data = json.loads(captured_list.out)
    assert any(s["stash_id"] == stash_id for s in stashes_data)

    # Test apply stash json
    code_apply = main(["rescue", "reset", "--apply", stash_id, "--json"])
    captured_apply = capsys.readouterr()
    assert code_apply == 0
    apply_data = json.loads(captured_apply.out)
    assert apply_data["success"] is True

    # Test force reset
    code_force = main(["rescue", "reset", "--force"])
    assert code_force == 0
    assert not is_worktree_dirty(git_worktree)
