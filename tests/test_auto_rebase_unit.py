"""Unit tests for autonomous worktree auto-rebase and conflict resolver."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from spec_ops.cli.parser import build_parser
from spec_ops.cli.worker_handler import handle_worker_command, handle_worker_rebase
from spec_ops.config.loader import load_config
from spec_ops.worker.auto_rebase import (
    AutoRebaseResult,
    canonicalize_task_id,
    cleanup_git_locks,
    resolve_target_worktree,
    auto_rebase_worktree,
)


def test_auto_rebase_result_to_dict():
    res = AutoRebaseResult(
        success=True,
        task_id="TASK-0147",
        status="clean",
        message="Rebased cleanly",
        conflicted_files=["src/mod.py"],
        handover_path="HANDOVER.md",
        pre_rebase_sha="abcdef1",
        current_head="1234567",
    )
    d = res.to_dict()
    assert d["success"] is True
    assert d["task_id"] == "TASK-0147"
    assert d["status"] == "clean"
    assert d["conflicted_files"] == ["src/mod.py"]
    assert d["handover_path"] == "HANDOVER.md"
    assert d["pre_rebase_sha"] == "abcdef1"
    assert d["current_head"] == "1234567"


def test_canonicalize_task_id():
    assert canonicalize_task_id(None) is None
    assert canonicalize_task_id("") is None
    assert canonicalize_task_id("TASK-0147") == "TASK-0147"
    assert canonicalize_task_id("task-147") == "TASK-0147"
    assert canonicalize_task_id("147") == "TASK-0147"
    assert canonicalize_task_id("0042") == "TASK-0042"


def test_cleanup_git_locks(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    git_dir = repo / ".git"
    idx_lock = git_dir / "index.lock"
    idx_lock.write_text("lock", encoding="utf-8")
    reb_dir = git_dir / "rebase-merge"
    reb_dir.mkdir()

    cleanup_git_locks(repo)
    assert not idx_lock.exists()
    assert not reb_dir.exists()


def test_auto_rebase_non_git_dir(tmp_path: Path):
    non_git = tmp_path / "non_git"
    non_git.mkdir()
    res = auto_rebase_worktree(worktree_dir=non_git, task_id="TASK-0147")
    assert res.success is False
    assert res.status == "error"
    assert "not a git worktree" in res.message or "not a valid git" in res.message


def test_auto_rebase_up_to_date(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.org"], cwd=repo, check=True, capture_output=True)

    f = repo / "file.txt"
    f.write_text("content", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)

    subprocess.run(["git", "checkout", "-b", "feat/TASK-0147"], cwd=repo, check=True, capture_output=True)

    res = auto_rebase_worktree(worktree_dir=repo, task_id="TASK-0147")
    assert res.success is True
    assert res.status == "up_to_date"
    assert "up to date" in res.message


def test_cli_parser_rebase_options():
    parser = build_parser()
    args = parser.parse_args(["worker", "rebase", "TASK-0147", "--abort-on-conflict", "--dry-run", "--json"])
    assert args.command == "worker"
    assert args.worker_action == "rebase"
    assert args.task_pos == "TASK-0147"
    assert args.abort_on_conflict is True
    assert args.dry_run is True
    assert args.json is True


def test_worker_rebase_json_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.org"], cwd=repo, check=True, capture_output=True)

    f = repo / "file.txt"
    f.write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    subprocess.run(["git", "checkout", "-b", "feat/TASK-0147"], cwd=repo, check=True, capture_output=True)
    cfg = load_config(repo)

    monkeypatch.chdir(repo)

    parser = build_parser()
    args = parser.parse_args(["worker", "rebase", "TASK-0147", "--json"])
    code = handle_worker_command(args, cfg)
    assert code == 0

    out, _ = capsys.readouterr()
    data = json.loads(out)
    assert data["success"] is True
    assert data["status"] == "up_to_date"
    assert data["task_id"] == "TASK-0147"
