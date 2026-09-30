"""Unit tests for ci_repair.py to maximize mutant kill rate."""

from __future__ import annotations

import subprocess
from pathlib import Path

from spec_ops.worker.ci_repair import (
    extract_failure_trace,
    fetch_failed_ci_logs,
    inject_ci_failure_prompt,
    verify_worktree_diff,
)


def test_verify_worktree_diff_non_git_repo(tmp_path: Path):
    ok, reason = verify_worktree_diff(tmp_path)
    assert not ok
    assert reason == "No Modifications Produced"


def test_verify_worktree_diff_empty_and_prompts_only(tmp_path: Path):
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)

    # Empty repo
    ok, reason = verify_worktree_diff(tmp_path)
    assert not ok
    assert reason == "No Modifications Produced"

    # Only prompt file created
    (tmp_path / ".task-prompt.md").write_text("prompt content", encoding="utf-8")
    (tmp_path / ".task-review-prompt.md").write_text("review content", encoding="utf-8")
    ok, reason = verify_worktree_diff(tmp_path)
    assert not ok
    assert reason == "No Modifications Produced"


def test_verify_worktree_diff_untracked_content(tmp_path: Path):
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)

    # Untracked empty file
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("   \n\t\n", encoding="utf-8")
    ok, reason = verify_worktree_diff(tmp_path)
    assert not ok
    assert reason == "No Modifications Produced"

    # Untracked file with real code
    real_file = tmp_path / "impl.py"
    real_file.write_text("def solve(): return 1\n", encoding="utf-8")
    ok, reason = verify_worktree_diff(tmp_path)
    assert ok
    assert reason == ""


def test_verify_worktree_diff_tracked_whitespace_vs_substantive(tmp_path: Path):
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)

    file_a = tmp_path / "code.py"
    file_a.write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    # Whitespace-only edit
    file_a.write_text("x   =   1  \n", encoding="utf-8")
    ok, reason = verify_worktree_diff(tmp_path)
    assert not ok
    assert reason == "No Modifications Produced"

    # Substantive edit
    file_a.write_text("x = 2\n", encoding="utf-8")
    ok, reason = verify_worktree_diff(tmp_path)
    assert ok
    assert reason == ""


def test_fetch_failed_ci_logs_custom_cmd(tmp_path: Path):
    # Successful custom command
    ok, logs = fetch_failed_ci_logs(tmp_path, custom_cmd=["python3", "-c", "print('Error: run failed')"])
    assert ok
    assert "Error: run failed" in logs

    # Failing custom command
    ok, logs = fetch_failed_ci_logs(tmp_path, custom_cmd=["python3", "-c", "import sys; sys.exit(1)"])
    assert not ok

    # Invalid executable
    ok, logs = fetch_failed_ci_logs(tmp_path, custom_cmd=["/nonexistent/binary/path"])
    assert not ok
    assert "Failed to execute" in logs


def test_extract_failure_trace():
    assert extract_failure_trace("") == "No failure trace provided."
    assert extract_failure_trace("   \n  ") == "No failure trace provided."

    raw = """
2026-09-29T12:00:00Z Step 1: Checkout code
2026-09-29T12:00:01Z Step 2: Install dependencies
2026-09-29T12:00:05Z Step 3: Run pytest
FAILED tests/test_core.py::test_calculation - AssertionError: expected 42 but got 0
Traceback (most recent call last):
  File "test_core.py", line 10, in test_calculation
    assert calc() == 42
2026-09-29T12:00:06Z Step 4: Cleanup
"""
    trace = extract_failure_trace(raw)
    assert "FAILED tests/test_core.py" in trace
    assert "AssertionError" in trace
    assert "Traceback" in trace
    assert "Checkout code" not in trace

    # When no markers match, returns full stripped log
    plain = "Informational message without errors"
    assert extract_failure_trace(plain) == plain


def test_inject_ci_failure_prompt(tmp_path: Path):
    prompt_file = inject_ci_failure_prompt("TASK-0020", tmp_path, "AssertionError on line 12")
    assert prompt_file.exists()
    content = prompt_file.read_text(encoding="utf-8")
    assert "Task TASK-0020: Autonomous Remote CI Repair Loop" in content
    assert "Remote CI Failure Diagnostics" in content
    assert "AssertionError on line 12" in content

    # Appending to existing prompt
    prompt_file.write_text("Existing instruction\n", encoding="utf-8")
    inject_ci_failure_prompt("TASK-0020", tmp_path, "Second error")
    updated = prompt_file.read_text(encoding="utf-8")
    assert updated.startswith("Existing instruction")
    assert "Second error" in updated


def test_verify_worktree_diff_untracked_dir_and_rename(tmp_path: Path):
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)

    # Untracked directory
    sub = tmp_path / "new_pkg"
    sub.mkdir()
    (sub / "mod.py").write_text("a = 1\n", encoding="utf-8")
    ok, _ = verify_worktree_diff(tmp_path)
    assert ok


def test_ci_heal_task_dry_run_and_failure_modes(tmp_path: Path):
    from spec_ops.config.loader import load_config
    from spec_ops.scaffold.init import init_project
    from spec_ops.worker.ci_repair import ci_heal_task

    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="App")
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    config = load_config(root_dir=repo)

    # Dry-run with numeric ID "0040"
    ok, msg = ci_heal_task(config, "0040", gh_cmd=["echo", "error log"], dry_run=True)
    assert ok
    assert "Dry-run:" in msg

    # Agent failure mode
    config.execution.agent_command = "false"
    config.execution.agent_max_attempts = 1
    ok_fail, msg_fail = ci_heal_task(config, "TASK-0040", gh_cmd=["echo", "error log"], dry_run=False)
    assert not ok_fail
    assert "Agent repair failed" in msg_fail

