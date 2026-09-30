"""BDD step definitions for US-0035: Stalled Autonomous Worktree Inspection and Diagnostic Takeover."""

from __future__ import annotations

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

scenarios("features/us_0035_stalled_worktree_inspection_takeover.feature")


@pytest.fixture
def takeover_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="TakeoverApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley Developer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "riley@specops.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    # Clear preflight commands so test runs fast and deterministic
    cfg.quality.preflight = []

    return {"repo": repo, "config": cfg}


@given(parsers.parse('an autonomous worker session has exhausted its self-healing attempts on task "{task_id}"'))
def worker_exhausted_task(takeover_ctx: dict[str, Any], task_id: str):
    cfg = takeover_ctx["config"]
    clean_id = task_id.upper().replace("TASK-", "").zfill(4)
    refined_dir = cfg.backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    t = Task(
        id=clean_id,
        title=f"Autonomous Task {clean_id}",
        status="Refined",
        file_path=refined_dir / f"{clean_id}.md",
        claimed_by="spec-ops-worker",
    )
    write_task_file(t)
    takeover_ctx["task_id"] = task_id
    takeover_ctx["task"] = t


@given(parsers.parse('the isolated worktree "{wt_path}" is preserved with preflight diagnostics in ".task-prompt.md"'))
def worktree_preserved_with_diagnostics(takeover_ctx: dict[str, Any], wt_path: str):
    repo = takeover_ctx["repo"]
    wt_dir = repo / wt_path.removeprefix("./")
    task_id = takeover_ctx["task_id"]
    branch = f"feat/{task_id}"
    create_worktree(repo, branch=branch, worktree_dir=wt_dir)

    prompt_file = wt_dir / ".task-prompt.md"
    prompt_file.write_text(
        "# Prompt\n\n## Preflight Failure Feedback\npytest failed with 1 assertion error\n",
        encoding="utf-8",
    )
    (wt_dir / "work.py").write_text("x = 10\n", encoding="utf-8")

    takeover_ctx["wt_dir"] = wt_dir
    takeover_ctx["branch"] = branch


@given(parsers.parse('an inspected worktree for "{task_id}"'))
def inspected_worktree_setup(takeover_ctx: dict[str, Any], task_id: str):
    worker_exhausted_task(takeover_ctx, task_id)
    clean_id = task_id.lower().replace("task-", "")
    worktree_preserved_with_diagnostics(takeover_ctx, f".worktrees/task-{clean_id}")


@given(parsers.parse('a stalled worktree "{wt_path}" that is deemed unrecoverable'))
def stalled_worktree_unrecoverable(takeover_ctx: dict[str, Any], wt_path: str):
    clean_num = wt_path.split("-")[-1]
    tid = f"TASK-{clean_num}"
    worker_exhausted_task(takeover_ctx, tid)
    worktree_preserved_with_diagnostics(takeover_ctx, wt_path)


@when(parsers.parse('the engineer executes "{cmd}"'))
def engineer_executes_rescue_cmd(takeover_ctx: dict[str, Any], cmd: str, capsys: pytest.CaptureFixture):
    cfg = takeover_ctx["config"]
    parser = build_parser()
    parts = cmd.split()[1:]
    args = parser.parse_args(parts)
    code = handle_rescue_command(args, cfg)
    captured = capsys.readouterr()
    takeover_ctx["stdout"] = captured.out
    takeover_ctx["stderr"] = captured.err
    takeover_ctx["exit_code"] = code


@then("the CLI displays the worktree directory path, git branch, and dirty status")
def cli_displays_worktree_path_branch_dirty(takeover_ctx: dict[str, Any]):
    stdout = takeover_ctx["stdout"]
    wt_dir = takeover_ctx["wt_dir"]
    branch = takeover_ctx["branch"]
    assert str(wt_dir) in stdout
    assert branch in stdout
    assert "Dirty:" in stdout


@then('the last preflight error diagnostics from ".task-prompt.md" are rendered to the terminal')
def cli_displays_preflight_diagnostics(takeover_ctx: dict[str, Any]):
    stdout = takeover_ctx["stdout"]
    assert "pytest failed with 1 assertion error" in stdout


@then("instructions are provided for completing or discarding the rescue.")
def cli_displays_instructions(takeover_ctx: dict[str, Any]):
    stdout = takeover_ctx["stdout"]
    assert "--complete" in stdout
    assert "--discard" in stdout


@then("the task claim is transferred to the human developer and instructions are printed.")
def task_claim_transferred_to_human(takeover_ctx: dict[str, Any]):
    stdout = takeover_ctx["stdout"]
    assert "claim transferred to human developer: riley" in stdout or "claim transferred to human developer" in stdout
    cfg = takeover_ctx["config"]
    clean_id = takeover_ctx["task_id"].upper().replace("TASK-", "").zfill(4)
    task_file = cfg.backlog_dir / "refined" / f"{clean_id}.md"
    assert task_file.exists()
    assert "claimed_by: riley" in task_file.read_text(encoding="utf-8")


@then("preflight verification executes inside the worktree")
def preflight_verification_executes(takeover_ctx: dict[str, Any]):
    assert takeover_ctx["exit_code"] == 0


@then(parsers.parse('upon preflight passing, any uncommitted changes are committed with trailer "{trailer}"'))
def uncommitted_changes_committed_with_trailer(takeover_ctx: dict[str, Any], trailer: str):
    repo = takeover_ctx["repo"]
    log_res = subprocess.run(["git", "log", "-1", "--pretty=full"], cwd=repo, capture_output=True, text=True)
    assert trailer in log_res.stdout


@then(parsers.parse('the feature branch is squash-merged into "{target_branch}" under MERGE_LOCK'))
def branch_squash_merged(takeover_ctx: dict[str, Any], target_branch: str):
    repo = takeover_ctx["repo"]
    chk = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture_output=True, text=True)
    assert chk.stdout.strip() == target_branch


@then(parsers.parse('task "{task_id}" is moved from "{from_folder}" to "{to_folder}"'))
def task_moved_to_complete(takeover_ctx: dict[str, Any], task_id: str, from_folder: str, to_folder: str):
    repo = takeover_ctx["repo"]
    clean_id = task_id.upper().replace("TASK-", "").zfill(4)
    from_file = repo / from_folder.removeprefix("./") / f"{clean_id}.md"
    to_file = repo / to_folder.removeprefix("./") / f"{clean_id}.md"
    assert not from_file.exists()
    assert to_file.exists()


@then("the isolated worktree directory and branch are cleanly removed.")
def worktree_and_branch_removed(takeover_ctx: dict[str, Any]):
    wt_dir = takeover_ctx["wt_dir"]
    branch = takeover_ctx["branch"]
    repo = takeover_ctx["repo"]
    assert not wt_dir.exists()
    chk = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo)
    assert chk.returncode != 0


@then(parsers.parse('the worktree directory "{wt_path}" is deleted'))
def worktree_directory_deleted(takeover_ctx: dict[str, Any], wt_path: str):
    repo = takeover_ctx["repo"]
    wt_dir = repo / wt_path.removeprefix("./")
    assert not wt_dir.exists()


@then("its associated git branch is deleted")
def branch_deleted(takeover_ctx: dict[str, Any]):
    branch = takeover_ctx["branch"]
    repo = takeover_ctx["repo"]
    chk = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo)
    assert chk.returncode != 0


@then(parsers.parse('task "{task_id}" remains safely in "{folder_path}" for re-assignment.'))
def task_remains_safely_in_folder(takeover_ctx: dict[str, Any], task_id: str, folder_path: str):
    repo = takeover_ctx["repo"]
    clean_id = task_id.upper().replace("TASK-", "").zfill(4)
    task_file = repo / folder_path.removeprefix("./") / f"{clean_id}.md"
    assert task_file.exists()
