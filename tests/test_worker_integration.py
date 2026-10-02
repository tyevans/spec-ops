"""Unit tests for worker integration and inference-driven rebase healing."""

import subprocess
from pathlib import Path

import pytest

from spec_ops.worker import BacklogWorkerEngine, request_global_shutdown
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
    from spec_ops.worker import engine as worker
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


def test_determine_rebase_command_fork_point(repo_with_git: Path, tmp_path: Path):
    from spec_ops.worker.integration import determine_rebase_command
    from spec_ops.worker.worktree import create_worktree

    # Create task 1
    subprocess.run(["git", "checkout", "-b", "feat/base-branch"], cwd=repo_with_git, check=True, capture_output=True)
    (repo_with_git / "f1.txt").write_text("file 1\n")
    subprocess.run(["git", "add", "f1.txt"], cwd=repo_with_git, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(task-0001): task 1"], cwd=repo_with_git, check=True, capture_output=True)

    # Branch task 2 from task 1
    wt_dir = tmp_path / "wt_task2"
    create_worktree(repo_with_git, "feat/task-2", wt_dir, base_ref="feat/base-branch")
    (wt_dir / "f2.txt").write_text("file 2\n")
    subprocess.run(["git", "add", "f2.txt"], cwd=wt_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(task-0002): task 2"], cwd=wt_dir, check=True, capture_output=True)

    # Squash-merge task 1 into main
    subprocess.run(["git", "checkout", "main"], cwd=repo_with_git, check=True, capture_output=True)
    subprocess.run(["git", "merge", "--squash", "feat/base-branch"], cwd=repo_with_git, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(task-0001): squashed task 1"], cwd=repo_with_git, check=True, capture_output=True)

    task2 = Task(id="0002", title="Task 2")
    cmd = determine_rebase_command(wt_dir, task2, main_branch="main")
    # Fork point or task boundary should select --onto main instead of plain rebase main
    assert "--onto" in cmd
    assert cmd[1] == "rebase"
    assert cmd[3] == "main"


def test_create_worktree_defaults_to_main(repo_with_git: Path, tmp_path: Path):
    from spec_ops.worker.worktree import create_worktree

    # Switch root repo to a feature branch with extra commit
    subprocess.run(["git", "checkout", "-b", "feat/some-side-branch"], cwd=repo_with_git, check=True, capture_output=True)
    (repo_with_git / "side.txt").write_text("side\n")
    subprocess.run(["git", "add", "side.txt"], cwd=repo_with_git, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "side commit"], cwd=repo_with_git, check=True, capture_output=True)

    wt_dir = tmp_path / "wt_isolated"
    create_worktree(repo_with_git, "feat/isolated", wt_dir)

    # Worktree should be branched from main, not containing side.txt
    assert not (wt_dir / "side.txt").exists()


def test_rebase_with_inference_healing_squashed_upstream(repo_with_git: Path, tmp_path: Path):
    from spec_ops.worker.worktree import create_worktree

    # Create task 1
    subprocess.run(["git", "checkout", "-b", "feat/task-1-branch"], cwd=repo_with_git, check=True, capture_output=True)
    (repo_with_git / "feature1.txt").write_text("feature 1\n")
    subprocess.run(["git", "add", "feature1.txt"], cwd=repo_with_git, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(task-0001): task 1 implementation"], cwd=repo_with_git, check=True, capture_output=True)

    # Branch task 2 off task 1
    wt_dir = tmp_path / "wt_task2_rebase"
    create_worktree(repo_with_git, "feat/task-2-branch", wt_dir, base_ref="feat/task-1-branch")
    (wt_dir / "feature2.txt").write_text("feature 2\n")
    subprocess.run(["git", "add", "feature2.txt"], cwd=wt_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(task-0002): task 2 implementation"], cwd=wt_dir, check=True, capture_output=True)

    # Squash-merge task 1 into main
    subprocess.run(["git", "checkout", "main"], cwd=repo_with_git, check=True, capture_output=True)
    subprocess.run(["git", "merge", "--squash", "feat/task-1-branch"], cwd=repo_with_git, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: squashed PR with task 1 (#1)"], cwd=repo_with_git, check=True, capture_output=True)

    config = load_config(repo_with_git)
    task2 = Task(id="0002", title="Task 2")
    ok, msg = rebase_with_inference_healing(wt_dir, task2, config)
    assert ok is True
    assert "Rebased successfully" in msg
    assert (wt_dir / "feature1.txt").exists()
    assert (wt_dir / "feature2.txt").exists()


