"""Tests for redstring knowledge graph integration and SpecOpsGraphService."""

from __future__ import annotations

import asyncio
import pytest
from hypothesis import given, strategies as st

from spec_ops.core.models import ADR, PRD, Persona, ProjectData, Task, UserStory
from spec_ops.graph.extractor import SpecOpsGraphExtractor
from spec_ops.graph.service import SpecOpsGraphService


@pytest.fixture
def sample_project_data() -> ProjectData:
    data = ProjectData()
    data.personas.append(
        Persona(
            id="Alex",
            name="Alex Systems Architect",
            role="Architect",
            goals=["Clean boundaries"],
            pain_points=["Monolithic decay"],
            story_ids=["US-0001"],
        )
    )
    data.stories.append(
        UserStory(
            id="US-0001",
            title="Event Sourced Backlog",
            persona="Alex",
            governing_prd="PRD-0001",
        )
    )
    data.prds.append(
        PRD(
            id="PRD-0001",
            title="Core Delivery Engine",
            target_persona="Alex",
            linked_stories=["US-0001"],
            implementing_tasks=["TASK-0001"],
        )
    )
    data.tasks.append(
        Task(
            id="TASK-0001",
            title="Task Decider",
            status="Refined",
            governing_adrs=["ADR-0010"],
            governing_prds=["PRD-0001"],
            governing_stories=["US-0001"],
            target_bc="core",
        )
    )
    data.tasks.append(
        Task(
            id="TASK-0002",
            title="Knowledge Graph",
            status="Proposed",
            dependencies=["TASK-0001"],
            governing_adrs=["ADR-0011"],
            target_bc="graph",
        )
    )
    data.adrs.append(
        ADR(
            id="ADR-0010",
            title="Event Sourcing",
            status="Accepted",
            domain="core",
        )
    )
    data.adrs.append(
        ADR(
            id="ADR-0011",
            title="Knowledge Graph",
            status="Accepted",
            domain="graph",
        )
    )
    return data


def test_extractor_entities_and_relationships(sample_project_data: ProjectData) -> None:
    extractor = SpecOpsGraphExtractor()
    entities, relationships = extractor.extract(sample_project_data)

    names = {e.name for e in entities}
    assert "Alex" in names
    assert "US-0001" in names
    assert "PRD-0001" in names
    assert "TASK-0001" in names
    assert "TASK-0002" in names
    assert "ADR-0010" in names
    assert "ADR-0011" in names

    rel_types = {r.relationship_type for r in relationships}
    assert "desires" in rel_types
    assert "specifies" in rel_types
    assert "implements" in rel_types
    assert "governed_by" in rel_types
    assert "depends_on" in rel_types


def test_graph_service_queries(sample_project_data: ProjectData) -> None:
    async def run_test():
        service = SpecOpsGraphService()
        await service.build_from_project_data(sample_project_data)

        # Entity lookup
        task1 = await service.get_entity_by_name("TASK-0001")
        assert task1 is not None
        assert task1.entity_type == "Task"
        assert task1.properties["status"] == "Refined"

        # Neighbor queries
        neighbors = await service.get_neighbors_for_name("TASK-0001")
        neighbor_names = {n.name for n in neighbors}
        assert "TASK-0002" in neighbor_names or "ADR-0010" in neighbor_names

        # Convert to GraphData for visualizer
        graph_data = await service.to_graph_data()
        assert len(graph_data.nodes) >= 6
        assert len(graph_data.edges) >= 4

    asyncio.run(run_test())


def test_graph_service_cycle_detection(sample_project_data: ProjectData) -> None:
    async def run_test():
        service = SpecOpsGraphService()
        await service.build_from_project_data(sample_project_data)

        # No cycles initially
        cycles = await service.find_dependency_cycles()
        assert cycles == []

        # Introduce circular dependency: TASK-0001 depends on TASK-0002
        sample_project_data.tasks[0].dependencies = ["TASK-0002"]
        await service.build_from_project_data(sample_project_data)

        cycles = await service.find_dependency_cycles()
        assert len(cycles) > 0
        assert any("TASK-0001" in c and "TASK-0002" in c for c in cycles)

    asyncio.run(run_test())


@given(st.lists(st.integers(min_value=1, max_value=20), min_size=2, max_size=10, unique=True))
def test_hypothesis_acyclic_chain_graph(chain: list[int]) -> None:
    async def run_test():
        data = ProjectData()
        for i, val in enumerate(chain):
            deps = [f"TASK-{chain[i-1]:04d}"] if i > 0 else []
            data.tasks.append(
                Task(
                    id=f"TASK-{val:04d}",
                    title=f"Task {val}",
                    status="Refined",
                    dependencies=deps,
                )
            )

        service = SpecOpsGraphService()
        await service.build_from_project_data(data)
        cycles = await service.find_dependency_cycles()
        assert cycles == []

    asyncio.run(run_test())
