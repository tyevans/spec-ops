"""Generative property-based tests for SDLC provenance and traceability audit engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009; PRD-0005; US-0019.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

import re
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.models import Persona, PRD, ProjectData, Task, UserStory
from spec_ops.core.provenance import (
    CommitRecord,
    audit_provenance,
    extract_task_ids_from_trailers,
    extract_trailers_from_text,
    is_autonomous_contributor,
    parse_commit_from_raw,
)


# Strategy generating arbitrary commit texts with or without trailers
valid_chars = st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"), blacklist_characters=("\n", "\r"))
safe_text = st.text(alphabet=valid_chars, min_size=1, max_size=40)
task_num_strategy = st.integers(min_value=1, max_value=9999)


@given(
    subject=safe_text,
    body=safe_text,
    task_num=task_num_strategy,
    has_trailer=st.booleans(),
    trailer_key=st.sampled_from(["SpecOps-Task", "specops-task", "Task-ID", "task-id", "Task"]),
)
@settings(max_examples=100)
def test_property_commit_trailer_determinism(
    subject: str,
    body: str,
    task_num: int,
    has_trailer: bool,
    trailer_key: str,
):
    """Invariant: spec-ops audit provenance deterministically identifies commits missing SpecOps-Task trailers."""
    task_id = f"TASK-{task_num:04d}"
    if has_trailer:
        full_text = f"{subject}\n\n{body}\n\n{trailer_key}: {task_id}\n"
    else:
        # Commit without task trailer
        full_text = f"{subject}\n\n{body}\n\nOther-Trailer: irrelevant\n"

    trailers = extract_trailers_from_text(full_text)
    task_ids = extract_task_ids_from_trailers(trailers)

    if has_trailer:
        assert task_id in task_ids, f"Expected {task_id} in {task_ids}"
    else:
        assert len(task_ids) == 0, f"Expected 0 task IDs, got {task_ids}"

    rec = parse_commit_from_raw(
        full_hash="0123456789abcdef0123456789abcdef01234567",
        short_hash="0123456",
        author="Developer",
        email="dev@example.com",
        date="2026-09-30",
        subject=subject,
        body=body + (f"\n\n{trailer_key}: {task_id}" if has_trailer else ""),
    )

    data = ProjectData(
        personas=[Persona(id="jordan", name="Jordan")],
        prds=[PRD(id="PRD-0005", title="Graph", target_persona="Jordan")],
        stories=[UserStory(id="US-0019", title="Traceability", persona="Jordan", governing_prd="PRD-0005")],
        tasks=[Task(id=task_id, title="Test Task", status="Complete", governing_stories=["US-0019"])],
    )

    report = audit_provenance(data, [rec])

    if has_trailer:
        assert rec not in report.unanchored_commits
        assert report.anchored_commits == 1
    else:
        assert rec in report.unanchored_commits
        assert report.anchored_commits == 0
        assert report.integrity_pct < 100.0


@given(
    trailer_val=st.text(min_size=0, max_size=30),
    author=st.text(min_size=0, max_size=30),
    email=st.text(min_size=0, max_size=30),
)
@settings(max_examples=80)
def test_property_autonomous_attribution_soundness(trailer_val: str, author: str, email: str):
    """Invariant: contributor attribution is sound across arbitrary author metadata."""
    trailers = {"Provenance": trailer_val} if trailer_val else {}
    is_auto = is_autonomous_contributor(trailers, author=author, email=email)

    # If any autonomous indicator is present, must be True
    v_low = trailer_val.lower()
    ident = f"{author} {email}".lower()
    expected = (
        any(k in v_low for k in ("autonomous", "spec-ops", "agent", "worker", "bot"))
        or any(k in ident for k in ("[bot]", "spec-ops-worker", "autonomous", "agent-runner"))
    )
    assert is_auto == expected


@given(task_numbers=st.lists(task_num_strategy, min_size=1, max_size=10, unique=True))
@settings(max_examples=50)
def test_property_multiple_tasks_extraction(task_numbers: list[int]):
    """Invariant: multiple task references in a single trailer are all extracted."""
    task_ids = [f"TASK-{n:04d}" for n in task_numbers]
    combined_val = ", ".join(task_ids)
    trailers = {"SpecOps-Task": combined_val}
    extracted = extract_task_ids_from_trailers(trailers)

    for tid in task_ids:
        assert tid in extracted
    assert len(extracted) == len(task_ids)


@given(
    n_commits=st.integers(min_value=1, max_value=20),
    n_unanchored=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=50)
def test_property_audit_partition_integrity(n_commits: int, n_unanchored: int):
    """Invariant: total commits == anchored commits + unanchored commits, and integrity is bounded."""
    actual_unanchored = min(n_commits, n_unanchored)
    actual_anchored = n_commits - actual_unanchored

    commits: list[CommitRecord] = []
    tasks: list[Task] = []
    for i in range(actual_anchored):
        tid = f"TASK-{i + 1:04d}"
        tasks.append(Task(id=tid, title=f"Task {i + 1}", status="Complete", governing_stories=["US-0001"]))
        commits.append(
            CommitRecord(
                full_hash=f"{i:040d}",
                short_hash=f"{i:07d}",
                author="Dev",
                email="dev@example.com",
                date="2026-09-30",
                subject=f"feat: {tid}",
                body=f"SpecOps-Task: {tid}",
                trailers={"SpecOps-Task": tid},
                task_ids=[tid],
            )
        )
    for i in range(actual_unanchored):
        idx = actual_anchored + i
        commits.append(
            CommitRecord(
                full_hash=f"{idx:040d}",
                short_hash=f"{idx:07d}",
                author="Rogue",
                email="rogue@example.com",
                date="2026-09-30",
                subject="rogue commit",
                body="no trailer",
                trailers={},
                task_ids=[],
            )
        )

    data = ProjectData(
        personas=[Persona(id="taylor", name="Taylor")],
        prds=[PRD(id="PRD-0001", title="PRD", target_persona="Taylor")],
        stories=[UserStory(id="US-0001", title="Story", persona="Taylor", governing_prd="PRD-0001")],
        tasks=tasks,
    )

    report = audit_provenance(data, commits)

    assert report.total_commits == len(commits)
    assert report.anchored_commits == actual_anchored
    assert len(report.unanchored_commits) == actual_unanchored
    assert report.total_commits == report.anchored_commits + len(report.unanchored_commits)
    assert 0.0 <= report.integrity_pct <= 100.0
    if actual_unanchored == 0:
        assert report.integrity_pct == 100.0
    else:
        assert report.integrity_pct < 100.0
