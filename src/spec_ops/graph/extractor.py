"""Deterministic AST and frontmatter extractor for redstring knowledge graphs."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from redstring import Entity, ExtractionMethod, Provenance, Relationship

from ..core.models import ProjectData


def make_deterministic_uuid(namespace: str, name: str) -> UUID:
    """Generates a reproducible UUIDv5 for graph entities and relationships."""
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, f"specops.{namespace}")
    return uuid.uuid5(ns, name.strip().upper())


class SpecOpsGraphExtractor:
    """Transforms structured ProjectData specifications into redstring entities and relationships."""

    def __init__(self, tenant_id: UUID | None = None):
        self.tenant_id = tenant_id or uuid.UUID(int=0)

    def extract(self, data: ProjectData) -> tuple[list[Entity], list[Relationship]]:
        entities: list[Entity] = []
        relationships: list[Relationship] = []
        entity_map: dict[str, Entity] = {}

        now = datetime.now(timezone.utc)

        def make_prov(source_path: str) -> Provenance:
            return Provenance(
                observed_at=now,
                extraction_method=ExtractionMethod.PATTERN,
                confidence=1.0,
                source_id=source_path or "docs/project",
            )

        # 1. Personas
        for p in data.personas:
            eid = make_deterministic_uuid("persona", p.id)
            source_file = str(p.file_path) if p.file_path else "docs/project/user_stories/PERSONAS.md"
            ent = Entity(
                id=eid,
                tenant_id=self.tenant_id,
                name=p.id,
                normalized_name=p.name.strip().lower(),
                entity_type="Persona",
                description=p.role,
                properties={
                    "name": p.name,
                    "role": p.role,
                    "goals": p.goals,
                    "pain_points": p.pain_points,
                },
                provenance=make_prov(source_file),
            )
            entities.append(ent)
            entity_map[p.id.upper()] = ent
            entity_map[p.name.strip().lower()] = ent

        # 2. PRDs
        for prd in data.prds:
            cid = f"PRD-{prd.id.split('-')[-1].zfill(4)}" if prd.id.split('-')[-1].isdigit() else prd.id
            eid = make_deterministic_uuid("prd", cid)
            source_file = str(prd.file_path) if prd.file_path else f"docs/project/product/{prd.id}.md"
            ent = Entity(
                id=eid,
                tenant_id=self.tenant_id,
                name=cid,
                normalized_name=cid.lower(),
                entity_type="PRD",
                description=prd.title,
                properties={
                    "title": prd.title,
                    "status": prd.status,
                    "target_persona": prd.target_persona,
                },
                provenance=make_prov(source_file),
            )
            entities.append(ent)
            entity_map[cid.upper()] = ent
            entity_map[prd.id.upper()] = ent

        # 3. User Stories
        for s in data.stories:
            cid = f"US-{s.id.split('-')[-1].zfill(4)}" if s.id.split('-')[-1].isdigit() else s.id
            eid = make_deterministic_uuid("story", cid)
            source_file = str(s.file_path) if s.file_path else f"docs/project/user_stories/{s.id}.md"
            ent = Entity(
                id=eid,
                tenant_id=self.tenant_id,
                name=cid,
                normalized_name=cid.lower(),
                entity_type="UserStory",
                description=s.title,
                properties={
                    "title": s.title,
                    "status": s.status,
                    "persona": s.persona,
                    "feature": s.feature,
                },
                provenance=make_prov(source_file),
            )
            entities.append(ent)
            entity_map[cid.upper()] = ent
            entity_map[s.id.upper()] = ent

        # 4. Tasks
        for t in data.tasks:
            cid = t.canonical_id
            eid = make_deterministic_uuid("task", cid)
            source_file = str(t.file_path) if t.file_path else f"docs/project/backlog/{cid}.md"
            ent = Entity(
                id=eid,
                tenant_id=self.tenant_id,
                name=cid,
                normalized_name=cid.lower(),
                entity_type="Task",
                description=t.title,
                properties={
                    "title": t.title,
                    "status": t.status,
                    "target_bc": t.target_bc,
                    "priority_rank": t.priority_rank,
                    "claimed_by": t.claimed_by,
                },
                provenance=make_prov(source_file),
            )
            entities.append(ent)
            entity_map[cid.upper()] = ent
            entity_map[t.id.upper()] = ent

        # 5. ADRs
        for a in data.adrs:
            cid = f"ADR-{a.id.split('-')[-1].zfill(4)}" if a.id.split('-')[-1].isdigit() else a.id
            eid = make_deterministic_uuid("adr", cid)
            source_file = str(a.file_path) if a.file_path else f"docs/project/adrs/{cid}.md"
            ent = Entity(
                id=eid,
                tenant_id=self.tenant_id,
                name=cid,
                normalized_name=cid.lower(),
                entity_type="ADR",
                description=a.title,
                properties={
                    "title": a.title,
                    "status": a.status,
                    "domain": a.domain,
                },
                provenance=make_prov(source_file),
            )
            entities.append(ent)
            entity_map[cid.upper()] = ent
            entity_map[a.id.upper()] = ent

        # Helper to create relationship
        def add_rel(source_name: str, target_name: str, rel_type: str, source_path: str = "") -> None:
            s_ent = entity_map.get(source_name.upper()) or entity_map.get(source_name.lower())
            t_ent = entity_map.get(target_name.upper()) or entity_map.get(target_name.lower())
            if not s_ent or not t_ent:
                return
            rid = make_deterministic_uuid("rel", f"{s_ent.name}->{rel_type}->{t_ent.name}")
            relationships.append(
                Relationship(
                    id=rid,
                    tenant_id=self.tenant_id,
                    source_entity_id=s_ent.id,
                    target_entity_id=t_ent.id,
                    relationship_type=rel_type,
                    source_id=source_path or "specops-extractor",
                    confidence=1.0,
                )
            )

        # Linking: Persona desires Story
        for p in data.personas:
            for sid in p.story_ids:
                add_rel(p.id, sid, "desires")

        # Linking: Story specifies PRD
        for s in data.stories:
            if s.governing_prd:
                add_rel(s.id, s.governing_prd, "specifies")

        # Linking: Task implements / governed_by
        for t in data.tasks:
            for dep in t.dependencies:
                dep_id = f"TASK-{dep.split('-')[-1].zfill(4)}" if dep.split('-')[-1].isdigit() else dep
                add_rel(t.canonical_id, dep_id, "depends_on")

            for prd_id in t.governing_prds:
                c_prd = f"PRD-{prd_id.split('-')[-1].zfill(4)}" if prd_id.split('-')[-1].isdigit() else prd_id
                add_rel(t.canonical_id, c_prd, "governed_by")

            for us_id in t.governing_stories:
                c_us = f"US-{us_id.split('-')[-1].zfill(4)}" if us_id.split('-')[-1].isdigit() else us_id
                add_rel(t.canonical_id, c_us, "implements")

            for adr_id in t.governing_adrs:
                c_adr = f"ADR-{adr_id.split('-')[-1].zfill(4)}" if adr_id.split('-')[-1].isdigit() else adr_id
                add_rel(t.canonical_id, c_adr, "governed_by")

        return entities, relationships
