"""Unit tests for worker integration and inference-driven rebase healing."""

import subprocess
from pathlib import Path

import pytest

from spec_ops.backlog.worker import BacklogWorkerEngine, request_global_shutdown
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.worker.integration import rebase_with_inference_healing, squash_merge_and_commit


@pytest.fixture
def repo_with_git(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="IntegrationApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@runner.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)
    return repo


def test_squash_merge_and_commit_clean(repo_with_git: Path):
    # Create a feature branch
    branch = "feat/clean-branch"
    subprocess.run(["git", "checkout", "-b", branch], cwd=repo_with_git, check=True, capture_output=True)
    (repo_with_git / "new_feature.txt").write_text("Feature content\n")
    subprocess.run(["git", "add", "new_feature.txt"], cwd=repo_with_git, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add feature"], cwd=repo_with_git, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo_with_git, check=True, capture_output=True)

    called = False

    def on_staged():
        nonlocal called
        called = True

    ok, msg = squash_merge_and_commit(
        repo_with_git,
        branch,
        "feat(task-0001): integrated feature",
        on_staged=on_staged,
    )
    assert ok is True
    assert "Merged and committed cleanly" in msg
    assert called is True
    assert (repo_with_git / "new_feature.txt").exists()


def test_squash_merge_fails_on_unmerged_index(repo_with_git: Path):
    # Simulate an unresolved conflict index
    branch = "feat/test-branch"
    subprocess.run(["git", "branch", branch], cwd=repo_with_git, check=True, capture_output=True)

    # Fake a porcelain conflict line in a status mock or git state
    # Create conflict manually
    file_p = repo_with_git / "conflict.txt"
    file_p.write_text("base\n")
    subprocess.run(["git", "add", "conflict.txt"], cwd=repo_with_git, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add conflict file"], cwd=repo_with_git, check=True, capture_output=True)

    subprocess.run(["git", "checkout", "-b", "other"], cwd=repo_with_git, check=True, capture_output=True)
    file_p.write_text("other change\n")
    subprocess.run(["git", "commit", "-am", "change in other"], cwd=repo_with_git, check=True, capture_output=True)

    subprocess.run(["git", "checkout", "main"], cwd=repo_with_git, check=True, capture_output=True)
    file_p.write_text("main change\n")
    subprocess.run(["git", "commit", "-am", "change in main"], cwd=repo_with_git, check=True, capture_output=True)

    # Cause merge conflict
    subprocess.run(["git", "merge", "other"], cwd=repo_with_git, capture_output=True)

    ok, msg = squash_merge_and_commit(repo_with_git, branch, "feat: attempt merge")
    assert ok is False
    assert "unresolved merge conflicts" in msg


def test_rebase_with_inference_healing_success(repo_with_git: Path, tmp_path: Path):
    # Set up a branch with a conflict
    conflicted_file = repo_with_git / "shared.txt"
    conflicted_file.write_text("line 1\nline 2\n")
    subprocess.run(["git", "add", "shared.txt"], cwd=repo_with_git, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add shared.txt"], cwd=repo_with_git, check=True, capture_output=True)

    # Branch feat
    subprocess.run(["git", "checkout", "-b", "feat/my-feature"], cwd=repo_with_git, check=True, capture_output=True)
    conflicted_file.write_text("line 1\nfeature change\n")
    subprocess.run(["git", "commit", "-am", "feature commit"], cwd=repo_with_git, check=True, capture_output=True)

    # Advance main
    subprocess.run(["git", "checkout", "main"], cwd=repo_with_git, check=True, capture_output=True)
    conflicted_file.write_text("line 1\nmain change\n")
    subprocess.run(["git", "commit", "-am", "main commit"], cwd=repo_with_git, check=True, capture_output=True)

    # Set up worktree
    worktree_dir = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", str(worktree_dir), "feat/my-feature"], cwd=repo_with_git, check=True, capture_output=True)

    # Configure a mock agent script that resolves the conflict
    resolver_script = tmp_path / "resolve.py"
    resolver_script.write_text(
        "from pathlib import Path\n"
        "p = Path('shared.txt')\n"
        "p.write_text('line 1\\nmain change\\nfeature change\\n')\n",
        encoding="utf-8",
    )

    config = load_config(repo_with_git)
    config.execution.agent_command = f"python3 {resolver_script}"
    config.execution.enable_conflict_healing = True

    task = Task(id="0099", title="Test Healing", file_path=repo_with_git / "task.md")

    ok, msg = rebase_with_inference_healing(worktree_dir, task, config)
    assert ok is True
    assert "healed" in msg
    assert (worktree_dir / "shared.txt").read_text() == "line 1\nmain change\nfeature change\n"


def test_agent_halt_on_shutdown_signal(repo_with_git: Path, tmp_path: Path):
    from spec_ops.backlog import worker
    config = load_config(repo_with_git)
    config.execution.agent_command = "echo 'noop'"
    config.execution.agent_max_attempts = 3
    engine = BacklogWorkerEngine(config)

    task = Task(id="0098", title="Signal Test", file_path=repo_with_git / "task.md")
    worktree_dir = tmp_path / "wt_sig"
    worktree_dir.mkdir(parents=True, exist_ok=True)

    request_global_shutdown()
    try:
        ok, msg = engine.invoke_agent(task, worktree_dir)
        assert ok is False
        assert "Interrupted by shutdown signal" in msg
    finally:
        worker._GLOBAL_SHUTDOWN = False
