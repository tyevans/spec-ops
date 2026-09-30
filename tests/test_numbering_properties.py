"""Hypothesis property-based generative verification for numbering uniqueness invariants (ADR-0009)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.numbering import audit_numbering_uniqueness


@settings(max_examples=30, deadline=None)
@given(
    st.lists(st.integers(min_value=1, max_value=9999), min_size=1, max_size=20, unique=True),
    st.sampled_from(["adrs", "product", "backlog", "user_stories"]),
)
def test_property_unique_numbers_never_collide(numbers: list[int], group_dir: str):
    """Generative property: Any collection of unique numbers within a group produces zero collisions."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target_dir = root / "docs" / "project" / group_dir
        target_dir.mkdir(parents=True)

        prefix_map = {
            "adrs": "adr-",
            "product": "prd-",
            "backlog": "",
            "user_stories": "us-",
        }
        prefix = prefix_map[group_dir]

        for num in numbers:
            filename = f"{prefix}{num:04d}-item.md"
            (target_dir / filename).write_text(f"---\nid: '{num:04d}'\n---\n# Content\n", encoding="utf-8")

        report = audit_numbering_uniqueness(root)
        assert report.is_valid
        assert len(report.collisions) == 0


@settings(max_examples=30, deadline=None)
@given(
    st.lists(st.integers(min_value=1, max_value=500), min_size=1, max_size=10, unique=True),
    st.integers(min_value=1, max_value=500),
    st.sampled_from(["adrs", "product", "backlog", "user_stories"]),
)
def test_property_duplicate_numbers_always_detected(
    base_numbers: list[int], duplicate_target: int, group_dir: str
):
    """Generative property: Injecting a duplicate number in any group deterministically triggers collision."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target_dir = root / "docs" / "project" / group_dir
        target_dir.mkdir(parents=True)

        prefix_map = {
            "adrs": "adr-",
            "product": "prd-",
            "backlog": "",
            "user_stories": "us-",
        }
        prefix = prefix_map[group_dir]

        # Write base unique files
        for num in base_numbers:
            filename = f"{prefix}{num:04d}-base.md"
            (target_dir / filename).write_text(f"---\nid: '{num:04d}'\n---\n# Content\n", encoding="utf-8")

        # Inject two files with the exact same duplicate_target number
        file1 = target_dir / f"{prefix}{duplicate_target:04d}-dup1.md"
        file2 = target_dir / f"{prefix}{duplicate_target:04d}-dup2.md"
        file1.write_text(f"---\nid: '{duplicate_target:04d}'\n---\n# Duplicate 1\n", encoding="utf-8")
        file2.write_text(f"---\nid: '{duplicate_target:04d}'\n---\n# Duplicate 2\n", encoding="utf-8")

        report = audit_numbering_uniqueness(root)
        assert not report.is_valid
        colliding_numbers = {c.number for c in report.collisions}
        assert duplicate_target in colliding_numbers
        # Ensure reported paths match the colliding files
        matching = [c for c in report.collisions if c.number == duplicate_target]
        assert len(matching) == 1
        assert file1 in matching[0].paths
        assert file2 in matching[0].paths


@settings(max_examples=20, deadline=None)
@given(st.integers(min_value=1, max_value=9999))
def test_property_cross_group_numbers_strictly_isolated(common_num: int):
    """Generative property: Identical numbers across different artifact groups never trigger collisions."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs = root / "docs" / "project"

        (docs / "adrs").mkdir(parents=True)
        (docs / "product").mkdir(parents=True)
        (docs / "backlog").mkdir(parents=True)
        (docs / "user_stories").mkdir(parents=True)

        (docs / "adrs" / f"adr-{common_num:04d}-item.md").write_text(f"# ADR-{common_num:04d}", encoding="utf-8")
        (docs / "product" / f"prd-{common_num:04d}-item.md").write_text(f"# PRD-{common_num:04d}", encoding="utf-8")
        (docs / "backlog" / f"{common_num:04d}-item.md").write_text(f"# TASK-{common_num:04d}", encoding="utf-8")
        (docs / "user_stories" / f"us-{common_num:04d}-item.md").write_text(f"# US-{common_num:04d}", encoding="utf-8")

        report = audit_numbering_uniqueness(root)
        assert report.is_valid
        assert len(report.collisions) == 0
