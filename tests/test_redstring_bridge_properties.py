"""Hypothesis generative property tests for Redstring Relational Knowledge Graph Substrate.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009, ADR-0011, ADR-0015.
Verifies topological path preservation, neighbor set equality, and lossless serialization.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from hypothesis import given, settings, strategies as st
from redstring import Alias, Entity, InMemoryGraphStore, Relationship

from spec_ops.core.models import ProjectData, Task
from spec_ops.graph.redstring_bridge import RedstringBridge, SpecOpsFrontmatterExtractor


@st.composite
def dag_tasks_strategy(draw: st.DrawFn) -> list[Task]:
    """Generates an arbitrary Directed Acyclic Graph (DAG) of task dependencies."""
    num_nodes = draw(st.integers(min_value=3, max_value=12))
    node_ids = [f"TASK-{i:04d}" for i in range(1, num_nodes + 1)]
    tasks: list[Task] = []

    for i, nid in enumerate(node_ids):
        # Choose dependencies strictly from strictly preceding nodes to enforce DAG
        if i == 0:
            deps: list[str] = []
        else:
            candidates = node_ids[:i]
            sample_size = draw(st.integers(min_value=0, max_value=min(3, len(candidates))))
            deps = draw(st.lists(st.sampled_from(candidates), min_size=sample_size, max_size=sample_size, unique=True))

        tasks.append(
            Task(
                id=nid,
                title=f"Generated Task {nid}",
                status="Refined",
                dependencies=deps,
                target_bc="core",
            )
        )
    return tasks


@settings(max_examples=30, deadline=None)
@given(dag_tasks_strategy())
def test_property_dag_serialization_roundtrip_preserves_neighbors_and_paths(tasks: list[Task]) -> None:
    """Asserts that serialization and deserialization of arbitrary DAGs preserves all neighbor sets and topological paths."""
    async def run_property_check() -> None:
        tid = uuid.UUID(int=0)
        data = ProjectData()
        data.tasks.extend(tasks)

        extractor = SpecOpsFrontmatterExtractor(tenant_id=tid)
        entities, relationships, aliases = extractor.extract(data)

        # 1. Build original store
        orig_store = InMemoryGraphStore()
        orig_store._entities[tid] = {e.id: e for e in entities}
        orig_store._relationships[tid] = {r.id: r for r in relationships}
        orig_store._aliases[tid] = {a.alias_entity_id: a for a in aliases}

        # 2. Serialize to JSON payload
        payload = {
            "entities": [e.model_dump(mode="json") for e in entities],
            "relationships": [r.model_dump(mode="json") for r in relationships],
            "aliases": [a.model_dump(mode="json") for a in aliases],
        }
        serialized_json = json.dumps(payload)

        # 3. Deserialize back
        deserialized_data = json.loads(serialized_json)
        deser_ents = [Entity.model_validate(e) for e in deserialized_data["entities"]]
        deser_rels = [Relationship.model_validate(r) for r in deserialized_data["relationships"]]
        deser_aliases = [Alias.model_validate(a) for a in deserialized_data["aliases"]]

        deser_store = InMemoryGraphStore()
        deser_store._entities[tid] = {e.id: e for e in deser_ents}
        deser_store._relationships[tid] = {r.id: r for r in deser_rels}
        deser_store._aliases[tid] = {a.alias_entity_id: a for a in deser_aliases}

        # 4. Invariant: Identical entity counts and IDs
        assert len(deser_ents) == len(entities)
        assert len(deser_rels) == len(relationships)
        assert len(deser_aliases) == len(aliases)

        # 5. Invariant: Exact neighbor set preservation across every node
        for e in entities:
            orig_neighbors = await orig_store.neighbors(e.id, tid)
            deser_neighbors = await deser_store.neighbors(e.id, tid)
            orig_ids = {n.id for n in orig_neighbors}
            deser_ids = {n.id for n in deser_neighbors}
            assert orig_ids == deser_ids

        # 6. Invariant: Topological reachability preservation
        orig_bridge = RedstringBridge(Path("."))
        orig_bridge.store = orig_store
        orig_bridge._index_names(entities, aliases)

        deser_bridge = RedstringBridge(Path("."))
        deser_bridge.store = deser_store
        deser_bridge._index_names(deser_ents, deser_aliases)

        # Test reachability along all declared dependencies
        for t in tasks:
            for dep in t.dependencies:
                orig_reach, orig_path = await orig_bridge.reach(t.canonical_id, dep)
                deser_reach, deser_path = await deser_bridge.reach(t.canonical_id, dep)
                assert orig_reach is True
                assert deser_reach is True
                assert orig_path == deser_path

    asyncio.run(run_property_check())


@settings(max_examples=30, deadline=None)
@given(st.integers(min_value=1, max_value=9999))
def test_property_alias_resolution_invariants(task_num: int) -> None:
    """Asserts that numeric, short, and prefixed identifiers resolve to identical canonical entity."""
    async def run_alias_check() -> None:
        tid = uuid.UUID(int=0)
        data = ProjectData()
        canon_id = f"TASK-{task_num:04d}"
        data.tasks.append(
            Task(
                id=str(task_num),
                title=f"Task {task_num}",
                status="Refined",
            )
        )

        extractor = SpecOpsFrontmatterExtractor(tenant_id=tid)
        entities, relationships, aliases = extractor.extract(data)

        bridge = RedstringBridge(Path("."))
        bridge.store._entities[tid] = {e.id: e for e in entities}
        bridge.store._relationships[tid] = {r.id: r for r in relationships}
        bridge.store._aliases[tid] = {a.alias_entity_id: a for a in aliases}
        bridge._index_names(entities, aliases)

        # Variations to test
        variations = [
            canon_id,
            canon_id.lower(),
            str(task_num),
            f"TASK-{task_num}",
            f"task-{task_num}",
        ]

        expected_ent = await bridge.resolve_entity(canon_id)
        assert expected_ent is not None
        assert expected_ent.name == canon_id

        for var in variations:
            resolved = await bridge.resolve_entity(var)
            assert resolved is not None
            assert resolved.id == expected_ent.id
            assert resolved.name == canon_id

    asyncio.run(run_alias_check())
