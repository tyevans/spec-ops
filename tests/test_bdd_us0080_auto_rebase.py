"""BDD step definitions for US-0080: Autonomous Worktree Auto-Rebase and Optimistic Merge Conflict Resolver."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.cli.parser import build_parser
from spec_ops.cli.worker_handler import handle_worker_command
from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.worker.integration import is_rebase_in_progress
from spec_ops.worker.worktree import create_worktree

scenarios("features/us_0080_auto_rebase.feature")


@pytest.fixture
def bdd_rebase_ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="AutoRebaseApp", target_dir=repo, profiles=["core", "bdd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex Architect"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.test"], cwd=repo, check=True, capture_output=True)

    # Initial file
    init_file = repo / "src" / "base.py"
    init_file.parent.mkdir(parents=True, exist_ok=True)
    init_file.write_text("def base_fn():\n    return 0\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial base commit"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    return {"repo": repo, "config": cfg, "monkeypatch": monkeypatch}


# --- Scenario 1: Clean automated rebase onto latest main tip ---


@given(parsers.parse('an active worktree whose branch is 2 commits behind "{main_branch}"'))
def setup_worktree_behind_main(bdd_rebase_ctx: dict[str, Any], main_branch: str):
    repo = bdd_rebase_ctx["repo"]
    wt_dir = repo / ".worktrees" / "task-0147"
    branch = "feat/TASK-0147"

    # Create worktree branch
    create_worktree(repo, branch=branch, worktree_dir=wt_dir)

    # Commit 1 on feature branch in worktree
    feat_file = wt_dir / "src" / "feat_0147.py"
    feat_file.write_text("def feat_0147():\n    return True\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=wt_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add feature 0147"], cwd=wt_dir, check=True, capture_output=True)
    feat_pre_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt_dir, capture_output=True, text=True).stdout.strip()

    # Commit 2 changes on main in the root repo
    main_f1 = repo / "src" / "upstream_1.py"
    main_f1.write_text("UPSTREAM_1 = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: upstream commit 1"], cwd=repo, check=True, capture_output=True)

    main_f2 = repo / "src" / "upstream_2.py"
    main_f2.write_text("UPSTREAM_2 = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: upstream commit 2"], cwd=repo, check=True, capture_output=True)

    bdd_rebase_ctx["wt_dir"] = wt_dir
    bdd_rebase_ctx["branch"] = branch
    bdd_rebase_ctx["feat_pre_sha"] = feat_pre_sha


@when(parsers.parse('the worker executes "{command_str}"'))
def execute_worker_command(bdd_rebase_ctx: dict[str, Any], command_str: str):
    wt_dir = bdd_rebase_ctx["wt_dir"]
    cfg = bdd_rebase_ctx["config"]
    monkeypatch = bdd_rebase_ctx["monkeypatch"]

    monkeypatch.chdir(wt_dir)

    # Execute via public frontdoor CLI parser and handler (ADR-0003)
    cmd_args = command_str.split()[1:]  # strip 'spec-ops'
    parser = build_parser()
    parsed_args = parser.parse_args(cmd_args)
    exit_code = handle_worker_command(parsed_args, cfg)

    bdd_rebase_ctx["exit_code"] = exit_code


@then(parsers.parse('the worktree branch is rebased cleanly onto "{main_branch}"'))
def verify_rebased_cleanly(bdd_rebase_ctx: dict[str, Any], main_branch: str):
    wt_dir = bdd_rebase_ctx["wt_dir"]
    repo = bdd_rebase_ctx["repo"]
    exit_code = bdd_rebase_ctx["exit_code"]

    assert exit_code == 0, f"Expected successful exit code 0, got {exit_code}"
    assert not is_rebase_in_progress(wt_dir), "Rebase should not be in progress"

    # Branch HEAD should now include the latest commit from main
    main_sha = subprocess.run(["git", "rev-parse", main_branch], cwd=repo, capture_output=True, text=True).stdout.strip()
    merge_base = subprocess.run(["git", "merge-base", "HEAD", main_branch], cwd=wt_dir, capture_output=True, text=True).stdout.strip()
    assert merge_base == main_sha, f"Expected merge-base {merge_base} to equal main SHA {main_sha}"

    # Verify feature commit was preserved
    feat_file = wt_dir / "src" / "feat_0147.py"
    assert feat_file.exists(), "Feature file should exist after rebase"


@then("the worktree working directory remains clean")
def verify_working_dir_clean(bdd_rebase_ctx: dict[str, Any]):
    wt_dir = bdd_rebase_ctx["wt_dir"]
    status_res = subprocess.run(["git", "status", "--porcelain"], cwd=wt_dir, capture_output=True, text=True)
    assert not status_res.stdout.strip(), f"Expected clean working directory, but got: {status_res.stdout}"


# --- Scenario 2: Safe conflict abort with diagnostic handover generation ---


@given(parsers.parse('an active worktree with conflicting changes against "{main_branch}"'))
def setup_worktree_with_conflicts(bdd_rebase_ctx: dict[str, Any], main_branch: str):
    repo = bdd_rebase_ctx["repo"]
    wt_dir = repo / ".worktrees" / "task-0147"
    branch = "feat/TASK-0147"

    # Create worktree branch
    create_worktree(repo, branch=branch, worktree_dir=wt_dir)

    # In worktree, modify base.py line 2
    wt_base = wt_dir / "src" / "base.py"
    wt_base.write_text("def base_fn():\n    return 'feature_0147_value'\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=wt_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: modify base_fn in worktree"], cwd=wt_dir, check=True, capture_output=True)
    pre_rebase_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt_dir, capture_output=True, text=True).stdout.strip()

    # In main repo on main branch, modify base.py line 2 differently (creating direct conflict)
    main_base = repo / "src" / "base.py"
    main_base.write_text("def base_fn():\n    return 'upstream_main_conflict_value'\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: conflicting modification on main"], cwd=repo, check=True, capture_output=True)

    bdd_rebase_ctx["wt_dir"] = wt_dir
    bdd_rebase_ctx["branch"] = branch
    bdd_rebase_ctx["pre_rebase_sha"] = pre_rebase_sha


@then("the conflicting rebase is safely aborted")
def verify_conflicting_rebase_aborted(bdd_rebase_ctx: dict[str, Any]):
    wt_dir = bdd_rebase_ctx["wt_dir"]
    branch = bdd_rebase_ctx["branch"]
    pre_sha = bdd_rebase_ctx["pre_rebase_sha"]
    exit_code = bdd_rebase_ctx["exit_code"]

    assert exit_code == 1, f"Expected failure exit code 1 on conflict abort, got {exit_code}"
    assert not is_rebase_in_progress(wt_dir), "Rebase should have been safely aborted"

    # Verify HEAD is not detached
    sym_res = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=wt_dir, capture_output=True, text=True)
    assert sym_res.returncode == 0, "HEAD should not be detached"
    assert sym_res.stdout.strip() == branch, f"Expected branch {branch}, got {sym_res.stdout.strip()}"

    # Verify branch state was restored to pre-rebase SHA
    cur_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt_dir, capture_output=True, text=True).stdout.strip()
    assert cur_sha == pre_sha, f"Expected restored SHA {pre_sha}, got {cur_sha}"


@then(parsers.parse('a conflict diagnostic summary is generated in "{handover_filename}"'))
def verify_conflict_handover_generated(bdd_rebase_ctx: dict[str, Any], handover_filename: str):
    wt_dir = bdd_rebase_ctx["wt_dir"]
    handover_path = wt_dir / handover_filename
    assert handover_path.exists(), f"Expected {handover_filename} to be generated at {handover_path}"

    content = handover_path.read_text(encoding="utf-8")
    assert "Conflict Diagnostic Summary" in content
    assert "base.py" in content
    assert "Exact Failure Log" in content
    assert "TASK-0147" in content
