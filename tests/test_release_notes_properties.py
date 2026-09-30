"""Generative property-based invariant tests for release notes generator (ADR-0009, US-0049)."""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.models import CommitInfo, Task, UserStory
from spec_ops.prd.release_notes import (
    CapabilityItem,
    PersonaBenefit,
    ReleaseNotesData,
    StorySummary,
    is_chore_or_spike_commit,
    is_chore_or_spike_task,
    milestone_slug,
    render_html_release_notes,
    render_markdown_release_notes,
)

safe_text = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=80)
html_dangerous_text = st.text(
    alphabet=list('abcdefghijklmnopqrstuvwxyz0123456789 <>&"\'/=:;()[]{}'),
    min_size=1,
    max_size=120,
)


@st.composite
def task_strategy(draw: Any) -> Task:
    slice_type = draw(st.sampled_from(["feat", "chore", "spike", "refactor", "internal", "test", "domain", "api", "ui"]))
    tid_num = draw(st.integers(min_value=1, max_value=9999))
    is_spike_id = draw(st.booleans())
    prefix = "SPIKE-" if is_spike_id else "TASK-"
    tid = f"{prefix}{tid_num:04d}"
    
    title_prefix = draw(st.sampled_from(["", "chore: ", "spike: ", "refactor: ", "feat: ", "docs: "]))
    raw_title = draw(st.text(min_size=3, max_size=50))
    title = f"{title_prefix}{raw_title}"
    hypothesis = "Verify sub-50ms" if draw(st.booleans()) and slice_type == "spike" else ""
    
    return Task(
        id=tid,
        title=title,
        status="Complete",
        slice_type=slice_type,
        hypothesis=hypothesis,
    )


@st.composite
def commit_strategy(draw: Any) -> CommitInfo:
    c_hash = draw(st.text(alphabet="0123456789abcdef", min_size=40, max_size=40))
    prefix = draw(st.sampled_from(["chore: ", "spike: ", "refactor: ", "test: ", "feat: ", "fix: "]))
    subject = f"{prefix}{draw(st.text(min_size=3, max_size=50))}"
    slice_trailer = draw(st.sampled_from(["chore", "spike", "refactor", "feat", "fix"]))
    return CommitInfo(
        hash=c_hash,
        author="Taylor",
        date="2026-09-30",
        subject=subject,
        trailers={"SpecOps-Slice": slice_trailer},
    )


@settings(max_examples=100)
@given(st.lists(task_strategy(), min_size=1, max_size=30))
def test_chore_and_spike_tasks_strictly_identified_and_filtered(tasks: list[Task]) -> None:
    """Hypothesis invariant: tasks categorized as chores or spikes are strictly filtered out."""
    for t in tasks:
        is_chore_or_spike = is_chore_or_spike_task(t)
        cid = t.canonical_id.upper()
        slice_t = t.slice_type.lower()
        title_lower = t.title.lower()
        
        if slice_t in ("chore", "spike", "refactor", "internal", "test"):
            assert is_chore_or_spike is True
        elif cid.startswith("SPIKE") or t.hypothesis:
            assert is_chore_or_spike is True
        elif any(kw in title_lower for kw in ["chore", "spike", "refactor"]):
            assert is_chore_or_spike is True


@settings(max_examples=100)
@given(st.lists(commit_strategy(), min_size=1, max_size=30))
def test_chore_and_spike_commits_strictly_identified(commits: list[CommitInfo]) -> None:
    """Hypothesis invariant: chore, spike, and refactor commits are strictly filtered."""
    for c in commits:
        is_cs = is_chore_or_spike_commit(c)
        subj = c.subject.lower()
        trailer = c.trailers.get("SpecOps-Slice", "").lower()
        
        if trailer in ("chore", "spike", "refactor", "test"):
            assert is_cs is True
        elif any(subj.startswith(prefix) for prefix in ["chore:", "spike:", "refactor:", "test:"]):
            assert is_cs is True


@settings(max_examples=100)
@given(
    title=html_dangerous_text,
    desc=html_dangerous_text,
    story_title=html_dangerous_text,
    scenario=html_dangerous_text,
    persona_name=html_dangerous_text,
    benefit=html_dangerous_text,
    branded=st.booleans(),
)
def test_generated_html_contains_zero_unescaped_content(
    title: str,
    desc: str,
    story_title: str,
    scenario: str,
    persona_name: str,
    benefit: str,
    branded: bool,
) -> None:
    """Hypothesis invariant: generated HTML output contains zero unescaped content."""
    notes = ReleaseNotesData(
        milestone_id="M1",
        milestone_title="Milestone M1",
        capabilities=[CapabilityItem(prd_id="PRD-0001", prd_title="Engine", title=title, description=desc)],
        stories=[StorySummary(id="US-0001", title=story_title, scenarios=[scenario])],
        personas=[PersonaBenefit(name=persona_name, role="Architect", benefits=[benefit])],
    )
    rendered = render_html_release_notes(notes, branded=branded)
    
    # Assert zero unescaped script tags
    assert "<script" not in rendered.lower()
    assert "</script" not in rendered.lower()
    
    # Verify allowed HTML tags only
    allowed_tags = {"html", "head", "meta", "title", "body", "div", "span", "h1", "h2", "h3", "h4", "p", "a", "ul", "li"}
    tag_matches = re.findall(r"<([a-zA-Z0-9]+)(?:\s|>)", rendered)
    for tag in tag_matches:
        assert tag.lower() in allowed_tags, f"Unexpected tag found in HTML: <{tag}>"


@settings(max_examples=50)
@given(m_num=st.integers(min_value=1, max_value=999))
def test_milestone_slug_invariance(m_num: int) -> None:
    """Hypothesis invariant: milestone slug consistently resolves M<id> to m<id>."""
    assert milestone_slug(f"M{m_num}") == f"m{m_num}"
    assert milestone_slug(f"Milestone {m_num}") == f"m{m_num}"
    assert milestone_slug(f"Milestone M{m_num}: Foundations") == f"m{m_num}"
