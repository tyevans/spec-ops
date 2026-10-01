"""Hypothesis property-based tests for Supply-Chain Lockfile Mutation Sentinel (ADR-0009, ADR-0018)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.config.models import SecuritySettings, SpecOpsConfig
from spec_ops.security.lockfile_sentinel import (
    PROTECTED_LOCKFILES,
    detect_lockfile_mutations,
    inspect_lockfile_sentinel,
    is_protected_lockfile,
    remediate_lockfile_mutations,
)

SAFE_FILENAMES = [
    "src/spec_ops/main.py",
    "docs/explanation/architecture.md",
    "tests/test_foo.py",
    "README.md",
    "package.json",
    "Cargo.toml",
    "pyproject.toml",
    "LICENSE",
]

LOCKFILE_SAMPLES = sorted(PROTECTED_LOCKFILES)


@given(
    protected=st.lists(st.sampled_from(LOCKFILE_SAMPLES), min_size=1, max_size=len(LOCKFILE_SAMPLES), unique=True),
    safe_files=st.lists(st.sampled_from(SAFE_FILENAMES), max_size=5, unique=True),
)
@settings(max_examples=25, deadline=None)
def test_property_lockfile_mutations_strictly_detected_and_blocked(protected: list[str], safe_files: list[str]):
    """Invariant: Any file change set including at least one protected lockfile is blocked without a waiver."""
    all_files = list(set(protected + safe_files))

    detected = detect_lockfile_mutations(Path("."), changed_files=all_files)
    assert set(detected) == set(protected)

    result = inspect_lockfile_sentinel(
        repo_dir=".",
        fix=False,
        task_allows_dependencies=False,
        changed_files=all_files,
    )

    assert result.ok is False
    assert result.valid is False
    assert set(result.modified_lockfiles) == set(protected)
    assert len(result.violations) == len(protected)
    assert result.waiver_applied is False
    for p in protected:
        assert any(p in v for v in result.violations)


@given(
    safe_files=st.lists(st.sampled_from(SAFE_FILENAMES), max_size=8, unique=True)
)
@settings(max_examples=20, deadline=None)
def test_property_non_lockfile_mutations_always_pass(safe_files: list[str]):
    """Invariant: Any change set without protected lockfiles passes cleanly."""
    detected = detect_lockfile_mutations(Path("."), changed_files=safe_files)
    assert len(detected) == 0

    result = inspect_lockfile_sentinel(
        repo_dir=".",
        fix=False,
        task_allows_dependencies=False,
        changed_files=safe_files,
    )

    assert result.ok is True
    assert result.valid is True
    assert len(result.violations) == 0
    assert len(result.modified_lockfiles) == 0
    assert result.waiver_applied is False


@given(
    protected=st.lists(st.sampled_from(LOCKFILE_SAMPLES), min_size=1, max_size=len(LOCKFILE_SAMPLES), unique=True),
    safe_files=st.lists(st.sampled_from(SAFE_FILENAMES), max_size=5, unique=True),
    via_task=st.booleans(),
)
@settings(max_examples=25, deadline=None)
def test_property_waivers_permit_lockfile_mutations(
    protected: list[str], safe_files: list[str], via_task: bool
):
    """Invariant: Approved waivers explicitly permit lockfile mutations across all combinations."""
    all_files = list(set(protected + safe_files))

    cfg = None
    task_dep = False

    if via_task:
        task_dep = True
    else:
        cfg = SpecOpsConfig(
            security=SecuritySettings(lockfile_immutability=False)
        )

    result = inspect_lockfile_sentinel(
        repo_dir=".",
        fix=False,
        config=cfg,
        task_allows_dependencies=task_dep,
        changed_files=all_files,
    )

    assert result.ok is True
    assert result.valid is True
    assert set(result.modified_lockfiles) == set(protected)
    assert result.waiver_applied is True
    assert result.waiver_details is not None
    assert len(result.violations) == 0


@given(
    target_lockfile=st.sampled_from(LOCKFILE_SAMPLES),
    noise_files=st.lists(st.sampled_from(SAFE_FILENAMES), max_size=3, unique=True),
)
@settings(max_examples=10, deadline=None)
def test_property_remediation_restores_git_worktree_cleanliness(
    tmp_path_factory, target_lockfile: str, noise_files: list[str]
):
    """Invariant: inspect_lockfile_sentinel with fix=True restores git state."""
    repo = tmp_path_factory.mktemp("prop_remediate")

    # Git init
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo, check=True, capture_output=True)

    # Initial baseline commit with tracked lockfile
    lock_path = repo / target_lockfile
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("initial lockfile content\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    # Modify the lockfile
    lock_path.write_text("unauthorized modified content\n", encoding="utf-8")

    # Also add noise safe files
    for nf in noise_files:
        p = repo / nf
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("safe content\n", encoding="utf-8")

    # Run sentinel with fix=True
    result = inspect_lockfile_sentinel(repo, fix=True)

    assert result.ok is True
    assert target_lockfile in result.remediated
    # Content must have been reverted to original HEAD
    assert lock_path.read_text(encoding="utf-8") == "initial lockfile content\n"
