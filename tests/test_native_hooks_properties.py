"""Hypothesis property-based tests for native git hook scaffolding (ADR-0009)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from spec_ops.scaffold.native_hooks import (
    generate_pre_commit_hook,
    generate_pre_push_hook,
    install_native_hooks,
    propagate_hooks_to_worktree,
    resolve_hooks_dir,
)

# Common bashisms that violate POSIX /bin/sh compliance
PROHIBITED_BASHISMS = [
    re.compile(r"\[\["),              # Bash double brackets
    re.compile(r"\]\]"),
    re.compile(r"\bfunction\s+[a-zA-Z0-9_]+"),  # 'function foo' syntax
    re.compile(r"<<<"),               # Here-strings
    re.compile(r"\$\{?[a-zA-Z0-9_]+\[@\]"),     # Bash array indexing
    re.compile(r"\[\s+[^\]]+\s+==\s+"),          # == equality in single brackets (POSIX uses =)
]

VALID_BRANCH_CHARS = st.characters(codec="ascii", whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=("-", "_", "/"))
BRANCH_STRATEGY = st.text(VALID_BRANCH_CHARS, min_size=2, max_size=30).filter(
    lambda s: bool(re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_\-/]{0,28}[a-zA-Z0-9]$", s))
    and "//" not in s
    and ".." not in s
    and not s.endswith(".lock")
)

BACKLOG_PATHS = st.sampled_from([
    "docs/project/backlog/PRIORITY.md",
    "docs/project/backlog/refined/0010-sample.md",
    "docs/project/backlog/proposed/0099-draft.md",
    "docs/project/backlog/complete/0001-setup.md",
    "docs/project/backlog/ROADMAP.md",
])

NON_BACKLOG_PATHS = st.sampled_from([
    "src/spec_ops/core/engine.py",
    "tests/test_feature.py",
    "docs/how-to/setup.md",
    "README.md",
])


def test_native_hooks_posix_syntax():
    """Validates that generated hook scripts pass POSIX shell syntax checking."""
    sh_path = shutil.which("sh")
    assert sh_path is not None, "POSIX shell interpreter 'sh' not found"

    for gen_func in (generate_pre_commit_hook, generate_pre_push_hook):
        script = gen_func()
        assert script.startswith("#!/bin/sh\n")

        # Run POSIX syntax validation: sh -n validates without executing
        proc = subprocess.run([sh_path, "-n", "-s"], input=script, text=True, capture_output=True)
        assert proc.returncode == 0, f"POSIX shell syntax check failed:\n{proc.stderr}"

        # Assert no bashisms present
        for pattern in PROHIBITED_BASHISMS:
            assert not pattern.search(script), f"Bashism detected matching pattern: {pattern.pattern}"


@settings(max_examples=30, deadline=None)
@given(branch_name=BRANCH_STRATEGY, staged_path=BACKLOG_PATHS)
def test_hypothesis_backlog_isolation_invariant(tmp_path_factory, branch_name: str, staged_path: str):
    """Property Invariant: Pre-commit hook aborts on non-main branch modifying backlog (ADR-0005)."""
    repo = tmp_path_factory.mktemp("hypo_hook_repo")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "HypoTester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "hypo@test.com"], cwd=repo, check=True, capture_output=True)

    # Initial commit
    (repo / "base.txt").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    install_native_hooks(repo, force=True)

    is_main_or_master = branch_name in ("main", "master")
    if not is_main_or_master:
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo, check=True, capture_output=True)

    # Stage backlog modification
    target = repo / staged_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Backlog modification", encoding="utf-8")
    subprocess.run(["git", "add", staged_path], cwd=repo, check=True, capture_output=True)

    res = subprocess.run(["git", "commit", "-m", "attempted change"], cwd=repo, capture_output=True, text=True)

    if is_main_or_master:
        # On main/master, backlog check does not abort (it proceeds to next checks)
        assert "Invariant Violation (ADR-0005)" not in (res.stdout + res.stderr)
    else:
        # On any feature or task branch, backlog isolation strictly aborts
        assert res.returncode == 1
        assert "Invariant Violation (ADR-0005)" in (res.stdout + res.stderr)


@settings(max_examples=25, deadline=None)
@given(branch_name=BRANCH_STRATEGY, staged_path=NON_BACKLOG_PATHS)
def test_hypothesis_non_backlog_files_proceed(tmp_path_factory, branch_name: str, staged_path: str):
    """Property Invariant: Pre-commit hook does not trigger ADR-0005 violation on non-backlog files."""
    repo = tmp_path_factory.mktemp("hypo_clean_repo")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "HypoTester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "hypo@test.com"], cwd=repo, check=True, capture_output=True)

    (repo / "base.txt").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    install_native_hooks(repo, force=True)

    if branch_name not in ("main", "master"):
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo, check=True, capture_output=True)

    target = repo / staged_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Clean code file\n", encoding="utf-8")
    subprocess.run(["git", "add", staged_path], cwd=repo, check=True, capture_output=True)

    res = subprocess.run(["git", "commit", "-m", "clean commit"], cwd=repo, capture_output=True, text=True)

    assert "Invariant Violation (ADR-0005)" not in (res.stdout + res.stderr)
