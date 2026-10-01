"""Generative property-based tests for worktree salvage and patch staging invariants (ADR-0009)."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from spec_ops.rescue.salvage import (
    format_salvage_commit_message,
    get_staged_files,
    get_untracked_files,
    normalize_task_id,
    patch_files,
    salvage_files,
)
from spec_ops.worker.commits import parse_commit_trailers

CANDIDATE_POOL = [
    "src/spec_ops/core/models.py",
    "src/spec_ops/core/parser.py",
    "src/spec_ops/core/service.py",
    "src/spec_ops/cli/handler.py",
    "src/spec_ops/utils/helpers.py",
    "tests/core/test_models.py",
    "tests/core/test_parser.py",
    "tests/cli/test_handler.py",
    "docs/notes.md",
    "scratch_pad.py",
]


@st.composite
def file_selection_strategy(draw):
    pool = CANDIDATE_POOL
    selected = draw(st.sets(st.sampled_from(pool), min_size=1, max_size=len(pool) - 1))
    return sorted(selected)


@pytest.fixture(scope="module")
def shared_git_worktree():
    tmp_dir = Path(tempfile.mkdtemp(prefix="salvage_prop_"))
    repo = tmp_dir / "repo"
    repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)

    (repo / "init.txt").write_text("initial", encoding="utf-8")
    subprocess.run(["git", "add", "init.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    wt_dir = repo / ".worktrees" / "task-0018"
    wt_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "worktree", "add", "-b", "feat/TASK-0018", str(wt_dir), "main"], cwd=repo, check=True, capture_output=True)

    # Populate candidate files in worktree
    for rel in CANDIDATE_POOL:
        p = wt_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"content of {rel}\n", encoding="utf-8")

    yield wt_dir

    shutil.rmtree(tmp_dir, ignore_errors=True)


@settings(max_examples=30, deadline=10000)
@given(selected=file_selection_strategy())
def test_salvage_staging_isolation_property(shared_git_worktree: Path, selected: list[str]):
    """Property: For any arbitrary selection of file paths, only the chosen files are staged,

    and all unselected files remain untouched and untracked/unstaged.
    """
    wt_dir = shared_git_worktree
    # Ensure fresh state
    subprocess.run(["git", "reset", "HEAD"], cwd=wt_dir, capture_output=True)

    ok, msg = salvage_files(wt_dir, "TASK-0018", selected)
    assert ok, f"salvage_files failed: {msg}"

    staged = get_staged_files(wt_dir)
    assert sorted(staged) == sorted(selected), f"Staged files {staged} do not match selected {selected}"

    all_unselected = set(CANDIDATE_POOL) - set(selected)
    untracked = set(get_untracked_files(wt_dir))

    # All unselected files must NOT be staged
    assert set(staged).isdisjoint(all_unselected), "Unselected files leaked into staging index!"

    # All unselected candidate files must remain in the untracked set
    assert all_unselected.issubset(untracked), "Unselected files were unexpectedly modified or deleted!"


@settings(max_examples=25, deadline=10000)
@given(
    set_a=st.sets(st.sampled_from(CANDIDATE_POOL[:5]), min_size=1),
    set_b=st.sets(st.sampled_from(CANDIDATE_POOL[5:]), min_size=1),
)
def test_incremental_patch_staging_property(shared_git_worktree: Path, set_a: set[str], set_b: set[str]):
    """Property: Progressively patching disjoint file sets monotonically unions the staging index."""
    wt_dir = shared_git_worktree
    subprocess.run(["git", "reset", "HEAD"], cwd=wt_dir, capture_output=True)

    # 1. Salvage initial set A
    ok_a, _ = salvage_files(wt_dir, "TASK-0018", list(set_a))
    assert ok_a
    assert sorted(get_staged_files(wt_dir)) == sorted(set_a)

    # 2. Patch incremental set B
    ok_b, _ = patch_files(wt_dir, "TASK-0018", list(set_b))
    assert ok_b

    expected_union = sorted(set_a | set_b)
    staged = get_staged_files(wt_dir)
    assert sorted(staged) == expected_union

    unselected = set(CANDIDATE_POOL) - (set_a | set_b)
    assert set(staged).isdisjoint(unselected)


@given(
    task_num=st.integers(min_value=1, max_value=9999),
    title=st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_", min_size=3, max_size=50),
    slice_type=st.sampled_from(["feat", "fix", "refactor", "spike"]),
    author=st.from_regex(r"[A-Z][a-z]+ <[a-z]+@[a-z]+\.[a-z]+>", fullmatch=True),
    rescuer=st.from_regex(r"[A-Z][a-z]+ <[a-z]+@[a-z]+\.[a-z]+>", fullmatch=True),
)
def test_salvage_commit_trailer_invariants(task_num: int, title: str, slice_type: str, author: str, rescuer: str):
    """Property: Commit message formatting deterministically embeds valid RFC-822 dual-custody trailers."""
    canonical_id = f"TASK-{str(task_num).zfill(4)}"
    dummy_task = type("DummyTask", (), {
        "id": str(task_num),
        "canonical_id": canonical_id,
        "title": title,
        "slice_type": slice_type,
        "governing_stories": ["US-0088"],
        "governing_prds": ["PRD-0004"],
        "governing_adrs": ["ADR-0005"],
    })()

    msg = format_salvage_commit_message(dummy_task, author=author, rescued_by=rescuer)

    trailers = parse_commit_trailers(msg)
    assert trailers.get("SpecOps-Task") == canonical_id
    assert trailers.get("Author") == author
    assert trailers.get("Rescued-By") == rescuer
    assert trailers.get("Provenance") == "agent-human-hybrid"
    assert trailers.get("SpecOps-Story") == "US-0088"
    assert trailers.get("SpecOps-PRD") == "PRD-0004"
    assert trailers.get("SpecOps-ADR") == "ADR-0005"
