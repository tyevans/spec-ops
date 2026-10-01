"""BDD step definitions for US-0092: Proactive Worktree Disk Quota Monitor and Orphan Pruning Daemon."""

from __future__ import annotations

import os
import subprocess
import time
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

scenarios("features/us_0092_worktree_quota.feature")


def _age_directory(dir_path: Path, seconds_ago: float) -> None:
    """Sets modification and access timestamps on a directory and all its files."""
    past = time.time() - seconds_ago
    for root, dirs, files in os.walk(dir_path):
        for name in dirs + files:
            try:
                os.utime(Path(root) / name, (past, past))
            except OSError:
                pass
    os.utime(dir_path, (past, past))


@pytest.fixture
def quota_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="QuotaApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley Developer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "riley@specops.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    return {"repo": repo, "config": cfg}


@given('multiple git worktrees in ".worktrees/" with merged and unmerged tasks')
def setup_multiple_worktrees(quota_context: dict[str, Any]):
    repo = quota_context["repo"]
    cfg = quota_context["config"]

    # 1. Completed & merged worktree: task-0005
    wt_0005 = repo / ".worktrees" / "task-0005"
    create_worktree(repo, branch="feat/TASK-0005", worktree_dir=wt_0005)
    (wt_0005 / "feature_0005.py").write_text("def f(): return True\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=wt_0005, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: 0005 feature"], cwd=wt_0005, check=True, capture_output=True)
    # Merge into main
    subprocess.run(["git", "merge", "feat/TASK-0005", "--no-ff", "-m", "merge feat/TASK-0005"], cwd=repo, check=True, capture_output=True)
    # Mark task complete in backlog
    complete_dir = cfg.backlog_dir / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    t5 = Task(id="0005", title="Completed Task 0005", status="Complete", file_path=complete_dir / "0005-completed.md")
    write_task_file(t5)

    # 2. Refined & active unmerged worktree: task-0016
    wt_0016 = repo / ".worktrees" / "task-0016"
    create_worktree(repo, branch="feat/TASK-0016", worktree_dir=wt_0016)
    (wt_0016 / "in_progress.py").write_text("x = 42\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=wt_0016, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "wip: unmerged task 0016"], cwd=wt_0016, check=True, capture_output=True)
    refined_dir = cfg.backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    t16 = Task(id="0016", title="Active Task 0016", status="Refined", file_path=refined_dir / "0016-active.md")
    write_task_file(t16)

    # 3. Orphan unmerged worktree: task-9999
    wt_orphan = repo / ".worktrees" / "task-9999"
    create_worktree(repo, branch="feat/orphan-9999", worktree_dir=wt_orphan)
    (wt_orphan / "orphan.py").write_text("# orphan unmerged\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=wt_orphan, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: orphan unmerged"], cwd=wt_orphan, check=True, capture_output=True)

    quota_context["wt_0005"] = wt_0005
    quota_context["wt_0016"] = wt_0016
    quota_context["wt_orphan"] = wt_orphan


@when(parsers.parse('the engineer runs "{cmd}"'))
@when(parsers.parse('the engineer executes "{cmd}"'))
def run_cli_command(quota_context: dict[str, Any], cmd: str, capsys: pytest.CaptureFixture):
    cfg = quota_context["config"]
    parser = build_parser()
    parts = cmd.split()[1:]
    args = parser.parse_args(parts)
    code = handle_rescue_command(args, cfg)
    captured = capsys.readouterr()
    quota_context["exit_code"] = code
    quota_context["stdout"] = captured.out
    quota_context["stderr"] = captured.err


@then("a tabular summary displays directory sizes and associated task statuses")
def verify_tabular_summary(quota_context: dict[str, Any]):
    stdout = quota_context["stdout"]
    assert "Worktree Disk Quota & Storage Consumption" in stdout
    assert "task-0005" in stdout
    assert "Complete" in stdout
    assert "task-0016" in stdout
    assert "Refined" in stdout
    assert "task-9999" in stdout
    assert "Orphan" in stdout
    assert "Total Worktree Storage:" in stdout


@then("flags candidates eligible for safe pruning")
def verify_flags_candidates(quota_context: dict[str, Any]):
    stdout = quota_context["stdout"]
    assert "Yes (Candidate)" in stdout
    assert "Candidates eligible for safe pruning:" in stdout


@given('an abandoned worktree whose task was completed and merged into "main"')
def setup_abandoned_merged_worktree(quota_context: dict[str, Any]):
    repo = quota_context["repo"]
    cfg = quota_context["config"]

    # 1. Completed & merged worktree: task-0005 (aged 2 days)
    wt_0005 = repo / ".worktrees" / "task-0005"
    create_worktree(repo, branch="feat/TASK-0005", worktree_dir=wt_0005)
    (wt_0005 / "done.py").write_text("done = True\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=wt_0005, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: 0005 done"], cwd=wt_0005, check=True, capture_output=True)
    subprocess.run(["git", "merge", "feat/TASK-0005", "--no-ff", "-m", "merge feat/TASK-0005"], cwd=repo, check=True, capture_output=True)

    complete_dir = cfg.backlog_dir / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    t5 = Task(id="0005", title="Completed Task 0005", status="Complete", file_path=complete_dir / "0005-completed.md")
    write_task_file(t5)
    _age_directory(wt_0005, 2 * 86400)

    # 2. Active unmerged worktree: task-0016 (active, unmerged)
    wt_0016 = repo / ".worktrees" / "task-0016"
    create_worktree(repo, branch="feat/TASK-0016", worktree_dir=wt_0016)
    (wt_0016 / "active.py").write_text("active = True\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=wt_0016, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: 0016 active"], cwd=wt_0016, check=True, capture_output=True)

    refined_dir = cfg.backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    t16 = Task(id="0016", title="Active Task 0016", status="Refined", file_path=refined_dir / "0016-active.md")
    write_task_file(t16)
    _age_directory(wt_0016, 2 * 86400)

    quota_context["abandoned_wt"] = wt_0005
    quota_context["abandoned_branch"] = "feat/TASK-0005"
    quota_context["active_wt"] = wt_0016
    quota_context["active_branch"] = "feat/TASK-0016"


@then("the worktree directory and branch are deleted safely")
def verify_worktree_deleted_safely(quota_context: dict[str, Any]):
    abandoned_wt = quota_context["abandoned_wt"]
    abandoned_branch = quota_context["abandoned_branch"]
    repo = quota_context["repo"]

    assert not abandoned_wt.exists(), f"Worktree directory {abandoned_wt} should be deleted"
    chk = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{abandoned_branch}"], cwd=repo)
    assert chk.returncode != 0, f"Branch {abandoned_branch} should be deleted"


@then("zero active unmerged worktrees are affected")
def verify_active_worktrees_unaffected(quota_context: dict[str, Any]):
    active_wt = quota_context["active_wt"]
    active_branch = quota_context["active_branch"]
    repo = quota_context["repo"]

    assert active_wt.exists(), f"Active worktree directory {active_wt} must NOT be deleted"
    chk = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{active_branch}"], cwd=repo)
    assert chk.returncode == 0, f"Active branch {active_branch} must NOT be deleted"
