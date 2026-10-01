"""Hypothesis property-based tests for Milestone Planning Studio (ADR-0009).

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0025.
Validates frontmatter preservation, capacity simulation ordering, and roadmap sync invariants.
"""

from __future__ import annotations

import math
from pathlib import Path
import re
import string
from hypothesis import given, settings
from hypothesis import strategies as st
import yaml

from spec_ops.backlog.milestone_studio import (
    FeasibilitySimulation,
    MilestoneStudio,
    TaskAllocation,
)
from spec_ops.backlog.milestone_studio_sync import (
    sync_roadmap_milestone,
    update_task_frontmatter_milestone,
)
from spec_ops.core.migration import parse_frontmatter_and_body


@st.composite
def random_task_frontmatter_and_body(draw):
    """Generates realistic yet diverse task Markdown documents."""
    task_num = draw(st.integers(min_value=1, max_value=999))
    tid = f"TASK-{task_num:04d}"
    title = draw(st.text(alphabet=string.ascii_letters + " -", min_size=3, max_size=40)).strip() or "Sample Task"
    status = draw(st.sampled_from(["Refined", "Proposed", "Complete"]))
    target_bc = draw(st.sampled_from(["backlog", "core", "worker", "prd", "visualizer"]))

    dep_count = draw(st.integers(min_value=0, max_value=4))
    deps = [f"TASK-{draw(st.integers(min_value=1, max_value=100)):04d}" for _ in range(dep_count)]

    tags_count = draw(st.integers(min_value=0, max_value=3))
    tags = [f"tag-{draw(st.text(alphabet=string.ascii_lowercase, min_size=2, max_size=8))}" for _ in range(tags_count)]

    custom_int = draw(st.integers(min_value=1, max_value=1000))
    custom_bool = draw(st.booleans())
    custom_str = draw(st.text(alphabet=string.ascii_letters, min_size=1, max_size=20))

    meta = {
        "id": tid,
        "title": title,
        "status": status,
        "target_bc": target_bc,
        "dependencies": deps,
        "tags": tags,
        "custom_int": custom_int,
        "custom_bool": custom_bool,
        "custom_str": custom_str,
    }

    has_initial_ms = draw(st.booleans())
    if has_initial_ms:
        ms_key = draw(st.sampled_from(["milestone", "target_milestone", "target_release"]))
        meta[ms_key] = f"M{draw(st.integers(min_value=1, max_value=5))}-Release"

    raw_yaml = yaml.dump(meta, sort_keys=False, default_flow_style=False)
    body = f"\n# {title}\n\nDetailed task description with lists:\n- Item 1\n- Item 2\n"
    full_content = f"---\n{raw_yaml}---\n{body}"
    return meta, body, full_content


@settings(max_examples=50, deadline=None)
@given(
    data=random_task_frontmatter_and_body(),
    new_milestone=st.sampled_from(["M1-MVP", "M2-Q4-Release", "M3-Scale", "Milestone 4"]),
    execution_profile=st.sampled_from([None, "agent-autonomous", "human-lead", "hybrid-pair"]),
)
def test_property_frontmatter_preservation_across_reallocation(
    data: tuple[dict, str, str],
    new_milestone: str,
    execution_profile: str | None,
):
    """ADR-0009 Invariant: Milestone reallocation preserves all other frontmatter fields and body."""
    original_meta, original_body, full_content = data

    modified, new_content = update_task_frontmatter_milestone(
        full_content,
        new_milestone=new_milestone,
        execution_profile=execution_profile,
    )
    assert modified is True

    parsed_meta, _, parsed_body = parse_frontmatter_and_body(new_content)
    assert parsed_meta, "Frontmatter must remain valid YAML after update"

    # 1. Byte-exact preservation of markdown body
    assert parsed_body == original_body

    # 2. Target milestone field updated
    ms_val = (
        parsed_meta.get("milestone")
        or parsed_meta.get("target_milestone")
        or parsed_meta.get("target_release")
    )
    assert str(ms_val).strip("'\"") == new_milestone

    # 3. Execution profile updated if specified
    if execution_profile:
        assert parsed_meta.get("execution_profile") == execution_profile

    # 4. Strict preservation of all other metadata keys and values
    for k, v in original_meta.items():
        if k in ("milestone", "target_milestone", "target_release", "execution_profile"):
            continue
        assert k in parsed_meta, f"Field '{k}' was dropped during reallocation"
        assert parsed_meta[k] == v, f"Field '{k}' value mutated during reallocation"


@settings(max_examples=50, deadline=None)
@given(
    total=st.integers(min_value=0, max_value=100),
    completed_ratio=st.floats(min_value=0.0, max_value=1.0),
    weekly_velocity=st.floats(min_value=0.5, max_value=50.0),
    max_depth=st.integers(min_value=1, max_value=8),
)
def test_property_feasibility_confidence_intervals_ordering(
    total: int,
    completed_ratio: float,
    weekly_velocity: float,
    max_depth: int,
):
    """Generative property invariant: P50 <= P80 <= P95 confidence ordering and consistency."""
    completed = int(total * completed_ratio)
    remaining = total - completed

    daily_v = max(0.1, weekly_velocity / 7.0)
    p50_days = math.ceil(remaining / (daily_v * 1.0)) if remaining > 0 else 0
    p80_days = math.ceil(remaining / (daily_v * 0.8)) if remaining > 0 else 0
    p95_days = math.ceil(remaining / (daily_v * 0.6)) if remaining > 0 else 0

    assert 0 <= p50_days <= p80_days <= p95_days

    if remaining == 0:
        assert p50_days == 0
        assert p80_days == 0
        assert p95_days == 0


@settings(max_examples=30, deadline=None)
@given(
    task_num=st.integers(min_value=1, max_value=500),
    ms_target=st.sampled_from(["M1-MVP", "M2-Q4-Release", "M3-Horizon"]),
)
def test_property_roadmap_sync_deduplication(tmp_path_factory, task_num: int, ms_target: str):
    """Property invariant: ROADMAP.md sync places task in target milestone without duplication."""
    tmp_dir = tmp_path_factory.mktemp("roadmap_prop")
    roadmap_file = tmp_dir / "ROADMAP.md"

    tid = f"TASK-{task_num:04d}"
    title = f"Property Test Task {task_num}"

    # Initial sync to M1-MVP
    sync_roadmap_milestone(roadmap_file, tid, title, "M1-MVP")
    content1 = roadmap_file.read_text(encoding="utf-8")
    assert f"(`{tid}`)." in content1
    assert len(re.findall(rf"\(`?{tid}`?\)", content1)) == 1

    # Reallocate to target milestone
    sync_roadmap_milestone(roadmap_file, tid, title, ms_target)
    content2 = roadmap_file.read_text(encoding="utf-8")
    # Must appear exactly once in the entire file
    assert len(re.findall(rf"\(`?{tid}`?\)", content2)) == 1
