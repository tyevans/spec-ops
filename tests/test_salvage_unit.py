"""Unit tests for selective worktree patch takeover and partial file salvage (TASK-0136 / US-0088)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from spec_ops.worker import BacklogWorkerEngine

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.cli.main import main
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.rescue.lifecycle import create_worktree
from spec_ops.rescue.salvage import (
    complete_salvage,
    ensure_rescue_branch,
    format_salvage_commit_message,
    get_rescue_branch_name,
    get_staged_files,
    get_untracked_files,
    normalize_task_id,
    patch_files,
    patch_task,
    run_curated_preflight,
    salvage_files,
    salvage_task,
)
from spec_ops.scaffold.init import init_project


@pytest.fixture
def salvage_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="SalvageApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley Developer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "developer@company.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)
    return repo


def test_normalize_task_id():
    assert normalize_task_id("TASK-0018") == ("TASK-0018", "0018")
    assert normalize_task_id("0018") == ("TASK-0018", "0018")
    assert normalize_task_id("18") == ("TASK-0018", "0018")
    assert normalize_task_id("task-0136") == ("TASK-0136", "0136")
    assert normalize_task_id("0") == ("TASK-0000", "0000")


def test_get_rescue_branch_name(salvage_repo: Path):
    assert get_rescue_branch_name("TASK-0018") == "rescue/task-0018"
    wt_dir = salvage_repo / ".worktrees" / "task-0018"
    create_worktree(salvage_repo, branch="feat/TASK-0018", worktree_dir=wt_dir)

    # When upper branch exists
    subprocess.run(["git", "branch", "rescue/TASK-0018"], cwd=wt_dir, check=True, capture_output=True)
    assert get_rescue_branch_name("TASK-0018", wt_dir) == "rescue/TASK-0018"


def test_format_salvage_commit_message():
    task = Task(
        id="0018",
        title="Implement Core Domain Models",
        status="Refined",
        governing_stories=["US-0088"],
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0005"],
    )

    msg = format_salvage_commit_message(task)
    assert "feat(task-0018): Implement Core Domain Models (rescued)" in msg
    assert "SpecOps-Task: TASK-0018" in msg
    assert "Author: Morgan <agent@specops.local>" in msg
    assert "Rescued-By: Riley <developer@company.com>" in msg
    assert "Provenance: agent-human-hybrid" in msg
    assert "SpecOps-Story: US-0088" in msg
    assert "SpecOps-PRD: PRD-0004" in msg
    assert "SpecOps-ADR: ADR-0005" in msg

    # Custom author & rescued_by
    custom_msg = format_salvage_commit_message(task, author="Claude <claude@anthropic.com>", rescued_by="Alex <alex@specops.org>")
    assert "Author: Claude <claude@anthropic.com>" in custom_msg
    assert "Rescued-By: Alex <alex@specops.org>" in custom_msg


def test_salvage_and_patch_files(salvage_repo: Path):
    cfg = load_config(salvage_repo)
    wt_dir = salvage_repo / ".worktrees" / "task-0018"
    create_worktree(salvage_repo, branch="feat/TASK-0018", worktree_dir=wt_dir)

    # Create files
    models_file = wt_dir / "src" / "models.py"
    models_file.parent.mkdir(parents=True, exist_ok=True)
    models_file.write_text("class DomainModel: pass\n", encoding="utf-8")

    tests_file = wt_dir / "tests" / "test_models.py"
    tests_file.parent.mkdir(parents=True, exist_ok=True)
    tests_file.write_text("def test_model(): pass\n", encoding="utf-8")

    scratch_file = wt_dir / "src" / "scratch_debug.py"
    scratch_file.write_text("# Hallucinated scratch\n", encoding="utf-8")

    bloated_file = wt_dir / "src" / "parser.py"
    bloated_file.write_text("\n".join(["# line"] * 600), encoding="utf-8")

    # 1. Salvage explicitly models.py and tests/test_models.py
    ok, msg = salvage_files(wt_dir, "TASK-0018", ["src/models.py", "tests/test_models.py"])
    assert ok
    staged = get_staged_files(wt_dir)
    assert sorted(staged) == ["src/models.py", "tests/test_models.py"]

    untracked = get_untracked_files(wt_dir)
    assert "src/scratch_debug.py" in untracked
    assert "src/parser.py" in untracked

    # 2. Incrementally patch another clean file
    clean_parser = wt_dir / "src" / "clean_parser.py"
    clean_parser.write_text("def parse(): pass\n", encoding="utf-8")
    ok, patch_msg = patch_files(wt_dir, "TASK-0018", ["src/clean_parser.py"])
    assert ok

    staged_after_patch = get_staged_files(wt_dir)
    assert sorted(staged_after_patch) == ["src/clean_parser.py", "src/models.py", "tests/test_models.py"]
    assert "src/scratch_debug.py" in get_untracked_files(wt_dir)


def test_salvage_nonexistent_file(salvage_repo: Path):
    wt_dir = salvage_repo / ".worktrees" / "task-0018"
    create_worktree(salvage_repo, branch="feat/TASK-0018", worktree_dir=wt_dir)

    ok, msg = salvage_files(wt_dir, "TASK-0018", ["src/does_not_exist.py"])
    assert not ok
    assert "does not exist" in msg


def test_salvage_task_worktree_not_found(salvage_repo: Path):
    cfg = load_config(salvage_repo)
    ok, msg = salvage_task(cfg, "TASK-9999", ["src/a.py"])
    assert not ok
    assert "Worktree not found" in msg


def test_patch_task_worktree_not_found(salvage_repo: Path):
    cfg = load_config(salvage_repo)
    ok, msg = patch_task(cfg, "TASK-9999", ["src/a.py"])
    assert not ok
    assert "Worktree not found" in msg


def test_complete_salvage_end_to_end(salvage_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(salvage_repo)
    cfg = load_config(salvage_repo)

    # 1. Create task in refined
    task = Task(
        id="0018",
        title="Implement Core Domain Models",
        status="Refined",
        governing_stories=["US-0088"],
        file_path=cfg.backlog_dir / "refined" / "0018-core-models.md",
    )
    write_task_file(task)

    priority_file = cfg.backlog_dir / "PRIORITY.md"
    priority_file.write_text("# Backlog Priority Index\n\n- **TASK-0018 (Refined)**: [`0018-core-models`](refined/0018-core-models.md)\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=salvage_repo, check=True)
    subprocess.run(["git", "commit", "-m", "chore: add task 0018"], cwd=salvage_repo, check=True)

    # 2. Provision worktree
    wt_dir = salvage_repo / ".worktrees" / "task-0018"
    create_worktree(salvage_repo, branch="feat/TASK-0018", worktree_dir=wt_dir)

    # 3. Add valid file and scratch file
    valid_file = wt_dir / "valid_model.py"
    valid_file.write_text("class Valid: pass\n", encoding="utf-8")
    scratch_file = wt_dir / "scratch_hallucinated.py"
    scratch_file.write_text("broken invalid syntax &&%$\n", encoding="utf-8")

    # 4. Salvage only valid file
    ok, msg = salvage_task(cfg, "TASK-0018", ["valid_model.py"])
    assert ok
    assert get_staged_files(wt_dir) == ["valid_model.py"]
    assert "scratch_hallucinated.py" in get_untracked_files(wt_dir)

    # 5. Stub run_preflight to succeed
    orig = BacklogWorkerEngine.run_preflight
    BacklogWorkerEngine.run_preflight = lambda self, *args, **kwargs: (True, "Preflight passed")
    try:
        comp_ok, comp_msg = complete_salvage(cfg, "TASK-0018")
        assert comp_ok, f"complete_salvage failed: {comp_msg}"
    finally:
        BacklogWorkerEngine.run_preflight = orig

    # 6. Verify worktree removed
    assert not wt_dir.exists()

    # 7. Verify task completed
    queue = BacklogQueue(cfg.backlog_dir)
    t = next((x for x in queue.list_all_tasks() if x.canonical_id == "TASK-0018"), None)
    assert t is not None
    assert t.status == "Complete"

    # 8. Verify squash commit on main has dual-custody trailers
    log_res = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=salvage_repo, capture_output=True, text=True)
    commit_body = log_res.stdout
    assert "feat(task-0018): Implement Core Domain Models (rescued)" in commit_body
    assert "SpecOps-Task: TASK-0018" in commit_body
    assert "Author: Morgan <agent@specops.local>" in commit_body
    assert "Rescued-By: Riley <developer@company.com>" in commit_body
    assert "Provenance: agent-human-hybrid" in commit_body


def test_cli_rescue_salvage_and_apply(salvage_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(salvage_repo)
    cfg = load_config(salvage_repo)

    # Create task
    task = Task(id="0018", title="Core Models", status="Refined", file_path=cfg.backlog_dir / "refined" / "0018-core-models.md")
    write_task_file(task)
    wt_dir = salvage_repo / ".worktrees" / "task-0018"
    create_worktree(salvage_repo, branch="feat/TASK-0018", worktree_dir=wt_dir)

    f1 = wt_dir / "f1.py"
    f1.write_text("x = 1\n", encoding="utf-8")
    f2 = wt_dir / "f2.py"
    f2.write_text("y = 2\n", encoding="utf-8")

    # CLI salvage
    code_salv = main(["rescue", "salvage", "TASK-0018", "--files", "f1.py"])
    assert code_salv == 0
    assert get_staged_files(wt_dir) == ["f1.py"]

    # CLI patch
    code_patch = main(["rescue", "patch", "TASK-0018", "--include", "f2.py"])
    assert code_patch == 0
    assert sorted(get_staged_files(wt_dir)) == ["f1.py", "f2.py"]
