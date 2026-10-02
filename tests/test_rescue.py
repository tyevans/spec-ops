"""Tests for worktree rescue and human takeover."""

import subprocess
from pathlib import Path

from spec_ops.config.models import SpecOpsConfig
from spec_ops.rescue.manager import WorktreeRescueManager


def test_rescue_manager_list_and_inspect(tmp_path: Path):
    cfg = SpecOpsConfig(root_dir=tmp_path)
    mgr = WorktreeRescueManager(cfg)

    # Empty case
    assert mgr.list_active_worktrees() == []

    # Create dummy worktree directory
    wt_dir = tmp_path / ".worktrees" / "task-0011"
    wt_dir.mkdir(parents=True)
    prompt_file = wt_dir / ".task-prompt.md"
    prompt_file.write_text(
        "# Prompt\n\n## Preflight Failure Feedback\npytest failed with 1 error\n",
        encoding="utf-8",
    )

    wts = mgr.list_active_worktrees()
    assert len(wts) == 1
    assert wts[0].task_id == "TASK-0011"
    assert "pytest failed with 1 error" in wts[0].failure_feedback

    info = mgr.inspect_task("TASK-0011")
    assert info is not None
    assert info.task_id == "TASK-0011"
    assert info.worktree_dir == wt_dir
    assert "pytest failed with 1 error" in info.failure_feedback


def test_rescue_manager_discard(tmp_path: Path):
    cfg = SpecOpsConfig(root_dir=tmp_path)
    mgr = WorktreeRescueManager(cfg)

    wt_dir = tmp_path / ".worktrees" / "task-0018"
    wt_dir.mkdir(parents=True)

    info = mgr.inspect_task("0018")
    assert info is not None
    assert info.exists

    ok, msg = mgr.discard_worktree("0018")
    assert ok
    assert not wt_dir.exists()


def test_build_agent_cmd():
    from spec_ops.backlog.worker import build_agent_cmd

    cmd1 = build_agent_cmd("agy --dangerously-skip-permissions -p {prompt}", "My multi-line 'prompt' with \"quotes\"", Path("prompt.md"))
    assert cmd1 == ["agy", "--dangerously-skip-permissions", "-p", "My multi-line 'prompt' with \"quotes\""]

    cmd2 = build_agent_cmd("claude --file {prompt_file}", "prompt", Path("task.md"))
    assert cmd2 == ["claude", "--file", "task.md"]

    cmd3 = build_agent_cmd("aider --message", "prompt", Path("task.md"))
    assert cmd3 == ["aider", "--message", "task.md"]

    cmd_continue = build_agent_cmd("agy -p {prompt}", "feedback prompt", Path("prompt.md"), continue_session=True)
    assert cmd_continue == ["agy", "--dangerously-skip-permissions", "-c", "-p", "feedback prompt"]


def test_rescue_manager_prune_all(tmp_path: Path):
    cfg = SpecOpsConfig(root_dir=tmp_path)
    mgr = WorktreeRescueManager(cfg)

    wt1 = tmp_path / ".worktrees" / "task-0001"
    wt2 = tmp_path / ".worktrees" / "task-0002"
    wt1.mkdir(parents=True)
    wt2.mkdir(parents=True)

    assert len(mgr.list_active_worktrees()) == 2
    count = mgr.prune_all_worktrees()
    assert count == 2
    assert len(mgr.list_active_worktrees()) == 0


def test_rescue_manager_syncs_security_profile_before_preflight(tmp_path: Path):
    from spec_ops.profiles.security import apply_security_profile

    # Initialize root with security profile
    apply_security_profile(tmp_path)
    (tmp_path / "specops.toml").write_text("[security]\nsecret_scanning = true\n", encoding="utf-8")

    # Add a task in refined
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    task_file = backlog_dir / "0099-test-task.md"
    task_file.write_text(
        "---\nid: '0099'\ntitle: Test Task\nstatus: Refined\n---\n# Task",
        encoding="utf-8",
    )

    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    # Create worktree missing SECURITY.md
    wt_dir = tmp_path / ".worktrees" / "task-0099"
    subprocess.run(["git", "worktree", "add", "-b", "feat/task-0099", str(wt_dir), "HEAD"], cwd=tmp_path, capture_output=True)
    sec_in_wt = wt_dir / "docs" / "project" / "SECURITY.md"
    if sec_in_wt.exists():
        sec_in_wt.unlink()
    assert not sec_in_wt.exists()

    cfg = SpecOpsConfig(root_dir=tmp_path)
    mgr = WorktreeRescueManager(cfg)

    mgr.complete_rescue("0099")
    assert sec_in_wt.is_file()


