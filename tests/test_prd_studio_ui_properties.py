"""Generative Hypothesis property tests for PRD Studio user interface rendering."""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.studio import KNOWN_PERSONAS
from spec_ops.prd.studio_ui import STUDIO_COMPONENT_STORIES, render_studio_html

SAFE_CHARS = string.ascii_letters + string.digits + " _-"
valid_title = st.text(alphabet=SAFE_CHARS, min_size=3, max_size=40).map(str.strip).filter(lambda s: len(s) >= 3)
valid_personas = st.sampled_from(sorted(KNOWN_PERSONAS))
valid_outcomes = st.lists(
    st.text(alphabet=SAFE_CHARS, min_size=3, max_size=40).map(str.strip).filter(lambda s: len(s) >= 3),
    min_size=1,
    max_size=5,
)


@settings(max_examples=40, deadline=None)
@given(title=valid_title, persona=valid_personas, outcomes=valid_outcomes)
def test_render_studio_html_generative_invariants(title: str, persona: str, outcomes: list[str]):
    seed = {
        "session_id": "studio-prop-test",
        "title": title,
        "persona": persona,
        "component": "prd",
        "problem_statement": "Generated problem statement",
        "outcomes": outcomes,
        "stage": "idea",
        "is_dirty": False,
        "is_valid": True,
    }
    html = render_studio_html(initial_state=seed)

    # Invariants
    assert "<!DOCTYPE html>" in html
    assert "<title>SpecOps PRD Studio</title>" in html
    assert "studio-prop-test" in html
    assert title in html
    assert f'<option value="{persona}">{persona}</option>' in html
    assert 'id="previewContent"' in html
    assert "cdn.jsdelivr.net" not in html
