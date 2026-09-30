"""Unit tests for native git hook scaffolding and worktree propagation."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from spec_ops.scaffold.native_hooks import (
    generate_pre_commit_hook,
    generate_pre_push_hook,
    install_native_hooks,
    propagate_all_worktrees,
    propagate_hooks_to_worktree,
    resolve_hooks_dir,
    scaffold_hooks_command,
)


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "test_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.test"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("Test", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def test_generate_pre_commit_hook():
    content = generate_pre_commit_hook()
    assert content.startswith("#!/bin/sh\n")
    assert "Invariant Violation (ADR-0005)" in content
    assert "uv lock --check" in content
    assert "audit-anti-mock" in content
    assert "spec-ops health" in content


def test_generate_pre_push_hook():
    content = generate_pre_push_hook()
    assert content.startswith("#!/bin/sh\n")
    assert "uv lock --check" in content
    assert "spec-ops health" in content


def test_resolve_hooks_dir_standard(temp_git_repo: Path):
    hooks_dir = resolve_hooks_dir(temp_git_repo)
    assert hooks_dir == temp_git_repo / ".git" / "hooks"


def test_resolve_hooks_dir_worktree(temp_git_repo: Path):
    wt_dir = temp_git_repo / ".worktrees" / "task-wt"
    subprocess.run(["git", "worktree", "add", "-b", "feat/wt", str(wt_dir)], cwd=temp_git_repo, check=True, capture_output=True)

    hooks_dir = resolve_hooks_dir(wt_dir)
    assert hooks_dir.exists()
    assert hooks_dir == temp_git_repo / ".git" / "hooks"


def test_resolve_hooks_dir_fake_worktree_fallback(tmp_path: Path):
    # .git is a file but git rev-parse fails
    fake_wt = tmp_path / "fake"
    fake_wt.mkdir()
    (fake_wt / ".git").write_text("gitdir: /nonexistent/path\n", encoding="utf-8")
    hooks_dir = resolve_hooks_dir(fake_wt)
    assert hooks_dir == fake_wt / ".git" / "hooks"


def test_install_native_hooks_fresh(temp_git_repo: Path):
    pre_commit, pre_push = install_native_hooks(temp_git_repo)
    assert pre_commit.is_file()
    assert pre_push.is_file()
    assert os.access(pre_commit, os.X_OK)
    assert os.access(pre_push, os.X_OK)
    assert (temp_git_repo / ".git" / "hooks" / "pre-commit") == pre_commit
    assert (temp_git_repo / ".git" / "hooks" / "pre-push") == pre_push


def test_install_native_hooks_exists_without_force(temp_git_repo: Path):
    install_native_hooks(temp_git_repo)
    with pytest.raises(FileExistsError) as exc_info:
        install_native_hooks(temp_git_repo, force=False)
    assert "Use --force to overwrite" in str(exc_info.value)


def test_install_native_hooks_overwrite_with_force(temp_git_repo: Path):
    install_native_hooks(temp_git_repo)
    hook_file = temp_git_repo / ".git" / "hooks" / "pre-commit"
    hook_file.write_text("stale", encoding="utf-8")

    pre_commit, _ = install_native_hooks(temp_git_repo, force=True)
    assert hook_file.read_text(encoding="utf-8") != "stale"
    assert hook_file.read_text(encoding="utf-8").startswith("#!/bin/sh\n")


def test_propagate_hooks_to_non_worktree(temp_git_repo: Path):
    res = propagate_hooks_to_worktree(temp_git_repo, temp_git_repo)
    assert res is None


def test_propagate_hooks_to_invalid_git_file(tmp_path: Path):
    fake_wt = tmp_path / "fake_wt"
    fake_wt.mkdir()
    (fake_wt / ".git").write_text("invalid git content", encoding="utf-8")
    res = propagate_hooks_to_worktree(tmp_path, fake_wt)
    assert res is None


def test_propagate_hooks_to_relative_gitdir(tmp_path: Path):
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    (fake_repo / ".git").mkdir()
    (fake_repo / ".git" / "hooks").mkdir()
    (fake_repo / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")

    fake_wt = fake_repo / "wt"
    fake_wt.mkdir()
    wt_gitdir = fake_repo / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)

    rel_path = os.path.relpath(wt_gitdir, fake_wt)
    (fake_wt / ".git").write_text(f"gitdir: {rel_path}\n", encoding="utf-8")

    res = propagate_hooks_to_worktree(fake_repo, fake_wt)
    assert res is not None
    assert res.is_symlink() or res.exists()


def test_propagate_hooks_parent_no_hooks_yet(tmp_path: Path):
    fake_repo = tmp_path / "fake_repo2"
    fake_repo.mkdir()
    (fake_repo / ".git").mkdir()

    fake_wt = fake_repo / "wt"
    fake_wt.mkdir()
    wt_gitdir = fake_repo / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)

    (fake_wt / ".git").write_text(f"gitdir: {wt_gitdir}\n", encoding="utf-8")

    res = propagate_hooks_to_worktree(fake_repo, fake_wt)
    assert res is not None
    assert (fake_repo / ".git" / "hooks").is_dir()


def test_propagate_hooks_symlink_failure_fallback(tmp_path: Path, monkeypatch):
    fake_repo = tmp_path / "fake_repo3"
    fake_repo.mkdir()
    hooks_dir = fake_repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "pre-commit").write_text("#!/bin/sh\n# hook\n", encoding="utf-8")

    fake_wt = fake_repo / "wt"
    fake_wt.mkdir()
    wt_gitdir = fake_repo / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (fake_wt / ".git").write_text(f"gitdir: {wt_gitdir}\n", encoding="utf-8")

    # Monkeypatch symlink_to on Path to raise OSError simulating Windows/permission restriction
    orig_symlink_to = Path.symlink_to

    def broken_symlink_to(self, target):
        raise OSError("Symlink disallowed on this system")

    monkeypatch.setattr(Path, "symlink_to", broken_symlink_to)

    res = propagate_hooks_to_worktree(fake_repo, fake_wt)
    assert res is not None
    assert res.is_dir()
    assert (res / "pre-commit").is_file()
    assert (res / "pre-commit").read_text(encoding="utf-8") == "#!/bin/sh\n# hook\n"


def test_propagate_hooks_to_active_worktree(temp_git_repo: Path):
    install_native_hooks(temp_git_repo)
    wt_dir = temp_git_repo / ".worktrees" / "task-prop"
    subprocess.run(["git", "worktree", "add", "-b", "feat/prop", str(wt_dir)], cwd=temp_git_repo, check=True, capture_output=True)

    wt_hooks = propagate_hooks_to_worktree(temp_git_repo, wt_dir)
    assert wt_hooks is not None
    assert wt_hooks.exists()
    assert (wt_hooks / "pre-commit").exists()

    # Calling again should be idempotent
    second_res = propagate_hooks_to_worktree(temp_git_repo, wt_dir)
    assert second_res == wt_hooks


def test_propagate_all_worktrees_no_worktrees_dir(temp_git_repo: Path):
    if (temp_git_repo / ".git" / "worktrees").exists():
        shutil.rmtree(temp_git_repo / ".git" / "worktrees")
    propagated = propagate_all_worktrees(temp_git_repo)
    assert propagated == []


def test_propagate_all_worktrees(temp_git_repo: Path):
    install_native_hooks(temp_git_repo)
    wt1 = temp_git_repo / ".worktrees" / "wt1"
    wt2 = temp_git_repo / ".worktrees" / "wt2"
    subprocess.run(["git", "worktree", "add", "-b", "feat/wt1", str(wt1)], cwd=temp_git_repo, check=True, capture_output=True)
    subprocess.run(["git", "worktree", "add", "-b", "feat/wt2", str(wt2)], cwd=temp_git_repo, check=True, capture_output=True)

    propagated = propagate_all_worktrees(temp_git_repo)
    assert len(propagated) >= 1
    for p in propagated:
        assert p.exists()


def test_scaffold_hooks_command_success(temp_git_repo: Path):
    code, msg = scaffold_hooks_command(temp_git_repo)
    assert code == 0
    assert "Installed native git hooks" in msg
    assert (temp_git_repo / ".git" / "hooks" / "pre-commit").is_file()


def test_scaffold_hooks_command_file_exists(temp_git_repo: Path):
    scaffold_hooks_command(temp_git_repo)
    code, msg = scaffold_hooks_command(temp_git_repo, force=False)
    assert code == 1
    assert "Use --force to overwrite" in msg

    # With force=True
    code2, msg2 = scaffold_hooks_command(temp_git_repo, force=True)
    assert code2 == 0
    assert "Installed native git hooks" in msg2


def test_scaffold_hooks_command_error(tmp_path: Path):
    blocking_file = tmp_path / "blocked"
    blocking_file.write_text("block", encoding="utf-8")
    code, msg = scaffold_hooks_command(blocking_file)
    assert code == 1
    assert "Failed to scaffold git hooks" in msg or "already exist" in msg
