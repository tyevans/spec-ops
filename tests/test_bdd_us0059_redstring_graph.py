"""Executable BDD step definitions for US-0059: Redstring Knowledge Graph and AST Projection."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.graph.redstring_bridge import RedstringBridge
from spec_ops.scaffold.init import init_project

scenarios("features/us_0059_redstring_graph.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="SpecOpsRedstringBDD")
    return {
        "root": tmp_path,
        "bridge": None,
        "stats": None,
        "store": None,
    }


def _scaffold_project(root: Path) -> None:
    p_docs = root / "docs" / "project"
    (p_docs / "product" / "accepted").mkdir(parents=True, exist_ok=True)
    (p_docs / "user_stories" / "accepted").mkdir(parents=True, exist_ok=True)
    (p_docs / "backlog" / "refined").mkdir(parents=True, exist_ok=True)
    (p_docs / "adrs" / "accepted").mkdir(parents=True, exist_ok=True)

    (p_docs / "user_stories" / "PERSONAS.md").write_text(
        "# Personas\n\n## 1. Alex — The Agentic Systems Architect\n- **Role**: Architect\n- **Pain Points**:\n  - Drift\n",
        encoding="utf-8",
    )
    (p_docs / "product" / "accepted" / "prd-0001-engine.md").write_text(
        "---\nid: '0001'\ntitle: Engine\nstatus: Accepted\n---\n## Checkable Outcomes\n1. Compile sub-50ms\n",
        encoding="utf-8",
    )
    (p_docs / "adrs" / "accepted" / "adr-0011-graph.md").write_text(
        "# ADR-0011: Graph\n\n## Status\nAccepted\n## Context\nContext\n## Decision\nUse redstring\n## Consequences\nFast\n",
        encoding="utf-8",
    )
    (p_docs / "user_stories" / "accepted" / "us-0001-story.md").write_text(
        "---\nid: '0001'\ntitle: Story\nstatus: Accepted\npersona: Alex\ngoverning_prd: PRD-0001\n---\nAs Alex I want speed\n",
        encoding="utf-8",
    )
    (p_docs / "backlog" / "refined" / "0001-base-task.md").write_text(
        "---\nid: '0001'\ntitle: Base Task\nstatus: Refined\ndependencies: []\ngoverning_adrs: [ADR-0011]\ngoverning_prds: [PRD-0001]\ngoverning_stories: [US-0001]\n---\n# Base\n",
        encoding="utf-8",
    )
    (p_docs / "backlog" / "refined" / "0002-dependent-task.md").write_text(
        "---\nid: '0002'\ntitle: Dependent Task\nstatus: Refined\ndependencies: [TASK-0001]\ngoverning_adrs: [ADR-0011]\n---\n# Dependent\n",
        encoding="utf-8",
    )


@given("a project repository with accepted PRDs, tasks, and ADRs")
def project_repo_with_specs(bdd_context: dict[str, Any]) -> None:
    root: Path = bdd_context["root"]
    _scaffold_project(root)


@when("the extractor parses the repository frontmatter")
def extractor_parses_frontmatter(bdd_context: dict[str, Any]) -> None:
    root: Path = bdd_context["root"]
    bridge = RedstringBridge(root)
    store, stats = bridge.compile_sync(force_cold=True)
    bdd_context["bridge"] = bridge
    bdd_context["store"] = store
    bdd_context["stats"] = stats


@then("a Redstring InMemoryGraphStore is populated with typed entities and relationships")
def store_is_populated_with_typed_entities(bdd_context: dict[str, Any]) -> None:
    bridge: RedstringBridge = bdd_context["bridge"]
    store = bdd_context["store"]
    ents = store._entities.get(bridge.tenant_id, {})
    rels = store._relationships.get(bridge.tenant_id, {})

    assert len(ents) >= 5
    assert len(rels) >= 4

    types = {e.entity_type for e in ents.values()}
    assert "PRD" in types
    assert "Task" in types
    assert "ADR" in types
    assert "UserStory" in types
    assert "Persona" in types

    rel_types = {r.relationship_type for r in rels.values()}
    assert "depends_on" in rel_types
    assert "governed_by" in rel_types
    assert "implements" in rel_types
    assert "specifies" in rel_types
    assert "satisfies" in rel_types


@then("graph queries for dependencies return valid topological neighbors")
def graph_queries_return_valid_neighbors(bdd_context: dict[str, Any]) -> None:
    bridge: RedstringBridge = bdd_context["bridge"]

    async def verify() -> None:
        t2 = await bridge.resolve_entity("TASK-0002")
        assert t2 is not None
        neighbors = await bridge.store.neighbors(t2.id, bridge.tenant_id)
        neighbor_names = {n.name for n in neighbors}
        assert "TASK-0001" in neighbor_names or "ADR-0011" in neighbor_names

        reachable, path = await bridge.reach("TASK-0002", "TASK-0001")
        assert reachable is True
        assert path == ["TASK-0002", "TASK-0001"]

    asyncio.run(verify())


@given('a compiled Redstring graph cached to disk at ".specops/cache/graph.json"')
def compiled_graph_cached(bdd_context: dict[str, Any]) -> None:
    root: Path = bdd_context["root"]
    _scaffold_project(root)
    bridge = RedstringBridge(root)
    store, stats = bridge.compile_sync(force_cold=True)
    cache_path = root / ".specops" / "cache" / "graph.json"
    assert cache_path.exists()
    bdd_context["bridge"] = bridge


@when("no markdown files have been modified")
def no_files_modified() -> None:
    pass


@then("compiling the graph loads from the cache snapshot in under 50 milliseconds")
def compiling_loads_under_50ms(bdd_context: dict[str, Any]) -> None:
    root: Path = bdd_context["root"]
    bridge = RedstringBridge(root)
    store, stats = bridge.compile_sync(force_cold=False)
    assert stats["cold"] is False
    assert stats["duration_ms"] < 50.0
    assert stats["cache_hits"] >= 5
    ents = store._entities.get(bridge.tenant_id, {})
    assert len(ents) >= 5
