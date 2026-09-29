"""Knowledge graph service backed by redstring InMemoryGraphStore."""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from redstring import Entity, InMemoryGraphStore, Relationship

from ..core.models import GraphData, GraphEdge, GraphNode, ProjectData
from .extractor import SpecOpsGraphExtractor, make_deterministic_uuid

STATUS_COLORS = {
    "Complete": "#10B981",
    "Refined": "#F59E0B",
    "Proposed": "#8B5CF6",
    "Accepted": "#06B6D4",
    "Shipped": "#10B981",
}

TYPE_COLORS = {
    "Persona": "#EC4899",
    "PRD": "#06B6D4",
    "UserStory": "#3B82F6",
    "Task": "#10B981",
    "ADR": "#8B5CF6",
}


class SpecOpsGraphService:
    """Coordinates the project knowledge graph using redstring."""

    def __init__(self, tenant_id: UUID | None = None, store: InMemoryGraphStore | None = None):
        self.tenant_id = tenant_id or uuid.UUID(int=0)
        self.store = store or InMemoryGraphStore()
        self.extractor = SpecOpsGraphExtractor(tenant_id=self.tenant_id)
        self._name_to_id: dict[str, UUID] = {}

    async def build_from_project_data(self, data: ProjectData) -> None:
        """Extracts entities and relationships from ProjectData and loads into redstring."""
        entities, relationships = self.extractor.extract(data)
        self._name_to_id.clear()

        for ent in entities:
            self._name_to_id[ent.name.upper()] = ent.id
            self._name_to_id[ent.normalized_name] = ent.id

        await self.store.upsert_entities(entities)
        await self.store.upsert_relationships(relationships)

    async def get_entity_by_name(self, name: str) -> Entity | None:
        eid = self._name_to_id.get(name.upper()) or self._name_to_id.get(name.lower())
        if not eid:
            return None
        return await self.store.get_entity(eid, self.tenant_id)

    async def get_neighbors_for_name(self, name: str) -> list[Entity]:
        eid = self._name_to_id.get(name.upper()) or self._name_to_id.get(name.lower())
        if not eid:
            return []
        return await self.store.neighbors(eid, self.tenant_id)

    async def get_all_relationships(self) -> list[Relationship]:
        all_ids = list(self._name_to_id.values())
        if not all_ids:
            return []
        return await self.store.get_relationships_for(all_ids, self.tenant_id)

    async def get_relationships_for_name(self, name: str) -> list[Relationship]:
        eid = self._name_to_id.get(name.upper()) or self._name_to_id.get(name.lower())
        if not eid:
            return []
        return await self.store.get_relationships_for([eid], self.tenant_id)

    async def find_dependency_cycles(self) -> list[list[str]]:
        """Finds any circular dependencies among tasks using Tarjan's SCC or DFS."""
        all_rels = await self.get_all_relationships()
        dep_rels = [r for r in all_rels if r.relationship_type == "depends_on"]

        entities_list = await self.store.get_entities(
            list({r.source_entity_id for r in dep_rels} | {r.target_entity_id for r in dep_rels}),
            self.tenant_id,
        )
        id_to_name = {e.id: e.name for e in entities_list}

        adj: dict[str, list[str]] = {}
        for r in dep_rels:
            u = id_to_name.get(r.source_entity_id, str(r.source_entity_id))
            v = id_to_name.get(r.target_entity_id, str(r.target_entity_id))
            adj.setdefault(u, []).append(v)

        visited: set[str] = set()
        rec_stack: list[str] = []
        cycles: list[list[str]] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    cycle_idx = rec_stack.index(neighbor)
                    cycles.append(rec_stack[cycle_idx:] + [neighbor])
            rec_stack.pop()

        for node in list(adj.keys()):
            if node not in visited:
                dfs(node)

        return cycles

    async def to_graph_data(self) -> GraphData:
        """Converts the redstring GraphStore state into SpecOps GraphData for visualizers."""
        all_rels = await self.get_all_relationships()
        all_eids = list({r.source_entity_id for r in all_rels} | {r.target_entity_id for r in all_rels})
        # If no relationships, still get all entities known
        if not all_eids:
            all_eids = list(self._name_to_id.values())

        entities = await self.store.get_entities(all_eids, self.tenant_id)
        id_to_ent = {e.id: e for e in entities}

        nodes: list[GraphNode] = []
        for ent in entities:
            status = ent.properties.get("status", "")
            color = STATUS_COLORS.get(status, TYPE_COLORS.get(ent.entity_type, "#94A3B8"))
            nodes.append(
                GraphNode(
                    id=ent.name,
                    label=ent.description or ent.name,
                    type=ent.entity_type.lower(),
                    color=color,
                    status=status,
                    role=ent.properties.get("role", ""),
                    domain=ent.properties.get("domain", ""),
                    bc=ent.properties.get("target_bc", ""),
                    metadata=ent.properties,
                )
            )

        edges: list[GraphEdge] = []
        for r in all_rels:
            src = id_to_ent.get(r.source_entity_id)
            tgt = id_to_ent.get(r.target_entity_id)
            if src and tgt:
                edges.append(
                    GraphEdge(
                        source=src.name,
                        target=tgt.name,
                        relation=r.relationship_type,
                        source_type=src.entity_type.lower(),
                        target_type=tgt.entity_type.lower(),
                    )
                )

        return GraphData(nodes=nodes, edges=edges)
