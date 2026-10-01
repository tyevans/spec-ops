"""Generative property-based tests for PRD sync and auto-save invariants.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0013; PRD-0003; US-0044.
Asserts that arbitrary edit sequences preserve content, AST section headers,
and falsifiable outcomes without markdown corruption or crashes.
"""

from __future__ import annotations

from pathlib import Path
import re

from hypothesis import given, settings
from hypothesis import strategies as st
import yaml

from spec_ops.visualizer.prd_sync import (
    PRDSyncEngine,
    compute_sha256,
    get_draft_status,
    save_draft,
)


@st.composite
def prd_draft_edit_strategy(draw):
    """Generates synthetic PRD drafts with varied titles, problems, and outcomes."""
    title = draw(st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")), min_size=3, max_size=40)).strip()
    if not title:
        title = "Default Title"

    persona = draw(st.sampled_from(["Alex", "Jordan", "Morgan", "Riley", "Taylor", "Sasha"]))
    component = draw(st.sampled_from(["core", "billing", "visualizer", "auth", "infra"]))

    problem_paragraphs = draw(
        st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po")),
                min_size=5,
                max_size=60,
            ),
            min_size=1,
            max_size=3,
        )
    )
    problem_text = "\n\n".join(p.strip() for p in problem_paragraphs if p.strip())
    if not problem_text:
        problem_text = "Standard problem statement for property test."

    num_outcomes = draw(st.integers(min_value=1, max_value=6))
    outcomes = []
    for _ in range(num_outcomes):
        outcome_line = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
                min_size=5,
                max_size=50,
            )
        ).strip()
        if outcome_line:
            outcomes.append(outcome_line)
    if not outcomes:
        outcomes = ["User completes operation successfully"]

    frontmatter = (
        f"---\n"
        f"id: PRD-9999\n"
        f"title: {title}\n"
        f"status: Idea\n"
        f"target_persona: {persona}\n"
        f"component: {component}\n"
        f"---\n"
    )

    outcomes_md = "\n".join(f"- {o}" for o in outcomes)
    body = (
        f"# PRD-9999: {title}\n\n"
        f"## Problem Statement\n"
        f"{problem_text}\n\n"
        f"## Checkable Outcomes\n"
        f"{outcomes_md}\n"
    )

    return {
        "title": title,
        "persona": persona,
        "component": component,
        "problem": problem_text,
        "outcomes": outcomes,
        "full_content": frontmatter + "\n" + body,
    }


@settings(max_examples=40, deadline=None)
@given(edits=st.lists(prd_draft_edit_strategy(), min_size=1, max_size=5))
def test_property_sequential_draft_edits_preserve_structure(tmp_path_factory, edits):
    """Asserts any sequence of draft edits preserves content, headers, and YAML AST without corruption."""
    temp_dir = tmp_path_factory.mktemp("prop_seq")
    prd_path = temp_dir / "docs" / "project" / "product" / "idea" / "prd-9999-prop.md"
    prd_path.parent.mkdir(parents=True, exist_ok=True)

    engine = PRDSyncEngine(repo_root=temp_dir, debounce_interval=0.01)
    last_hash: str | None = None

    for edit in edits:
        content = edit["full_content"]
        res = engine.save_draft(prd_path, content, expected_hash=last_hash)

        # Invariant 1: Status is always saved when expected_hash tracks sequential updates
        assert res.status == "saved"
        assert res.revision_digest == compute_sha256(content)
        last_hash = res.revision_digest

        # Invariant 2: Retrieved draft status is bit-exact with saved content
        status = engine.get_draft_status(prd_path)
        assert status["exists"] is True
        assert status["content"] == content
        assert status["digest"] == last_hash

        # Invariant 3: Section headers are preserved without AST corruption
        assert "# PRD-9999:" in status["content"]
        assert "## Problem Statement" in status["content"]
        assert "## Checkable Outcomes" in status["content"]

        # Invariant 4: Checkable outcome bullets are preserved
        for outcome in edit["outcomes"]:
            assert f"- {outcome}" in status["content"]

        # Invariant 5: YAML frontmatter parses cleanly
        parts = status["content"].split("---\n", 2)
        assert len(parts) >= 3
        parsed_yaml = yaml.safe_load(parts[1])
        assert parsed_yaml["id"] == "PRD-9999"
        assert parsed_yaml["target_persona"] == edit["persona"]


@settings(max_examples=35, deadline=None)
@given(
    base_edit=prd_draft_edit_strategy(),
    edit_a=prd_draft_edit_strategy(),
    edit_b=prd_draft_edit_strategy(),
)
def test_property_concurrent_edits_trigger_conflict_preserving_both(
    tmp_path_factory, base_edit, edit_a, edit_b
):
    """Asserts concurrent diverging modifications always produce conflict and preserve both versions."""
    temp_dir = tmp_path_factory.mktemp("prop_conflict")
    prd_path = temp_dir / "prd-conflict-test.md"

    # Save base version
    res_base = save_draft(prd_path, base_edit["full_content"], expected_hash=None)
    assert res_base.status == "saved"
    base_hash = res_base.revision_digest

    # Save edit_a (external author saves first, ensuring change from base)
    content_a = edit_a["full_content"] + "\n\n<!-- external change a -->\n"
    res_a = save_draft(prd_path, content_a, expected_hash=base_hash)
    assert res_a.status == "saved"
    a_hash = res_a.revision_digest

    # Ensure edit_b content differs from edit_a
    content_b = edit_b["full_content"] + "\n\n<!-- client edit b -->\n"

    # Attempt to save edit_b using obsolete base_hash
    res_b = save_draft(prd_path, content_b, expected_hash=base_hash)

    # Invariant 1: Conflict must be detected
    assert res_b.status == "conflict"
    assert res_b.disk_hash == a_hash
    assert res_b.client_hash == compute_sha256(content_b)

    # Invariant 2: Disk content remains edit_a without overwrite
    disk_content = prd_path.read_text(encoding="utf-8")
    assert disk_content == content_a

    # Invariant 3: Client draft is preserved in conflict file
    assert res_b.conflict_path is not None
    conflict_path = Path(res_b.conflict_path)
    assert conflict_path.exists()
    assert conflict_path.read_text(encoding="utf-8") == content_b

    # Invariant 4: diff_summary is present
    assert res_b.diff_summary != ""


@settings(max_examples=30, deadline=None)
@given(edits=st.lists(prd_draft_edit_strategy(), min_size=2, max_size=6))
def test_property_debounced_burst_collapses_to_latest(tmp_path_factory, edits):
    """Asserts a rapid burst of debounced saves collapses into latest edit when flushed."""
    temp_dir = tmp_path_factory.mktemp("prop_burst")
    prd_path = temp_dir / "prd-burst-test.md"

    engine = PRDSyncEngine(repo_root=temp_dir, debounce_interval=10.0)

    for edit in edits:
        engine.debounce_save(prd_path, edit["full_content"])

    # Flush pending writes
    flushed = engine.flush_pending(prd_path)
    assert len(flushed) == 1
    final_res = flushed[0]

    last_edit = edits[-1]
    assert final_res.status == "saved"
    assert final_res.revision_digest == compute_sha256(last_edit["full_content"])

    # File on disk has final edit content
    status = engine.get_draft_status(prd_path)
    assert status["content"] == last_edit["full_content"]
