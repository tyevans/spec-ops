"""Hypothesis property tests and unit tests for URL hash routing and state synchronization (ADR-0009)."""
from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

from spec_ops.visualizer.tour_script import (
    DEFAULT_TOUR_STEPS,
    generate_uat_receipt,
    get_tour_steps,
)
from spec_ops.visualizer.url_router_script import (
    VisualizerUrlState,
    parse_url_hash,
    serialize_url_hash,
)

SAFE_CHARS = string.ascii_letters + string.digits + "_-"


@st.composite
def visualizer_states(draw):
    tab = draw(
        st.sampled_from(
            ["graph", "matrix", "gantt", "kanban", "prds", "adrs", "personas", "lead", "security"]
        )
    )
    query = draw(st.text(alphabet=SAFE_CHARS, min_size=0, max_size=20))
    status = draw(st.sampled_from(["all", "Complete", "Refined", "Proposed"]))
    bc = draw(
        st.one_of(
            st.just("all"),
            st.text(alphabet=SAFE_CHARS, min_size=1, max_size=15),
        )
    )
    hide_done = draw(st.booleans())
    group_by = draw(st.sampled_from(["release", "bc"]))
    linked = draw(st.one_of(st.none(), st.text(alphabet=SAFE_CHARS, min_size=1, max_size=15)))
    entity = draw(st.one_of(st.none(), st.text(alphabet=SAFE_CHARS, min_size=1, max_size=15)))
    focus = draw(st.one_of(st.none(), st.text(alphabet=SAFE_CHARS, min_size=1, max_size=15)))
    persona = draw(
        st.one_of(
            st.just("all"),
            st.text(alphabet=SAFE_CHARS, min_size=1, max_size=15),
        )
    )
    milestone = draw(
        st.one_of(
            st.just("all"),
            st.text(alphabet=SAFE_CHARS, min_size=1, max_size=15),
        )
    )
    types_list = draw(
        st.one_of(
            st.none(),
            st.lists(
                st.sampled_from(["task", "story", "prd", "adr", "persona", "bc"]),
                min_size=1,
                max_size=3,
                unique=True,
            ),
        )
    )
    hops = draw(st.sampled_from(["all", "1", "2"]))
    preset = draw(
        st.one_of(
            st.none(),
            st.sampled_from(["default", "bc", "delivery", "architecture", "flow"]),
        )
    )

    return VisualizerUrlState(
        tab=tab,
        query=query,
        status=status,
        bc=bc,
        hide_done=hide_done,
        group_by=group_by,
        linked=linked,
        entity=entity,
        focus=focus,
        persona=persona,
        milestone=milestone,
        types=types_list,
        hops=hops,
        preset=preset,
    )


@settings(max_examples=50, deadline=None)
@given(state=visualizer_states())
def test_hypothesis_url_hash_state_isomorphism(state: VisualizerUrlState):
    """Generative property invariant (ADR-0009): Round-trip parsing and serialization produces identical hash strings."""
    # 1. Serialize state
    serialized = serialize_url_hash(state)
    assert serialized.startswith("#tab=")

    # 2. Parse back
    parsed = parse_url_hash(serialized)

    # 3. Re-serialize
    re_serialized = serialize_url_hash(parsed)

    # Round-trip isomorphism invariant
    assert re_serialized == serialized

    # State equality invariant
    parsed_again = parse_url_hash(re_serialized)
    assert parsed_again == parsed


# ============================================================================
# Mutation-Killing Unit Tests for url_router_script.py
# ============================================================================


def test_parse_url_hash_empty_and_root():
    """Verify parsing empty, root, and single slash hashes."""
    s1 = parse_url_hash("")
    assert s1.tab == "graph"
    assert s1.entity is None

    s2 = parse_url_hash("#")
    assert s2.tab == "graph"
    assert s2.entity is None

    s3 = parse_url_hash("#/")
    assert s3.tab == "graph"
    assert s3.entity is None


def test_parse_url_hash_shorthand_entity():
    """Verify single entity shorthand hashes (e.g. #TASK-0012)."""
    s = parse_url_hash("#TASK-0012")
    assert s.tab == "graph"
    assert s.entity == "TASK-0012"

    s2 = parse_url_hash("ADR-0007")
    assert s2.tab == "graph"
    assert s2.entity == "ADR-0007"


def test_parse_url_hash_tab_normalization():
    """Verify tab parameter validation and aliases."""
    # Canvas alias to graph
    s = parse_url_hash("#tab=canvas")
    assert s.tab == "graph"

    s2 = parse_url_hash("#tab=CANVAS")
    assert s2.tab == "graph"

    # All valid tabs
    for t in ["graph", "matrix", "gantt", "kanban", "prds", "adrs", "personas", "lead", "security"]:
        assert parse_url_hash(f"#tab={t}").tab == t
        assert parse_url_hash(f"#tab={t.upper()}").tab == t

    # Invalid tab falls back to graph
    assert parse_url_hash("#tab=invalid_tab").tab == "graph"


def test_parse_url_hash_queries_and_filters():
    """Verify q, query, and compound filter parsing."""
    s1 = parse_url_hash("#q=searchterm")
    assert s1.query == "searchterm"

    s2 = parse_url_hash("#query=altsearch")
    assert s2.query == "altsearch"

    # Compound filter: bc
    s_bc = parse_url_hash("#filter=bc:core")
    assert s_bc.bc == "core"

    # Compound filter: status
    assert parse_url_hash("#filter=status:complete").status == "Complete"
    assert parse_url_hash("#filter=status:refined").status == "Refined"
    assert parse_url_hash("#filter=status:proposed").status == "Proposed"

    # Compound filter: persona
    assert parse_url_hash("#filter=persona:taylor").persona == "taylor"

    # Plain text filter acts as query
    assert parse_url_hash("#filter=freeform_query").query == "freeform_query"


def test_parse_url_hash_status_and_hidedone_and_groupby():
    """Verify status casing, hideDone boolean, and groupBy variations."""
    assert parse_url_hash("#status=Complete").status == "Complete"
    assert parse_url_hash("#status=refined").status == "Refined"
    assert parse_url_hash("#status=PROPOSED").status == "Proposed"
    assert parse_url_hash("#status=other").status == "all"

    # hideDone
    assert parse_url_hash("#hideDone=true").hide_done is True
    assert parse_url_hash("#hideDone=1").hide_done is True
    assert parse_url_hash("#hide_done=true").hide_done is True
    assert parse_url_hash("#hideDone=false").hide_done is False

    # groupBy
    assert parse_url_hash("#groupBy=bc").group_by == "bc"
    assert parse_url_hash("#group_by=bc").group_by == "bc"
    assert parse_url_hash("#groupBy=release").group_by == "release"
    assert parse_url_hash("#groupBy=unknown").group_by == "release"


def test_parse_url_hash_types_hops_preset_focus():
    """Verify types, hops, preset, and focus / entity associations."""
    s = parse_url_hash("#types=task,story,PRD&hops=1&preset=delivery&focus=TASK-0013")
    assert s.types == ["task", "story", "prd"]
    assert s.hops == "1"
    assert s.preset == "delivery"
    assert s.focus == "TASK-0013"
    assert s.entity is None

    # Distinct focus and entity
    s2 = parse_url_hash("#entity=TASK-0001&focus=TASK-0002")
    assert s2.entity == "TASK-0001"
    assert s2.focus == "TASK-0002"

    h = serialize_url_hash(s2)
    assert "entity=TASK-0001" in h
    assert "focus=TASK-0002" in h


def test_serialize_url_hash_optional_fields():
    """Verify selective serialization of optional fields."""
    st = VisualizerUrlState(
        tab="matrix",
        query="testq",
        status="Refined",
        bc="core",
        hide_done=True,
        group_by="bc",
        persona="Taylor",
        milestone="M1",
        linked="PRD-0001",
        types=["task", "story"],
        hops="2",
        preset="bc",
        entity="TASK-0099",
    )
    res = serialize_url_hash(st)
    assert "tab=matrix" in res
    assert "q=testq" in res
    assert "status=Refined" in res
    assert "bc=core" in res
    assert "hideDone=true" in res
    assert "groupBy=bc" in res
    assert "persona=Taylor" in res
    assert "milestone=M1" in res
    assert "linked=PRD-0001" in res
    assert "types=task%2Cstory" in res or "types=task,story" in res
    assert "hops=2" in res
    assert "preset=bc" in res
    assert "entity=TASK-0099" in res


# ============================================================================
# Tour Script Unit Tests
# ============================================================================


def test_tour_steps_structure():
    """Verify tour steps definition."""
    steps = get_tour_steps()
    assert len(steps) == 4
    assert len(DEFAULT_TOUR_STEPS) == 4
    for i, s in enumerate(steps, 1):
        assert s["step"] == i
        assert len(s["title"]) > 0
        assert len(s["description"]) > 0
        assert s["selector"].startswith("#")


def test_generate_uat_receipt_cryptographic_hash():
    """Verify UAT receipt generation, deterministic SHA-256 digest, and signature block."""
    scenarios = ["Scenario: Alpha", "Scenario: Beta"]
    commits = ["a1b2c3d", "e4f5g6h"]
    receipt = generate_uat_receipt(
        feature_id="FEAT-VIS-07",
        prd_id="PRD-0005",
        scenarios=scenarios,
        commits=commits,
        timestamp="2026-09-29T22:30:00Z",
    )

    assert receipt["feature_id"] == "FEAT-VIS-07"
    assert receipt["prd_id"] == "PRD-0005"
    assert len(receipt["hash"]) == 64
    assert "FEAT-VIS-07" in receipt["markdown"]
    assert "PRD-0005" in receipt["markdown"]
    assert "Scenario: Alpha" in receipt["markdown"]
    assert "Scenario: Beta" in receipt["markdown"]
    assert "a1b2c3d" in receipt["markdown"]
    assert "Dual Sign-Off Signatures" in receipt["markdown"]
    assert "Product Sign-Off" in receipt["markdown"]
    assert "Security Sign-Off" in receipt["markdown"]

    # Invariant: identical inputs produce identical hash
    receipt2 = generate_uat_receipt(
        feature_id="FEAT-VIS-07",
        prd_id="PRD-0005",
        scenarios=scenarios,
        commits=commits,
        timestamp="2026-09-29T22:30:00Z",
    )
    assert receipt2["hash"] == receipt["hash"]

    # Invariant: empty scenarios and commits default gracefully
    r_empty = generate_uat_receipt(
        feature_id="FEAT-001",
        prd_id="PRD-001",
        scenarios=[],
    )
    assert len(r_empty["hash"]) == 64
    assert "VERIFIED" in r_empty["markdown"]
