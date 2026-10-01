"""Unit tests for SpecOpsFrontmatterExtractor and RedstringBridge.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009, ADR-0011, ADR-0015, ADR-0017.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import pytest

from spec_ops.core.models import ADR, PRD, Persona, ProjectData, Task, UserStory
from spec_ops.graph.redstring_bridge import RedstringBridge, SpecOpsFrontmatterExtractor


@pytest.fixture
def sample_data() -> ProjectData:
    data = ProjectData()
    data.personas.append(
        Persona(
            id="Alex",
            name="Alex — The Agentic Systems Architect",
            role="Platform Architect",
            pain_points=["Monolithic file sprawl", "Context drift"],
            goals=["Clean boundaries"],
            story_ids=["US-0059"],
        )
    )
    data.prds.append(
        PRD(
            id="PRD-0005",
            title="Relational Knowledge Graph",
            status="Accepted",
            target_persona="Alex",
            outcomes=["Compile sub-50ms", "Zero cycle deadlocks"],
        )
    )
    data.stories.append(
        UserStory(
            id="US-0059",
            title="Incremental Relational Graph Caching",
            status="Accepted",
            persona="Alex",
            governing_prd="PRD-0005",
        )
    )
    data.tasks.append(
        Task(
            id="TASK-0133",
            title="Redstring Knowledge Graph and AST Projection",
            status="Refined",
            dependencies=["TASK-0058"],
            governing_prds=["PRD-0005"],
            governing_stories=["US-0059"],
            governing_adrs=["ADR-0011"],
            claimed_by="Alex",
            target_bc="graph",
        )
    )
    data.tasks.append(
        Task(
            id="TASK-0058",
            title="Tarjan SCC Cycle Resolution",
            status="Complete",
            target_bc="core",
        )
    )
    data.adrs.append(
        ADR(
            id="ADR-0011",
            title="Relational Knowledge Graph Substrate with redstring",
            status="Accepted",
            domain="graph",
        )
    )
    return data


def test_extractor_seven_relationship_types(sample_data: ProjectData) -> None:
    """Verifies that all 7 typed relationships are extracted without LLM reliance."""
    extractor = SpecOpsFrontmatterExtractor()
    entities, relationships, aliases = extractor.extract(sample_data)

    entity_names = {e.name for e in entities}
    assert "Alex" in entity_names
    assert "PAIN-ALEX-01" in entity_names
    assert "PRD-0005" in entity_names
    assert "OUTCOME-PRD-0005-01" in entity_names
    assert "US-0059" in entity_names
    assert "TASK-0133" in entity_names
    assert "TASK-0058" in entity_names
    assert "ADR-0011" in entity_names

    rel_types = {r.relationship_type for r in relationships}
    # All 7 mandatory relationship types
    assert "satisfies" in rel_types
    assert "depends_on" in rel_types
    assert "governed_by" in rel_types
    assert "authored_by" in rel_types
    assert "implements" in rel_types
    assert "specifies" in rel_types
    assert "desires" in rel_types


def test_alias_consolidation(sample_data: ProjectData) -> None:
    """Verifies persona nicknames and alternative task identifiers are consolidated."""
    async def run_test() -> None:
        extractor = SpecOpsFrontmatterExtractor()
        entities, relationships, aliases = extractor.extract(sample_data)

        bridge = RedstringBridge(Path("."))
        tid = bridge.tenant_id
        bridge.store._entities[tid] = {e.id: e for e in entities}
        bridge.store._relationships[tid] = {r.id: r for r in relationships}
        bridge.store._aliases[tid] = {a.alias_entity_id: a for a in aliases}
        bridge._index_names(entities, aliases)

        # 1. Persona nickname consolidation
        e_canon = await bridge.resolve_entity("Alex")
        assert e_canon is not None
        assert e_canon.name == "Alex"

        e_full = await bridge.resolve_entity("Alex — The Agentic Systems Architect")
        assert e_full is not None
        assert e_full.id == e_canon.id

        # 2. Task alias consolidation (TASK-0133, TASK-133, 133, task-0133)
        t_canon = await bridge.resolve_entity("TASK-0133")
        assert t_canon is not None
        assert t_canon.name == "TASK-0133"

        for variant in ["TASK-133", "133", "0133", "task-0133"]:
            t_var = await bridge.resolve_entity(variant)
            assert t_var is not None
            assert t_var.id == t_canon.id

        # 3. PRD and ADR alias consolidation
        prd = await bridge.resolve_entity("PRD-5")
        assert prd is not None
        assert prd.name == "PRD-0005"

        adr = await bridge.resolve_entity("ADR-11")
        assert adr is not None
        assert adr.name == "ADR-0011"

    asyncio.run(run_test())


def test_native_reachability(sample_data: ProjectData) -> None:
    """Verifies reachability pathfinding across multi-hop relationships."""
    async def run_test() -> None:
        extractor = SpecOpsFrontmatterExtractor()
        entities, relationships, aliases = extractor.extract(sample_data)

        bridge = RedstringBridge(Path("."))
        tid = bridge.tenant_id
        bridge.store._entities[tid] = {e.id: e for e in entities}
        bridge.store._relationships[tid] = {r.id: r for r in relationships}
        bridge.store._aliases[tid] = {a.alias_entity_id: a for a in aliases}
        bridge._index_names(entities, aliases)

        # TASK-0133 -> TASK-0058 (depends_on)
        reachable, path = await bridge.reach("TASK-0133", "TASK-0058")
        assert reachable is True
        assert path == ["TASK-0133", "TASK-0058"]

        # TASK-0133 -> PRD-0005 (satisfies / governed_by)
        reachable, path = await bridge.reach("TASK-0133", "PRD-0005")
        assert reachable is True
        assert path == ["TASK-0133", "PRD-0005"]

        # Alex -> US-0059 -> PRD-0005
        reachable, path = await bridge.reach("Alex", "PRD-0005")
        assert reachable is True
        assert "US-0059" in path

        # Same node reachability
        reachable, path = await bridge.reach("TASK-0133", "TASK-0133")
        assert reachable is True
        assert path == ["TASK-0133"]

        # Unreachable query
        reachable, path = await bridge.reach("TASK-0058", "TASK-0133")
        assert reachable is False
        assert path == []

    asyncio.run(run_test())


def test_blast_radius_analysis(sample_data: ProjectData) -> None:
    """Verifies blast radius analysis identifies downstream dependents."""
    async def run_test() -> None:
        extractor = SpecOpsFrontmatterExtractor()
        entities, relationships, aliases = extractor.extract(sample_data)

        bridge = RedstringBridge(Path("."))
        tid = bridge.tenant_id
        bridge.store._entities[tid] = {e.id: e for e in entities}
        bridge.store._relationships[tid] = {r.id: r for r in relationships}
        bridge.store._aliases[tid] = {a.alias_entity_id: a for a in aliases}
        bridge._index_names(entities, aliases)

        # If TASK-0058 changes, TASK-0133 is downstream
        blast = await bridge.blast_radius("TASK-0058")
        assert blast["entity"] == "TASK-0058"
        assert "TASK-0133" in blast["tasks"]
        assert blast["total"] >= 1
        assert "Blast Radius for TASK-0058" in blast["summary"]

        # If ADR-0011 changes, TASK-0133 is downstream
        blast_adr = await bridge.blast_radius("ADR-0011")
        assert "TASK-0133" in blast_adr["tasks"]

    asyncio.run(run_test())


def test_cache_roundtrip_and_corruption_recovery(tmp_path: Path) -> None:
    """Verifies content-addressed cache storage, warm loading, and corruption recovery."""
    p_docs = tmp_path / "docs" / "project"
    (p_docs / "product" / "accepted").mkdir(parents=True, exist_ok=True)
    (p_docs / "user_stories" / "accepted").mkdir(parents=True, exist_ok=True)
    (p_docs / "backlog" / "refined").mkdir(parents=True, exist_ok=True)
    (p_docs / "adrs" / "accepted").mkdir(parents=True, exist_ok=True)

    (p_docs / "user_stories" / "PERSONAS.md").write_text("# Personas\n## 1. Alex\n- **Role**: Arch\n", encoding="utf-8")
    (p_docs / "product" / "accepted" / "prd-0001.md").write_text("---\nid: '0001'\ntitle: P1\nstatus: Accepted\n---\n## Checkable Outcomes\n1. Outcome\n", encoding="utf-8")
    (p_docs / "backlog" / "refined" / "0001-t.md").write_text("---\nid: '0001'\ntitle: T1\nstatus: Refined\n---\n# T\n", encoding="utf-8")

    bridge = RedstringBridge(tmp_path)

    # 1. Cold compile
    store1, stats1 = bridge.compile_sync(force_cold=True)
    assert stats1["cold"] is True
    cache_file = tmp_path / ".specops" / "cache" / "graph.json"
    assert cache_file.exists()

    # 2. Warm compile (<10ms)
    store2, stats2 = bridge.compile_sync(force_cold=False)
    assert stats2["cold"] is False
    assert stats2["duration_ms"] < 20.0
    assert len(store2._entities[bridge.tenant_id]) == len(store1._entities[bridge.tenant_id])

    # 3. Corrupt cache recovery
    cache_file.write_text('{"version": 1, "corrupt": true, "checksum": "invalid"}', encoding="utf-8")
    store3, stats3 = bridge.compile_sync(force_cold=False)
    assert stats3["cold"] is True
    assert len(store3._entities[bridge.tenant_id]) >= 3
