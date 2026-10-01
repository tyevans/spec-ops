"""BDD step definitions for US-0081: Automated Worktree Stash and Clean Reset Recovery Engine."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.cli.main import main
from spec_ops.config.loader import load_config
from spec_ops.rescue.lifecycle import is_worktree_dirty
from spec_ops.rescue.stash_reset import WorktreeStashResetter
from spec_ops.scaffold.init import init_project

scenarios("features/us_0081_stash_reset.feature")


@pytest.fixture
def repo_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="StashResetApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex Architect"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.test"], cwd=repo, check=True, capture_output=True)

    (repo / "README.md").write_text("# Stash Reset Test\n", encoding="utf-8")
    (repo / "specops.toml").write_text("[project]\nname = 'StashResetApp'\n", encoding="utf-8")
    (repo / "src" / "app.py").parent.mkdir(parents=True, exist_ok=True)
    (repo / "src" / "app.py").write_text("def hello():\n    return 'hello'\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    wt_dir = repo / ".worktrees" / "task-0159"
    subprocess.run(
        ["git", "worktree", "add", "-b", "feat/TASK-0159", str(wt_dir), "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    monkeypatch.chdir(wt_dir)
    cfg = load_config(repo)
    return {
        "repo": repo,
        "wt_dir": wt_dir,
        "config": cfg,
        "exit_code": None,
        "output": "",
        "created_stash_id": None,
    }


@given("a dirty worktree with uncommitted file modifications")
def setup_dirty_worktree(repo_env: dict[str, Any]) -> None:
    wt_dir = repo_env["wt_dir"]
    # 1. Modify tracked file
    (wt_dir / "src" / "app.py").write_text("def hello():\n    return 'dirty modification'\n", encoding="utf-8")
    # 2. Add untracked file
    (wt_dir / "src" / "new_feature.py").write_text("# brand new feature\n", encoding="utf-8")
    assert is_worktree_dirty(wt_dir)


@when("the developer runs spec-ops rescue reset with stash flag")
def run_rescue_reset_stash(repo_env: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    wt_dir = repo_env["wt_dir"]
    code = main(["rescue", "reset", "--stash", "--task-id", "TASK-0159"])
    captured = capsys.readouterr()
    repo_env["exit_code"] = code
    repo_env["output"] = captured.out + captured.err


@then("the uncommitted modifications are archived to a rescue stash")
def verify_stash_archived(repo_env: dict[str, Any]) -> None:
    repo = repo_env["repo"]
    stashes = WorktreeStashResetter.list_rescue_stashes(repo, task_id="TASK-0159")
    assert len(stashes) >= 1
    stash = stashes[0]
    repo_env["created_stash_id"] = stash.stash_id
    assert Path(stash.patch_file).exists()
    patch_text = Path(stash.patch_file).read_text(encoding="utf-8")
    assert "dirty modification" in patch_text or "new_feature.py" in patch_text


@then("the worktree is cleanly reset to pristine HEAD state")
def verify_worktree_clean_head(repo_env: dict[str, Any]) -> None:
    wt_dir = repo_env["wt_dir"]
    assert not is_worktree_dirty(wt_dir)
    assert not (wt_dir / "src" / "new_feature.py").exists()
    assert (wt_dir / "src" / "app.py").read_text(encoding="utf-8") == "def hello():\n    return 'hello'\n"


@then("exits with code 0")
def verify_exit_code_zero(repo_env: dict[str, Any]) -> None:
    assert repo_env["exit_code"] == 0


@given("a previously created rescue stash for a worktree")
def setup_previously_created_stash(repo_env: dict[str, Any]) -> None:
    wt_dir = repo_env["wt_dir"]
    # Dirty the worktree and stash it
    (wt_dir / "src" / "app.py").write_text("def hello():\n    return 'archived version'\n", encoding="utf-8")
    meta = WorktreeStashResetter.create_rescue_stash(wt_dir, task_id="TASK-0159")
    assert meta is not None
    repo_env["created_stash_id"] = meta.stash_id
    # Reset worktree cleanly
    WorktreeStashResetter.clean_reset(wt_dir, stash=False, task_id="TASK-0159")
    assert not is_worktree_dirty(wt_dir)


@when("the developer inspects available rescue archives")
def inspect_available_archives(repo_env: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["rescue", "reset", "--list-stashes", "--task-id", "TASK-0159"])
    captured = capsys.readouterr()
    repo_env["exit_code"] = code
    repo_env["output"] = captured.out + captured.err


@then("the stash details, timestamp, and diff summary are visible")
def verify_stash_details_visible(repo_env: dict[str, Any]) -> None:
    out = repo_env["output"]
    stash_id = repo_env["created_stash_id"]
    assert stash_id in out
    assert "TASK-0159" in out
    assert "Diff Summary" in out or "Summary" in out or "file" in out


@then("can be selectively reapplied")
def verify_selective_reapplication(repo_env: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    wt_dir = repo_env["wt_dir"]
    stash_id = repo_env["created_stash_id"]
    code = main(["rescue", "reset", "--apply", stash_id, "--task-id", "TASK-0159"])
    captured = capsys.readouterr()
    assert code == 0
    assert "Successfully applied" in captured.out
    assert (wt_dir / "src" / "app.py").read_text(encoding="utf-8") == "def hello():\n    return 'archived version'\n"
