"""BDD step definitions for US-0092: Zero-Pollution Worktree Garbage Collection and Orphan Pruning."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.cli.parser import build_parser
from spec_ops.cli.rescue_handler import handle_rescue_command
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.rescue.lifecycle import create_worktree
from spec_ops.scaffold.init import init_project

scenarios("features/us_0092_zero_pollution_worktree_pruning.feature")


@pytest.fixture
def prune_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="PruneApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley Developer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "riley@specops.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    return {"repo": repo, "config": cfg}


@given(parsers.parse('worktree directory "{wt_path}" exists on disk'))
def worktree_dir_exists(prune_context: dict[str, Any], wt_path: str):
    repo = prune_context["repo"]
    wt_dir = repo / wt_path.removeprefix("./")
    branch = f"feat/{wt_dir.name.upper()}"
    create_worktree(repo, branch=branch, worktree_dir=wt_dir)
    prune_context["target_wt"] = wt_dir
    prune_context["target_branch"] = branch


@given(parsers.parse('task "{task_id}" is already marked "complete" in "{folder_path}"'))
def task_marked_complete(prune_context: dict[str, Any], task_id: str, folder_path: str):
    repo = prune_context["repo"]
    complete_dir = repo / folder_path.removeprefix("./")
    complete_dir.mkdir(parents=True, exist_ok=True)
    clean_id = task_id.upper().replace("TASK-", "").zfill(4)

    task_file = complete_dir / f"{clean_id}-completed.md"
    task = Task(
        id=clean_id,
        title="Completed Task",
        status="Complete",
        file_path=task_file,
    )
    write_task_file(task)
    prune_context["task"] = task


@given(parsers.parse('worktree directory "{wt_path}" has uncommitted local changes authored by the engineer'))
def worktree_has_dirty_changes(prune_context: dict[str, Any], wt_path: str):
    repo = prune_context["repo"]
    wt_dir = repo / wt_path.removeprefix("./")
    branch = f"feat/{wt_dir.name.upper()}"
    create_worktree(repo, branch=branch, worktree_dir=wt_dir)
    (wt_dir / "active_work.py").write_text("# human modifications\nx = 10\n", encoding="utf-8")
    prune_context["target_wt"] = wt_dir
    prune_context["target_branch"] = branch


@given(parsers.parse('task "{task_id}" remains in "{folder_path}"'))
def task_remains_in_folder(prune_context: dict[str, Any], task_id: str, folder_path: str):
    repo = prune_context["repo"]
    target_dir = repo / folder_path.removeprefix("./")
    target_dir.mkdir(parents=True, exist_ok=True)
    clean_id = task_id.upper().replace("TASK-", "").zfill(4)

    task_file = target_dir / f"{clean_id}-active.md"
    task = Task(
        id=clean_id,
        title="Active Task",
        status="Refined",
        file_path=task_file,
    )
    write_task_file(task)
    prune_context["task"] = task


@given(parsers.parse("{count:d} stale worktrees totaling {size_str} of disk space"))
def create_stale_worktrees(prune_context: dict[str, Any], count: int, size_str: str):
    repo = prune_context["repo"]
    cfg = prune_context["config"]
    complete_dir = cfg.backlog_dir / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)

    stale_dirs = []
    bytes_per_wt = int(1.2 * (1024**3) / count)
    for i in range(1, count + 1):
        tid = f"000{i}"
        wt_dir = repo / ".worktrees" / f"task-{tid}"
        branch = f"feat/TASK-{tid}"
        create_worktree(repo, branch=branch, worktree_dir=wt_dir)
        task_file = complete_dir / f"{tid}.md"
        t = Task(
            id=tid,
            title=f"Completed {tid}",
            status="Complete",
            file_path=task_file,
        )
        write_task_file(t)

        large_file = wt_dir / "large_cache.bin"
        with open(large_file, "wb") as f:
            f.seek(bytes_per_wt - 1)
            f.write(b"\0")
        subprocess.run(["git", "add", "-A"], cwd=wt_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "chore: stale worktree cache"], cwd=wt_dir, check=True, capture_output=True)
        stale_dirs.append(wt_dir)
    prune_context["stale_dirs"] = stale_dirs


@when(parsers.parse('the engineer executes "{cmd}"'))
def engineer_executes_cli_command(prune_context: dict[str, Any], cmd: str, capsys: pytest.CaptureFixture):
    cfg = prune_context["config"]
    parser = build_parser()
    parts = cmd.split()[1:]  # skip 'spec-ops'
    args = parser.parse_args(parts)
    code = handle_rescue_command(args, cfg)
    captured = capsys.readouterr()
    prune_context["exit_code"] = code
    prune_context["stdout"] = captured.out
    prune_context["stderr"] = captured.err


@then(parsers.parse('the CLI identifies "{wt_path}" as an orphaned completed worktree'))
def cli_identifies_orphaned(prune_context: dict[str, Any], wt_path: str):
    stdout = prune_context["stdout"]
    assert f"Identified {wt_path} as an orphaned completed worktree" in stdout


@then(parsers.parse('safely runs "{cmd}"'))
def safely_runs_remove(prune_context: dict[str, Any], cmd: str):
    target_wt = prune_context["target_wt"]
    assert not target_wt.exists()


@then(parsers.parse('deletes the merged local branch "{branch_name}"'))
def deletes_merged_branch(prune_context: dict[str, Any], branch_name: str):
    repo = prune_context["repo"]
    chk = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], cwd=repo)
    assert chk.returncode != 0


@then(parsers.parse('executes "{cmd}".'))
def executes_prune(prune_context: dict[str, Any], cmd: str):
    assert prune_context["exit_code"] == 0


@then(parsers.parse('the CLI skips "{wt_path}"'))
def cli_skips_dirty_worktree(prune_context: dict[str, Any], wt_path: str):
    target_wt = prune_context["target_wt"]
    assert target_wt.exists()


@then("displays a protection warning:")
def displays_protection_warning(prune_context: dict[str, Any], docstring: str):
    stdout = prune_context["stdout"]
    assert docstring.strip() in stdout


@then("no filesystem modifications are made")
def no_filesystem_modifications(prune_context: dict[str, Any]):
    stale_dirs = prune_context["stale_dirs"]
    for d in stale_dirs:
        assert d.exists()


@then("the CLI prints a table of candidates for pruning, their branch names, and estimated reclaimable space.")
def cli_prints_candidate_table(prune_context: dict[str, Any]):
    stdout = prune_context["stdout"]
    assert "Candidate Worktrees for Pruning:" in stdout
    assert "Estimated Space" in stdout
    assert "1.2 GB" in stdout
    assert "(Dry run mode: no filesystem modifications made)" in stdout
