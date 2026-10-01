"""Hypothesis property invariant verification for autonomous worktree auto-rebase (ADR-0005, ADR-0009)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.worker.auto_rebase import auto_rebase_worktree
from spec_ops.worker.integration import is_rebase_in_progress


def _setup_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Hypothesis"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "hypothesis@specops.test"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_path, capture_output=True)

    # Initial commit
    init_f = repo_path / "src" / "root.py"
    init_f.parent.mkdir(parents=True, exist_ok=True)
    init_f.write_text("INITIAL = 0\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo_path, check=True, capture_output=True)


@settings(max_examples=30, deadline=None)
@given(
    main_commits=st.integers(min_value=1, max_value=3),
    feat_commits=st.integers(min_value=1, max_value=3),
    has_conflict=st.booleans(),
    dry_run=st.booleans(),
)
def test_auto_rebase_invariants(
    main_commits: int,
    feat_commits: int,
    has_conflict: bool,
    dry_run: bool,
) -> None:
    """Asserts that for any git state, auto-rebase results in clean rebase or safe pre-rebase restore."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = Path(tmp_dir)
        _setup_git_repo(repo_path)

        # Create branch feat/TASK-0147
        subprocess.run(["git", "checkout", "-b", "feat/TASK-0147"], cwd=repo_path, check=True, capture_output=True)

        # Apply feature commits
        for i in range(feat_commits):
            feat_file = repo_path / "src" / f"feat_{i}.py"
            feat_file.write_text(f"FEAT_{i} = {i}\n", encoding="utf-8")
            if has_conflict:
                shared = repo_path / "src" / "shared.py"
                shared.write_text(f"SHARED_VALUE = 'branch_val_{i}'\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"feat: commit {i}"], cwd=repo_path, check=True, capture_output=True)

        pre_rebase_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True).stdout.strip()

        # Switch to main and apply main commits
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, check=True, capture_output=True)
        for j in range(main_commits):
            main_file = repo_path / "src" / f"main_{j}.py"
            main_file.write_text(f"MAIN_{j} = {j}\n", encoding="utf-8")
            if has_conflict:
                shared = repo_path / "src" / "shared.py"
                shared.write_text(f"SHARED_VALUE = 'main_val_{j}'\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"chore: main commit {j}"], cwd=repo_path, check=True, capture_output=True)

        main_head_sha = subprocess.run(["git", "rev-parse", "main"], cwd=repo_path, capture_output=True, text=True).stdout.strip()

        # Switch back to feat/TASK-0147
        subprocess.run(["git", "checkout", "feat/TASK-0147"], cwd=repo_path, check=True, capture_output=True)

        # Execute auto-rebase
        result = auto_rebase_worktree(
            worktree_dir=repo_path,
            task_id="TASK-0147",
            target_branch="main",
            abort_on_conflict=True,
            dry_run=dry_run,
        )

        # --- Hard Invariants (ADR-0002, ADR-0005, ADR-0009) ---

        # Invariant 1: Rebase is NEVER left active or in-progress
        assert not is_rebase_in_progress(repo_path), "Git rebase state must never remain active after operation"

        # Invariant 2: HEAD is NEVER detached
        sym_res = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=repo_path, capture_output=True, text=True)
        assert sym_res.returncode == 0, f"HEAD must never be detached, got: {sym_res.stderr}"

        # Invariant 3: No stale lock files remain in .git
        git_dir_res = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=repo_path, capture_output=True, text=True)
        git_dir = Path(git_dir_res.stdout.strip())
        if not git_dir.is_absolute():
            git_dir = (repo_path / git_dir).resolve()
        assert not (git_dir / "index.lock").exists(), "index.lock must not linger"
        assert not (git_dir / "HEAD.lock").exists(), "HEAD.lock must not linger"
        assert not (git_dir / "rebase-merge").exists(), "rebase-merge dir must not linger"

        # Invariant 4: Backlog directory is NEVER modified (ADR-0005)
        backlog_status = subprocess.run(
            ["git", "status", "--porcelain", "--", "docs/project/backlog"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        assert not backlog_status.stdout.strip(), "docs/project/backlog must never be modified by auto-rebase"

        # Invariant 5: Dry-run never alters HEAD
        if dry_run:
            current_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True).stdout.strip()
            assert current_head == pre_rebase_sha, "Dry run must preserve exact pre-rebase HEAD"

        # Invariant 6: Successful clean rebase includes main head in history
        elif result.success and not has_conflict:
            mb_res = subprocess.run(["git", "merge-base", "HEAD", "main"], cwd=repo_path, capture_output=True, text=True)
            assert mb_res.stdout.strip() == main_head_sha, "Rebased branch must have main tip as ancestor"

        # Invariant 7: Conflicting rebase safely aborted with pre-rebase restore & HANDOVER.md
        elif not result.success and has_conflict:
            assert result.status == "conflict_aborted"
            current_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True).stdout.strip()
            assert current_head == pre_rebase_sha, "Conflicting rebase abort must restore pre-rebase HEAD"
            handover_file = repo_path / "HANDOVER.md"
            assert handover_file.exists(), "HANDOVER.md must be generated on conflict abort"
            content = handover_file.read_text(encoding="utf-8")
            assert "Conflict Diagnostic Summary" in content
            assert "TASK-0147" in content
