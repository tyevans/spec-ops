"""Generative property-based testing (Hypothesis) for milestone rollover invariants.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0077.
Enforces generative invariant assertions without private mock backdoors.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
import yaml

from spec_ops.backlog.rollover import (
    MilestoneRolloverCoordinator,
    matches_milestone,
    update_frontmatter_milestone,
)
from spec_ops.core.migration import parse_frontmatter_and_body


st_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" _-"),
    min_size=1,
    max_size=30,
).map(lambda s: s.strip() or "safe_val")

st_milestone_name = st.sampled_from(["M1", "M2", "M3", "M1-MVP", "Release-1", "v2.0", "Sprint-4"])

st_field_key = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll"), whitelist_characters="_"),
    min_size=2,
    max_size=15,
).filter(lambda k: k not in ("target_release", "milestone", "target_milestone", "id", "status"))


@st.composite
def st_task_markdown(
    draw: st.DrawFn,
    status: str = "Refined",
    milestone_field: str = "target_release",
    from_ms: str = "M1",
) -> tuple[dict[str, Any], str, str]:
    task_num = draw(st.integers(min_value=1, max_value=999))
    title = draw(st_safe_text)
    custom_key = draw(st_field_key)
    custom_val = draw(st_safe_text)
    body_text = draw(st.text(min_size=0, max_size=200))

    meta: dict[str, Any] = {
        "id": f"{task_num:04d}",
        "title": title,
        "status": status,
        custom_key: custom_val,
        milestone_field: from_ms,
    }

    yaml_block = yaml.dump(meta, sort_keys=False, default_flow_style=False).strip()
    full_content = f"---\n{yaml_block}\n---\n\n# TASK-{task_num:04d}: {title}\n{body_text}\n"
    return meta, full_content, body_text


class TestRolloverGenerativeInvariants:
    """Hypothesis generative properties proving mathematical safety of rollover mutations."""

    @settings(max_examples=50)
    @given(
        task_data=st_task_markdown(status="Refined", milestone_field="target_release", from_ms="M1"),
        to_milestone=st.sampled_from(["M2", "M3", "Sprint-9", "Release-2"]),
    )
    def test_property_non_target_fields_and_body_preserved_verbatim(
        self,
        task_data: tuple[dict[str, Any], str, str],
        to_milestone: str,
    ) -> None:
        """Asserts rollover ONLY modifies milestone fields and preserves all other frontmatter attributes."""
        original_meta, original_content, original_body = task_data

        modified, new_content, matched_key, _ = update_frontmatter_milestone(
            original_content,
            from_milestone="M1",
            to_milestone=to_milestone,
        )

        assert modified is True
        assert matched_key == "target_release"

        new_meta, _, new_body = parse_frontmatter_and_body(new_content)

        # 1. Target milestone field updated to to_milestone
        assert new_meta.get("target_release") == to_milestone

        # 2. All non-target frontmatter keys preserved with identical values
        for k, v in original_meta.items():
            if k not in ("target_release", "milestone", "target_milestone"):
                assert k in new_meta
                assert new_meta[k] == v, f"Frontmatter key '{k}' mutated unexpectedly!"

        # 3. Non-frontmatter body is 100% byte-for-byte identical
        assert new_body == parse_frontmatter_and_body(original_content)[2]

    @settings(max_examples=50)
    @given(
        task_data=st_task_markdown(status="Proposed", milestone_field="milestone", from_ms="M1"),
        to_milestone=st.sampled_from(["M2", "Release-X", "Sprint-Beta"]),
    )
    def test_property_milestone_tag_updated_preserving_attributes(
        self,
        task_data: tuple[dict[str, Any], str, str],
        to_milestone: str,
    ) -> None:
        """Asserts rollover updates alternative milestone tag preserving other fields."""
        original_meta, original_content, _ = task_data

        modified, new_content, matched_key, _ = update_frontmatter_milestone(
            original_content,
            from_milestone="M1",
            to_milestone=to_milestone,
        )

        assert modified is True
        assert matched_key == "milestone"

        new_meta, _, new_body = parse_frontmatter_and_body(new_content)
        assert new_meta.get("milestone") == to_milestone

        for k, v in original_meta.items():
            if k not in ("target_release", "milestone", "target_milestone"):
                assert new_meta[k] == v

        assert new_body == parse_frontmatter_and_body(original_content)[2]

    @settings(max_examples=35)
    @given(
        task_data=st_task_markdown(status="Complete", milestone_field="target_release", from_ms="M1"),
        to_milestone=st.sampled_from(["M2", "M3", "v2"]),
    )
    def test_property_completed_tasks_never_modified_on_disk(
        self,
        task_data: tuple[dict[str, Any], str, str],
        to_milestone: str,
    ) -> None:
        """Asserts tasks in complete/ are strictly untouched regardless of milestone metadata."""
        _, original_content, _ = task_data

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            backlog_dir = Path(tmp_dir_str)
            complete_dir = backlog_dir / "complete"
            refined_dir = backlog_dir / "refined"
            proposed_dir = backlog_dir / "proposed"

            complete_dir.mkdir(parents=True, exist_ok=True)
            refined_dir.mkdir(parents=True, exist_ok=True)
            proposed_dir.mkdir(parents=True, exist_ok=True)

            task_file = complete_dir / "0001-completed-task.md"
            task_file.write_text(original_content, encoding="utf-8")

            coord = MilestoneRolloverCoordinator(backlog_dir)
            result = coord.rollover(from_milestone="M1", to_milestone=to_milestone)

            # Completed task must NOT be counted as transitioned
            assert result.transitioned_count == 0
            assert "TASK-0001" not in result.transitioned_tasks

            # Content on disk must be 100% byte-for-byte identical
            disk_content = task_file.read_bytes().decode("utf-8")
            assert disk_content == original_content

    @settings(max_examples=30)
    @given(
        task_data=st_task_markdown(status="Refined", milestone_field="target_release", from_ms="M1"),
        to_milestone=st.sampled_from(["M2", "Release-Final"]),
    )
    def test_property_idempotence_and_second_pass_zero_mutations(
        self,
        task_data: tuple[dict[str, Any], str, str],
        to_milestone: str,
    ) -> None:
        """Asserts running rollover twice is idempotent and makes zero mutations on second pass."""
        _, original_content, _ = task_data

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            backlog_dir = Path(tmp_dir_str)
            refined_dir = backlog_dir / "refined"
            refined_dir.mkdir(parents=True, exist_ok=True)

            task_file = refined_dir / "0002-task.md"
            task_file.write_text(original_content, encoding="utf-8")

            coord = MilestoneRolloverCoordinator(backlog_dir)

            # First pass: transitions task to to_milestone
            res1 = coord.rollover("M1", to_milestone)
            assert res1.transitioned_count == 1
            content_after_pass1 = task_file.read_text(encoding="utf-8")

            # Second pass: zero tasks in M1, leaves file byte-for-byte untouched
            res2 = coord.rollover("M1", to_milestone)
            assert res2.transitioned_count == 0
            assert task_file.read_text(encoding="utf-8") == content_after_pass1
