"""Generative property-based tests for PRD delta decomposition (ADR-0009)."""

from pathlib import Path
from hypothesis import given, settings, strategies as st

from spec_ops.config.loader import load_config
from spec_ops.core.parser import extract_frontmatter
from spec_ops.prd.decomposer import PRDDecomposer
from spec_ops.scaffold.init import init_project


FALSIFIABLE_OUTCOME_SAMPLES = [
    "CLI emits JSON metrics matching telemetry schema when run with --json",
    "Heartbeat agent transmits ping payload to visualizer every 5 seconds",
    "Disconnected agents trigger stale warning alert within 15 seconds",
    "Database records commit timestamp in UTC ISO format",
    "REST endpoint returns HTTP 200 with active session token",
    "Worker process drops network egress packets targeting port 80",
    "Cache invalidation evicts stale entries after 60 seconds",
    "Config parser rejects unpinned version constraints with exit code 1",
]


@settings(max_examples=30, deadline=15000)
@given(
    initial_indices=st.lists(
        st.integers(min_value=0, max_value=len(FALSIFIABLE_OUTCOME_SAMPLES) - 1),
        min_size=2,
        max_size=4,
        unique=True,
    ),
    added_indices=st.lists(
        st.integers(min_value=0, max_value=len(FALSIFIABLE_OUTCOME_SAMPLES) - 1),
        min_size=1,
        max_size=3,
        unique=True,
    ),
)
def test_delta_decomposition_additive_invariant(
    tmp_path_factory,
    initial_indices: list[int],
    added_indices: list[int],
):
    """Verifies that delta decomposition is strictly additive: existing task frontmatter,

    IDs, file paths, and statuses in complete/ and refined/ remain byte-identical before
    and after delta decomposition.
    """
    tmp_path = tmp_path_factory.mktemp("delta_prop")
    init_project(tmp_path, name="DeltaInvariant")
    config = load_config(root_dir=tmp_path)

    # 1. Author initial PRD
    prd_dir = config.prd_dir / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd_file = prd_dir / "prd-0001-core.md"

    initial_outcomes = [FALSIFIABLE_OUTCOME_SAMPLES[i] for i in initial_indices]
    outcomes_text = "\n".join(f"{idx}. {text}" for idx, text in enumerate(initial_outcomes, 1))

    prd_file.write_text(
        f"""---
id: '0001'
title: Core Platform Engine
status: Accepted
created: 2026-09-29
target_persona: Alex
component: core
---

# PRD-0001 — Core Platform Engine

## Who this is for
- **Alex**: Systems architect.

## What the person cannot do today
- Cannot manage delta scope safely.

## What good looks like
1. Deterministic delta decomposition.

## What this does not do
- Does not edit git directly.

## Checkable Outcomes

{outcomes_text}
""",
        encoding="utf-8",
    )

    # 2. Decompose initial outcomes
    decomposer = PRDDecomposer(config)
    decomposer.decompose_by_outcomes("PRD-0001", include_spike=True)

    # 3. Simulate worktree progression: move some proposed tasks to complete and refined
    proposed_dir = config.backlog_dir / "proposed"
    complete_dir = config.backlog_dir / "complete"
    refined_dir = config.backlog_dir / "refined"
    complete_dir.mkdir(parents=True, exist_ok=True)
    refined_dir.mkdir(parents=True, exist_ok=True)

    proposed_files = sorted(proposed_dir.glob("*.md"))
    assert len(proposed_files) >= 2

    # Move first task to complete
    t_complete = proposed_files[0]
    c_content = t_complete.read_text(encoding="utf-8").replace("status: Proposed", "status: Complete")
    target_complete = complete_dir / t_complete.name
    target_complete.write_text(c_content, encoding="utf-8")
    t_complete.unlink()

    # Move second task to refined
    t_refined = proposed_files[1]
    r_content = t_refined.read_text(encoding="utf-8").replace("status: Proposed", "status: Refined")
    target_refined = refined_dir / t_refined.name
    target_refined.write_text(r_content, encoding="utf-8")
    t_refined.unlink()

    # Update PRIORITY.md
    priority_file = config.backlog_dir / "PRIORITY.md"
    priority_lines_before = priority_file.read_text(encoding="utf-8").splitlines()

    # 4. Snapshot complete/ and refined/ files
    snapshot_complete = {p.relative_to(tmp_path): p.read_bytes() for p in complete_dir.rglob("*.md")}
    snapshot_refined = {p.relative_to(tmp_path): p.read_bytes() for p in refined_dir.rglob("*.md")}

    assert len(snapshot_complete) >= 1
    assert len(snapshot_refined) >= 1

    # 5. Modify PRD by appending new outcomes
    new_outcomes = [FALSIFIABLE_OUTCOME_SAMPLES[i] for i in added_indices if i not in initial_indices]
    if not new_outcomes:
        new_outcomes = ["Unique observable outcome asserting metrics schema compliance"]

    all_outcomes = initial_outcomes + new_outcomes
    updated_outcomes_text = "\n".join(f"{idx}. {text}" for idx, text in enumerate(all_outcomes, 1))

    prd_content = prd_file.read_text(encoding="utf-8")
    # Replace checkable outcomes block
    import re
    updated_prd = re.sub(
        r"## Checkable Outcomes\s*\n.*?(?=\n## Linked User Stories|$)",
        f"## Checkable Outcomes\n\n{updated_outcomes_text}\n\n",
        prd_content,
        flags=re.DOTALL,
    )
    prd_file.write_text(updated_prd, encoding="utf-8")

    # 6. Execute delta decomposition
    delta_res, new_task_files, new_story_files = decomposer.decompose_diff("PRD-0001", include_spike=False)

    # 7. Invariant Verification: Byte-identical preservation
    # Every file in complete/ must exist at exact same path and have identical bytes
    for rel_path, expected_bytes in snapshot_complete.items():
        actual_file = tmp_path / rel_path
        assert actual_file.is_file(), f"File {rel_path} was removed from complete/"
        actual_bytes = actual_file.read_bytes()
        assert actual_bytes == expected_bytes, f"File {rel_path} in complete/ was mutated!"
        meta, _ = extract_frontmatter(actual_bytes.decode("utf-8"))
        assert meta.get("status") == "Complete"

    # Every file in refined/ must exist at exact same path and have identical bytes
    for rel_path, expected_bytes in snapshot_refined.items():
        actual_file = tmp_path / rel_path
        assert actual_file.is_file(), f"File {rel_path} was removed from refined/"
        actual_bytes = actual_file.read_bytes()
        assert actual_bytes == expected_bytes, f"File {rel_path} in refined/ was mutated!"
        meta, _ = extract_frontmatter(actual_bytes.decode("utf-8"))
        assert meta.get("status") == "Refined"

    # Any new tasks created must be in proposed/
    for tf in new_task_files:
        assert tf.parent == proposed_dir

    # Existing PRIORITY.md lines must be preserved
    priority_lines_after = priority_file.read_text(encoding="utf-8").splitlines()
    for line in priority_lines_before:
        assert line in priority_lines_after
