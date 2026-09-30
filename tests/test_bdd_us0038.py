"""BDD step definitions for US-0038: Zero-Toil Human Worktree Sandboxing."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.cli.parser import build_parser
from spec_ops.cli.worktree_handler import handle_worktree_command
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.rescue.sandbox import start_human_worktree
from spec_ops.scaffold.init import init_project

scenarios("features/us_0038_human_worktree_sandboxing.feature")


@pytest.fixture
def human_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="SandboxingApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    (repo / ".venv").mkdir()
    (repo / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley Engineer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "riley@specops.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    cfg.quality.preflight = []  # isolate test
    return {"repo": repo, "config": cfg, "monkeypatch": monkeypatch}


@given(parsers.parse('a refined task "{task_id}" in "{folder_path}"'))
def refined_task_in_backlog(human_context: dict[str, Any], task_id: str, folder_path: str):
    repo = human_context["repo"]
    target_dir = repo / folder_path.removeprefix("./")
    target_dir.mkdir(parents=True, exist_ok=True)
    clean_id = task_id.upper().replace("TASK-", "").zfill(4)

    task_file = target_dir / f"{clean_id}-feature.md"
    task = Task(
        id=clean_id,
        title="Human Sandboxed Feature",
        status="Refined",
        file_path=task_file,
    )
    write_task_file(task)
    human_context["task"] = task


@when(parsers.parse('the engineer executes "{cmd}"'))
def engineer_executes_worktree_cmd(human_context: dict[str, Any], cmd: str, capsys: pytest.CaptureFixture):
    cfg = human_context["config"]
    parser = build_parser()
    parts = cmd.split()[1:]  # skip 'spec-ops'
    args = parser.parse_args(parts)
    code = handle_worktree_command(args, cfg)
    captured = capsys.readouterr()
    human_context["exit_code"] = code
    human_context["stdout"] = captured.out
    human_context["stderr"] = captured.err


@then(parsers.parse('a new git worktree is created at "{wt_path}"'))
def new_worktree_created(human_context: dict[str, Any], wt_path: str):
    repo = human_context["repo"]
    wt_dir = repo / wt_path.removeprefix("./")
    assert wt_dir.exists()
    assert (wt_dir / ".git").exists()
    human_context["worktree_dir"] = wt_dir


@then(parsers.parse('a dedicated branch "{branch_name}" is checked out'))
def dedicated_branch_checked_out(human_context: dict[str, Any], branch_name: str):
    wt_dir = human_context["worktree_dir"]
    res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wt_dir, capture_output=True, text=True)
    assert res.stdout.strip() == branch_name


@then("local workspace environment symlinks and configs are initialized in the worktree")
def env_symlinks_initialized(human_context: dict[str, Any]):
    wt_dir = human_context["worktree_dir"]
    assert (wt_dir / ".venv").exists()


@then(parsers.parse('the command outputs the command to enter the workspace: "{enter_cmd}".'))
def command_outputs_enter_cmd(human_context: dict[str, Any], enter_cmd: str):
    stdout = human_context["stdout"]
    assert enter_cmd in stdout


@given(parsers.parse('the engineer is inside "{wt_path}" and has implemented the task'))
def engineer_inside_worktree_implemented(human_context: dict[str, Any], wt_path: str):
    repo = human_context["repo"]
    cfg = human_context["config"]

    if "task" not in human_context:
        refined_dir = repo / "docs" / "project" / "backlog" / "refined"
        refined_dir.mkdir(parents=True, exist_ok=True)
        task_file = refined_dir / "0021-feature.md"
        task = Task(
            id="0021",
            title="Human Sandboxed Feature",
            status="Refined",
            file_path=task_file,
        )
        write_task_file(task)
        human_context["task"] = task

    task = human_context["task"]
    ok, msg, wt_dir = start_human_worktree(cfg, task.canonical_id)
    assert ok
    assert wt_dir is not None

    (wt_dir / "src").mkdir(exist_ok=True)
    (wt_dir / "src" / "feature.py").write_text("# implementation\ndef feature(): return 42\n", encoding="utf-8")

    monkeypatch = human_context["monkeypatch"]
    monkeypatch.chdir(wt_dir)
    human_context["worktree_dir"] = wt_dir


@then("local preflight verification runs across tests, invariants, and linting")
def local_preflight_runs(human_context: dict[str, Any]):
    assert human_context["exit_code"] == 0


@then(parsers.parse('upon preflight success, changes are pushed or squash-merged into "{target_branch}" under MERGE_LOCK'))
def changes_merged_into_main(human_context: dict[str, Any], target_branch: str):
    repo = human_context["repo"]
    res = subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=repo, capture_output=True, text=True)
    assert "feat(task-0021)" in res.stdout


@then(parsers.parse('task "{task_id}" is advanced to "{target_folder}"'))
def task_advanced_to_complete(human_context: dict[str, Any], task_id: str, target_folder: str):
    repo = human_context["repo"]
    complete_dir = repo / "docs" / "project" / "backlog" / target_folder.strip("/")
    files = list(complete_dir.glob("0021*"))
    assert len(files) == 1


@then("the working directory is safely returned to the repository root.")
def working_dir_safely_returned(human_context: dict[str, Any]):
    repo = human_context["repo"]
    assert Path.cwd().resolve() == repo.resolve()
    wt_dir = human_context["worktree_dir"]
    assert not wt_dir.exists()
