"""Tests for worktree rescue and human takeover."""

import subprocess
from pathlib import Path

from spec_ops.backlog.rescue import WorktreeRescueManager
from spec_ops.config.models import SpecOpsConfig


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
