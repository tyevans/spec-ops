"""Generative Hypothesis property tests for PRD Studio domain state manager."""

from __future__ import annotations

import string
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.studio import KNOWN_PERSONAS
from spec_ops.prd.studio_state import PRDStudioSessionState, PRDStudioStateManager

SAFE_ALPHABET = string.ascii_letters + string.digits + " -_"
valid_text = st.text(alphabet=SAFE_ALPHABET, min_size=3, max_size=50).map(str.strip).filter(lambda s: len(s) >= 3)
valid_personas = st.sampled_from(sorted(KNOWN_PERSONAS))
valid_outcomes = st.lists(valid_text, min_size=1, max_size=8)


@settings(max_examples=50, deadline=None)
@given(
    title=valid_text,
    persona=valid_personas,
    problem=valid_text,
    outcomes=valid_outcomes,
)
def test_valid_draft_invariants(tmp_path_factory, title: str, persona: str, problem: str, outcomes: list[str]):
    tmp_path = tmp_path_factory.mktemp("hypo_prd")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    state = mgr.new_draft(
        title=title,
        persona=persona,
        problem_statement=problem,
        outcomes=outcomes,
    )
    assert state.is_valid is True
    assert len(state.validation_errors) == 0
    assert state.title == title
    assert state.persona == persona
    assert state.outcomes == outcomes

    # Serialization invariant
    payload = mgr.to_dict()
    assert payload["title"] == title
    assert payload["persona"] == persona
    assert payload["outcomes"] == outcomes
    assert payload["is_valid"] is True


@settings(max_examples=40, deadline=None)
@given(outcomes=st.lists(valid_text, min_size=2, max_size=8, unique=True))
def test_outcome_reordering_permutation_invariants(tmp_path_factory, outcomes: list[str]):
    tmp_path = tmp_path_factory.mktemp("hypo_reorder")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.new_draft(
        title="Valid Title",
        persona="Taylor",
        problem_statement="Valid statement",
        outcomes=outcomes,
    )
    n = len(outcomes)
    # Reverse permutation
    rev_indices = list(range(n - 1, -1, -1))
    assert mgr.reorder_outcomes(rev_indices) is True
    assert mgr.state.outcomes == list(reversed(outcomes))
    assert set(mgr.state.outcomes) == set(outcomes)
    assert len(mgr.state.outcomes) == n


@settings(max_examples=40, deadline=None)
@given(
    initial_outcomes=st.lists(valid_text, min_size=1, max_size=5),
    added_outcome=valid_text,
)
def test_outcome_add_remove_count_invariants(tmp_path_factory, initial_outcomes: list[str], added_outcome: str):
    tmp_path = tmp_path_factory.mktemp("hypo_add_remove")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.new_draft(
        title="Count Invariant",
        persona="Jordan",
        problem_statement="Problem statement",
        outcomes=initial_outcomes,
    )
    base_count = len(mgr.state.outcomes)
    mgr.add_outcome(added_outcome)
    assert len(mgr.state.outcomes) == base_count + 1
    assert mgr.state.outcomes[-1] == added_outcome

    # Remove the added outcome
    removed = mgr.remove_outcome(base_count)
    assert removed is True
    assert len(mgr.state.outcomes) == base_count
