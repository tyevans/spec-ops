"""Hypothesis generative property tests for worktree stash and clean reset recovery (ADR-0009)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from spec_ops.rescue.lifecycle import is_worktree_dirty
from spec_ops.rescue.stash_reset import (
    RescueStashMetadata,
    StashResetResult,
    apply_rescue_stash,
    clean_reset,
    create_rescue_stash,
)

safe_alphanumeric = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=("_", "-")),
    min_size=1,
    max_size=30,
)

safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"), whitelist_characters=("\n", "_", "-")),
    min_size=1,
    max_size=200,
)


@given(
    stash_id=safe_alphanumeric,
    task_id=st.integers(min_value=1, max_value=9999).map(lambda n: f"TASK-{n:04d}"),
    timestamp=st.datetimes().map(lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")),
    branch=st.sampled_from(["main", "feat/TASK-0010", "feat/TASK-0159", "task/spike-01"]),
    patch_file=safe_alphanumeric.map(lambda s: f"/tmp/{s}.patch"),
    modified_files=st.lists(safe_alphanumeric.map(lambda s: f"src/{s}.py"), min_size=0, max_size=5),
    diff_summary=safe_text,
)
def test_rescue_stash_metadata_lossless_roundtrip_property(
    stash_id: str,
    task_id: str,
    timestamp: str,
    branch: str,
    patch_file: str,
    modified_files: list[str],
    diff_summary: str,
):
    """Property: Metadata serialization to dict and from_dict is perfectly lossless."""
    meta = RescueStashMetadata(
        stash_id=stash_id,
        task_id=task_id,
        timestamp=timestamp,
        branch=branch,
        patch_file=patch_file,
        modified_files=modified_files,
        diff_summary=diff_summary,
    )
    serialized = meta.to_dict()
    restored = RescueStashMetadata.from_dict(serialized)
    assert restored.stash_id == meta.stash_id
    assert restored.task_id == meta.task_id
    assert restored.timestamp == meta.timestamp
    assert restored.branch == meta.branch
    assert restored.patch_file == meta.patch_file
    assert restored.modified_files == meta.modified_files
    assert restored.diff_summary == meta.diff_summary


@settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow], deadline=None)
@given(
    mod_content=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1, max_size=50),
    new_filename=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll")), min_size=3, max_size=10).map(lambda s: f"{s.lower()}.txt"),
    new_content=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1, max_size=50),
)
def test_stash_reset_and_reapply_preserves_arbitrary_diff_property(
    tmp_path_factory: pytest.TempPathFactory,
    mod_content: str,
    new_filename: str,
    new_content: str,
):
    """Property: Stashing and resetting any arbitrary directory state produces a clean git working tree,

    and applying the generated rescue stash completely restores the uncommitted diff.
    """
    repo = tmp_path_factory.mktemp("prop_repo")
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "PropTester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "proptester@specops.test"], cwd=repo, check=True, capture_output=True)

    tracked_file = repo / "tracked.txt"
    tracked_file.write_text("initial base content\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: base commit"], cwd=repo, check=True, capture_output=True)

    # 1. Dirty the worktree with arbitrary modifications and untracked files
    tracked_file.write_text(f"modified: {mod_content}\n", encoding="utf-8")
    untracked_file = repo / new_filename
    untracked_file.write_text(f"untracked: {new_content}\n", encoding="utf-8")

    assert is_worktree_dirty(repo)

    # 2. Execute clean_reset with stash=True
    result = clean_reset(repo, stash=True, task_id="TASK-PROP")

    assert result.success is True
    assert result.is_clean is True
    assert result.stash_id is not None
    assert not is_worktree_dirty(repo)
    assert not untracked_file.exists()
    assert tracked_file.read_text(encoding="utf-8") == "initial base content\n"

    # 3. Apply the rescue stash and verify exact restoration
    ok, msg = apply_rescue_stash(repo, result.stash_id)
    assert ok is True
    assert tracked_file.read_text(encoding="utf-8") == f"modified: {mod_content}\n"
    assert untracked_file.exists()
    assert untracked_file.read_text(encoding="utf-8") == f"untracked: {new_content}\n"
