"""Hypothesis property-based tests for worker orchestrator and specification consultation invariants."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.models import Task
from spec_ops.worker.commits import (
    build_commit_trailers,
    format_task_commit_message,
    parse_commit_trailers,
)
from spec_ops.worker.consultation import (
    conduct_peer_consultation,
    consult_specifications,
)

id_strategy = st.integers(min_value=1, max_value=9999).map(lambda n: f"TASK-{n:04d}")
bc_strategy = st.sampled_from(["worker", "core", "prd", "visualizer", "security", "backlog", "spike"])
slice_strategy = st.sampled_from(["feat", "fix", "refactor", "chore", "spike", "test"])
adr_strategy = st.lists(st.integers(min_value=1, max_value=20).map(lambda n: f"ADR-{n:04d}"), max_size=4)
prd_strategy = st.lists(st.integers(min_value=1, max_value=10).map(lambda n: f"PRD-{n:04d}"), max_size=3)
story_strategy = st.lists(st.integers(min_value=1, max_value=150).map(lambda n: f"US-{n:04d}"), max_size=3)


@given(
    task_id=id_strategy,
    title=st.text(min_size=1, max_size=50).filter(lambda s: "\n" not in s and ":" not in s),
    target_bc=bc_strategy,
    slice_type=slice_strategy,
    adrs=adr_strategy,
    prds=prd_strategy,
    stories=story_strategy,
)
@settings(max_examples=40)
def test_property_commit_trailers_roundtrip(task_id, title, target_bc, slice_type, adrs, prds, stories):
    """Verifies RFC-822 git trailer formatting and roundtrip invariance."""
    task = Task(
        id=task_id,
        title=title,
        target_bc=target_bc,
        slice_type=slice_type,
        governing_adrs=adrs,
        governing_prds=prds,
        governing_stories=stories,
    )

    trailers = build_commit_trailers(task, slice_type=slice_type)

    assert trailers["SpecOps-Task"] == task_id
    assert trailers["SpecOps-Slice"] == slice_type
    if stories:
        assert trailers["SpecOps-Story"] == ", ".join(stories)
    if prds:
        assert trailers["SpecOps-PRD"] == ", ".join(prds)
    if adrs:
        assert trailers["SpecOps-ADR"] == ", ".join(adrs)

    commit_msg = format_task_commit_message(task)
    parsed = parse_commit_trailers(commit_msg)

    assert parsed["SpecOps-Task"] == task_id
    assert parsed["SpecOps-Slice"] == slice_type
    if stories:
        assert parsed["SpecOps-Story"] == ", ".join(stories)
    if prds:
        assert parsed["SpecOps-PRD"] == ", ".join(prds)
    if adrs:
        assert parsed["SpecOps-ADR"] == ", ".join(adrs)


@given(
    task_id=id_strategy,
    title=st.text(min_size=1, max_size=40),
    target_bc=bc_strategy,
    adrs=adr_strategy,
    prds=prd_strategy,
    stories=story_strategy,
)
@settings(max_examples=30)
def test_property_spec_consultation_invariants(task_id, title, target_bc, adrs, prds, stories):
    """Verifies that specification consultation never crashes and preserves relational links."""
    repo_root = Path(__file__).resolve().parent.parent
    task = Task(
        id=task_id,
        title=title,
        target_bc=target_bc,
        governing_adrs=adrs,
        governing_prds=prds,
        governing_stories=stories,
    )

    report = consult_specifications(task, repo_root)

    assert report.task_id == task_id
    assert report.target_bc == target_bc
    assert len(report.adrs) == len(adrs)
    assert len(report.prds) == len(prds)
    assert len(report.stories) == len(stories)

    data = report.to_dict()
    assert json.dumps(data)
    assert report.brief
    assert title in report.brief


@given(
    target_bc=bc_strategy,
    sub_bc=st.sampled_from(["prd", "visualizer", "security", "bridge"]),
)
@settings(max_examples=25)
def test_property_peer_consultation_seam_isolation(tmp_path_factory, target_bc, sub_bc):
    """Verifies bounded context seam detection across combinations."""
    tmp_path = tmp_path_factory.mktemp("peer_prop")
    task = Task(id="0114", title="Test", target_bc=target_bc)

    if target_bc == sub_bc:
        files = [f"src/spec_ops/{target_bc}/module.py"]
        review = conduct_peer_consultation(task, tmp_path, tmp_path, check_git=False, changed_files=files)
        assert len(review.seam_violations) == 0
    else:
        files = [f"src/spec_ops/{sub_bc}/other.py"]
        review = conduct_peer_consultation(task, tmp_path, tmp_path, check_git=False, changed_files=files)
        assert any(f"'{sub_bc}'" in s for s in review.seam_violations)
