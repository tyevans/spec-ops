"""Zero-dependency native POSIX shell git hook generator and worktree propagator."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

PRE_COMMIT_SCRIPT = """#!/bin/sh
# SpecOps native pre-commit hook (ADR-0002, ADR-0003, ADR-0005, ADR-0011)
set -e

# 1. Backlog Isolation Gate (ADR-0005)
case "$BRANCH" in
    main|master|chore/backlog*|sync/*)
        ;;
    *)
        STAGED_BACKLOG=$(git diff --cached --name-only 2>/dev/null | grep '^docs/project/backlog/' || true)
        if [ -n "$STAGED_BACKLOG" ]; then
            echo "Invariant Violation (ADR-0005): Feature branches are strictly forbidden from modifying docs/project/backlog/. Backlog transitions are managed automatically upon merge to main." >&2
            exit 1
        fi
        ;;
esac

# 2. Supply-Chain Lockfile Verification (ADR-0011)
if git diff --cached --name-only 2>/dev/null | grep -q -E '^(uv\\.lock|pyproject\\.toml)$'; then
    if command -v uv >/dev/null 2>&1; then
        if ! uv lock --check >/dev/null 2>&1; then
            echo "Security Violation (ADR-0011): Lockfile out of sync with pyproject.toml. Run 'uv lock' to synchronize." >&2
            exit 1
        fi
    fi
fi

# 3. Anti-Mock Frontdoor Verification (ADR-0003)
STAGED_TESTS=$(git diff --cached --name-only 2>/dev/null | grep -E '^tests/.*\\.py$' || true)
if [ -n "$STAGED_TESTS" ]; then
    for test_file in $STAGED_TESTS; do
        if [ -f "$test_file" ]; then
            if command -v spec-ops >/dev/null 2>&1; then
                spec-ops test audit-anti-mock "$test_file" >/dev/null 2>&1 || {
                    echo "Anti-Mock Violation (ADR-0003): Private mock backdoor detected in staged test file: $test_file" >&2
                    exit 1
                }
            elif command -v uv >/dev/null 2>&1; then
                uv run spec-ops test audit-anti-mock "$test_file" >/dev/null 2>&1 || {
                    echo "Anti-Mock Violation (ADR-0003): Private mock backdoor detected in staged test file: $test_file" >&2
                    exit 1
                }
            fi
        fi
    done
fi

# 4. Real-Time Secret Scanning Gate (ADR-0019)
if command -v spec-ops >/dev/null 2>&1; then
    spec-ops security scan-secrets --staged >/dev/null 2>&1 || {
        echo "Security Violation (ADR-0019): Exposed secrets or credentials detected in staged diff." >&2
        spec-ops security scan-secrets --staged
        exit 1
    }
elif command -v uv >/dev/null 2>&1; then
    uv run spec-ops security scan-secrets --staged >/dev/null 2>&1 || {
        echo "Security Violation (ADR-0019): Exposed secrets or credentials detected in staged diff." >&2
        uv run spec-ops security scan-secrets --staged
        exit 1
    }
fi

# 5. SpecOps Invariant & Health Gate (<500 lines per ADR-0002)
if command -v uv >/dev/null 2>&1; then
    exec uv run spec-ops health
elif command -v spec-ops >/dev/null 2>&1; then
    exec spec-ops health
else
    exec python3 -m spec_ops.cli.main health
fi
"""


PRE_PUSH_SCRIPT = """#!/bin/sh
# SpecOps native pre-push hook (ADR-0002, ADR-0011)
set -e

# Supply-chain lockfile verification (ADR-0011)
if command -v uv >/dev/null 2>&1; then
    uv lock --check
fi

# SpecOps Invariant & Health Gate (<500 lines per ADR-0002)
if command -v uv >/dev/null 2>&1; then
    exec uv run spec-ops health
elif command -v spec-ops >/dev/null 2>&1; then
    exec spec-ops health
else
    exec python3 -m spec_ops.cli.main health
fi
"""


def generate_pre_commit_hook() -> str:
    """Renders POSIX shell script content for the native pre-commit hook."""
    return PRE_COMMIT_SCRIPT


def generate_pre_push_hook() -> str:
    """Renders POSIX shell script content for the native pre-push hook."""
    return PRE_PUSH_SCRIPT


def resolve_hooks_dir(repo_root: Path) -> Path:
    """Resolves target .git/hooks directory for main repository or worktree."""
    git_dir = repo_root / ".git"
    if git_dir.is_file():
        res = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            p = Path(res.stdout.strip())
            return p if p.is_absolute() else (repo_root / p).resolve()
    return repo_root / ".git" / "hooks"


def install_native_hooks(repo_root: Path, force: bool = False) -> tuple[Path, Path]:
    """Installs native pre-commit and pre-push hooks directly into .git/hooks/.

    Also propagates hooks to existing autonomous worktrees.
    """
    hooks_dir = resolve_hooks_dir(repo_root)
    hooks_dir.mkdir(parents=True, exist_ok=True)

    pre_commit_path = hooks_dir / "pre-commit"
    pre_push_path = hooks_dir / "pre-push"

    if not force:
        existing = [p for p in (pre_commit_path, pre_push_path) if p.exists()]
        if existing:
            names = ", ".join(p.name for p in existing)
            raise FileExistsError(f"Hook(s) already exist: {names}. Use --force to overwrite.")

    pre_commit_content = generate_pre_commit_hook()
    pre_commit_path.write_text(pre_commit_content, encoding="utf-8")
    pre_commit_path.chmod(0o755)

    pre_push_content = generate_pre_push_hook()
    pre_push_path.write_text(pre_push_content, encoding="utf-8")
    pre_push_path.chmod(0o755)

    propagate_all_worktrees(repo_root)

    return pre_commit_path, pre_push_path


def propagate_hooks_to_worktree(repo_root: Path, worktree_dir: Path) -> Path | None:
    """Ensures native git hooks are active in an isolated worktree."""
    wt_git = worktree_dir / ".git"
    if not wt_git.is_file():
        return None

    try:
        content = wt_git.read_text(encoding="utf-8").strip()
    except OSError:
        return None

    if not content.startswith("gitdir: "):
        return None

    raw_gitdir = content[8:].strip()
    wt_gitdir = Path(raw_gitdir)
    if not wt_gitdir.is_absolute():
        wt_gitdir = (worktree_dir / wt_gitdir).resolve()

    wt_hooks = wt_gitdir / "hooks"
    parent_hooks = repo_root / ".git" / "hooks"

    if wt_hooks.is_symlink() or wt_hooks.exists():
        return wt_hooks

    if not parent_hooks.exists():
        parent_hooks.mkdir(parents=True, exist_ok=True)

    try:
        wt_hooks.symlink_to("../../hooks")
    except OSError:
        wt_hooks.mkdir(parents=True, exist_ok=True)
        for hook_file in parent_hooks.glob("*"):
            if hook_file.is_file():
                target = wt_hooks / hook_file.name
                shutil.copy2(hook_file, target)
                target.chmod(0o755)

    return wt_hooks


def propagate_all_worktrees(repo_root: Path) -> list[Path]:
    """Propagates hooks to all active worktrees discovered under .git/worktrees."""
    worktrees_meta = repo_root / ".git" / "worktrees"
    propagated: list[Path] = []
    if not worktrees_meta.is_dir():
        return propagated

    for wt_entry in worktrees_meta.iterdir():
        if wt_entry.is_dir():
            wt_hooks = wt_entry / "hooks"
            if not wt_hooks.is_symlink() and not wt_hooks.exists():
                try:
                    wt_hooks.symlink_to("../../hooks")
                    propagated.append(wt_hooks)
                except OSError:
                    pass
    return propagated


def scaffold_hooks_command(repo_root: Path, force: bool = False, native: bool = True) -> tuple[int, str]:
    """CLI handler for 'spec-ops scaffold hooks'."""
    try:
        pre_commit, pre_push = install_native_hooks(repo_root, force=force)
        return 0, f"Installed native git hooks into {pre_commit.name} and {pre_push.name}"
    except FileExistsError as exc:
        return 1, str(exc)
    except Exception as exc:
        return 1, f"Failed to scaffold git hooks: {exc}"
