"""Generative Hypothesis property tests for PRD Studio API contracts."""

from __future__ import annotations

import string
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.studio import KNOWN_PERSONAS
from spec_ops.prd.studio_api import dispatch_studio_api_request
from spec_ops.prd.studio_state import PRDStudioStateManager

SAFE_CHARS = string.ascii_letters + string.digits + " _"
valid_text = st.text(alphabet=SAFE_CHARS, min_size=3, max_size=40).map(str.strip).filter(lambda s: len(s) >= 3)
valid_personas = st.sampled_from(sorted(KNOWN_PERSONAS))
valid_outcomes = st.text(alphabet=SAFE_CHARS, min_size=3, max_size=40).map(lambda s: s.strip().lstrip("-")).filter(lambda s: len(s) >= 3)


@settings(max_examples=40, deadline=None)
@given(title=valid_text, persona=valid_personas, outcome=valid_outcomes)
def test_api_field_mutation_property_invariants(tmp_path_factory, title: str, persona: str, outcome: str):
    tmp_path = tmp_path_factory.mktemp("api_prop")
    mgr = PRDStudioStateManager(repo_root=tmp_path)

    # 1. Update title via API
    code_t, res_t = dispatch_studio_api_request(
        mgr, "POST", "/api/studio/draft/update", payload={"field": "title", "value": title}
    )
    assert code_t == 200
    assert res_t["state"]["title"] == title

    # 2. Update persona via API
    code_p, res_p = dispatch_studio_api_request(
        mgr, "POST", "/api/studio/draft/update", payload={"field": "persona", "value": persona}
    )
    assert code_p == 200
    assert res_p["state"]["persona"] == persona

    # 3. Add outcome via API
    code_o, res_o = dispatch_studio_api_request(
        mgr, "POST", "/api/studio/draft/outcome/add", payload={"outcome": outcome}
    )
    assert code_o == 200
    assert res_o["state"]["outcomes"][-1] == outcome

    # 4. State snapshot via GET matches
    code_g, res_g = dispatch_studio_api_request(mgr, "GET", "/api/studio/state")
    assert code_g == 200
    assert res_g["state"]["title"] == title
    assert res_g["state"]["persona"] == persona
    assert res_g["state"]["outcomes"][-1] == outcome
