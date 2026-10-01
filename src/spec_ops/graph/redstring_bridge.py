"""Deterministic AST/frontmatter extractor and redstring knowledge graph bridge.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009, ADR-0011, ADR-0015, ADR-0017.
Enforces zero-LLM deterministic extraction, alias consolidation, reachability,
blast-radius analysis, and content-addressed SHA-256 caching.
Target Bounded Context: graph. File length strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from uuid import UUID

from redstring import (
    Alias,
    Entity,
    ExtractionMethod,
    InMemoryGraphStore,
    Provenance,
    Relationship,
)

from ..core.cache import compute_cache_checksum, compute_content_sha256
from ..core.models import ADR, PRD, Persona, ProjectData, Task, UserStory
from ..core.parser import (
    parse_adr,
    parse_personas,
    parse_prd,
    parse_priority_ranks,
    parse_task,
    parse_user_story,
)

logger = logging.getLogger(__name__)


def make_deterministic_uuid(namespace: str, name: str) -> UUID:
    """Generates a reproducible UUIDv5 for graph entities, relationships, and aliases."""
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, f"specops.{namespace}")
    return uuid.uuid5(ns, name.strip().upper())


def _make_entity(name: str, etype: str, tid: UUID, src: str, desc: str = "", props: dict[str, Any] | None = None) -> Entity:
    prov = Provenance(observed_at=datetime.now(timezone.utc), extraction_method=ExtractionMethod.PATTERN, confidence=1.0, source_id=src or "docs/project")
    return Entity(id=make_deterministic_uuid(etype.lower(), name), tenant_id=tid, name=name, normalized_name=name.lower(), entity_type=etype, description=desc, properties=props or {}, provenance=prov)


def _make_alias(canon_id: UUID, alias_name: str, tid: UUID, reason: str = "alias") -> Alias:
    clean = alias_name.strip()
    return Alias(id=make_deterministic_uuid("alias_rec", f"{canon_id}:{clean}"), tenant_id=tid, canonical_entity_id=canon_id, alias_entity_id=make_deterministic_uuid("alias", clean), alias_name=clean, alias_normalized_name=clean.lower(), merged_at=datetime.now(timezone.utc), merge_reason=reason)


def _make_rel(src: Entity, tgt: Entity, rel_type: str, tid: UUID) -> Relationship:
    return Relationship(id=make_deterministic_uuid("rel", f"{src.name}->{rel_type}->{tgt.name}"), tenant_id=tid, source_entity_id=src.id, target_entity_id=tgt.id, relationship_type=rel_type, source_id="specops-redstring-bridge", confidence=1.0)


class SpecOpsFrontmatterExtractor:
    """Zero-LLM deterministic extractor mapping markdown specifications to redstring models."""

    def __init__(self, tenant_id: UUID | None = None) -> None:
        self.tenant_id = tenant_id or uuid.UUID(int=0)

    def extract(self, data: ProjectData) -> tuple[list[Entity], list[Relationship], list[Alias]]:
        entities: list[Entity] = []
        relationships: list[Relationship] = []
        aliases: list[Alias] = []
        entity_map: dict[str, Entity] = {}

        # 1. Personas & Pain Points
        for p in data.personas:
            src = str(p.file_path or "docs/project/user_stories/PERSONAS.md")
            props = {"name": p.name, "role": p.role, "goals": p.goals, "pain_points": p.pain_points}
            ent = _make_entity(p.id, "Persona", self.tenant_id, src, desc=p.role, props=props)
            entities.append(ent)
            entity_map[p.id.upper()] = ent
            entity_map[p.name.strip().lower()] = ent
            aliases.append(_make_alias(ent.id, p.name, self.tenant_id, "name"))
            if "—" in p.name or "-" in p.name:
                aliases.append(_make_alias(ent.id, re.split(r"[\-—]", p.name)[0].strip(), self.tenant_id, "nickname"))
            for idx, pp in enumerate(p.pain_points):
                pain_id = f"PAIN-{p.id.upper()}-{idx+1:02d}"
                pain_ent = _make_entity(pain_id, "PainPoint", self.tenant_id, src, desc=pp)
                entities.append(pain_ent)
                entity_map[pain_id.upper()] = pain_ent
                relationships.append(_make_rel(ent, pain_ent, "desires", self.tenant_id))

        def register_aliases(ent: Entity, raw_id: str, canon_id: str) -> None:
            aliases.append(_make_alias(ent.id, raw_id, self.tenant_id))
            num = canon_id.split("-")[-1]
            if num.isdigit():
                pfx = canon_id.split("-")[0]
                aliases.extend([
                    _make_alias(ent.id, num, self.tenant_id),
                    _make_alias(ent.id, str(int(num)), self.tenant_id),
                    _make_alias(ent.id, f"{pfx}-{int(num)}", self.tenant_id),
                ])

        # 2. PRDs & Outcomes
        for prd in data.prds:
            cid = f"PRD-{prd.id.split('-')[-1].zfill(4)}" if prd.id.split('-')[-1].isdigit() else prd.id
            src = str(prd.file_path or f"docs/project/product/{prd.id}.md")
            props = {"title": prd.title, "status": prd.status, "target_persona": prd.target_persona}
            ent = _make_entity(cid, "PRD", self.tenant_id, src, desc=prd.title, props=props)
            entities.append(ent)
            entity_map[cid.upper()] = entity_map[prd.id.upper()] = ent
            register_aliases(ent, prd.id, cid)
            for idx, outcome in enumerate(prd.outcomes):
                out_id = f"OUTCOME-{cid}-{idx+1:02d}"
                out_ent = _make_entity(out_id, "Outcome", self.tenant_id, src, desc=outcome)
                entities.append(out_ent)
                entity_map[out_id.upper()] = out_ent
                relationships.append(_make_rel(ent, out_ent, "specifies", self.tenant_id))

        # 3. User Stories
        for s in data.stories:
            cid = f"US-{s.id.split('-')[-1].zfill(4)}" if s.id.split('-')[-1].isdigit() else s.id
            src = str(s.file_path or f"docs/project/user_stories/{s.id}.md")
            props = {"title": s.title, "status": s.status, "persona": s.persona, "feature": s.feature}
            ent = _make_entity(cid, "UserStory", self.tenant_id, src, desc=s.title, props=props)
            entities.append(ent)
            entity_map[cid.upper()] = entity_map[s.id.upper()] = ent
            register_aliases(ent, s.id, cid)

        # 4. Tasks
        for t in data.tasks:
            cid = t.canonical_id
            src = str(t.file_path or f"docs/project/backlog/{cid}.md")
            props = {"title": t.title, "status": t.status, "target_bc": t.target_bc, "claimed_by": t.claimed_by}
            ent = _make_entity(cid, "Task", self.tenant_id, src, desc=t.title, props=props)
            entities.append(ent)
            entity_map[cid.upper()] = entity_map[t.id.upper()] = ent
            register_aliases(ent, t.id, cid)

        # 5. ADRs
        for a in data.adrs:
            cid = f"ADR-{a.id.split('-')[-1].zfill(4)}" if a.id.split('-')[-1].isdigit() else a.id
            src = str(a.file_path or f"docs/project/adrs/{cid}.md")
            props = {"title": a.title, "status": a.status, "domain": a.domain}
            ent = _make_entity(cid, "ADR", self.tenant_id, src, desc=a.title, props=props)
            entities.append(ent)
            entity_map[cid.upper()] = entity_map[a.id.upper()] = ent
            register_aliases(ent, a.id, cid)

        def find_ent(name: str) -> Entity | None:
            if not name:
                return None
            clean = name.strip()
            if ent := (entity_map.get(clean.upper()) or entity_map.get(clean.lower())):
                return ent
            short = re.split(r"[\(—\-]", clean)[0].strip()
            return entity_map.get(short.upper()) or entity_map.get(short.lower())

        def add_rel(s_name: str, t_name: str, rtype: str) -> None:
            s, t = find_ent(s_name), find_ent(t_name)
            if s and t:
                relationships.append(_make_rel(s, t, rtype, self.tenant_id))

        c_id = lambda pfx, raw: f"{pfx}-{raw.split('-')[-1].zfill(4)}" if raw.split('-')[-1].isdigit() else raw
        for p in data.personas:
            for sid in p.story_ids:
                add_rel(p.id, sid, "desires")
        for s in data.stories:
            if s.governing_prd:
                add_rel(s.id, s.governing_prd, "specifies")
                add_rel(s.id, s.governing_prd, "satisfies")
            if s.persona:
                add_rel(s.id, s.persona, "authored_by")
                add_rel(s.persona, s.id, "desires")
        for t in data.tasks:
            for dep in t.dependencies:
                add_rel(t.canonical_id, c_id("TASK", dep), "depends_on")
            for prd_id in t.governing_prds:
                add_rel(t.canonical_id, c_id("PRD", prd_id), "governed_by")
                add_rel(t.canonical_id, c_id("PRD", prd_id), "satisfies")
            for us_id in t.governing_stories:
                add_rel(t.canonical_id, c_id("US", us_id), "implements")
            for adr_id in t.governing_adrs:
                add_rel(t.canonical_id, c_id("ADR", adr_id), "governed_by")
            if t.claimed_by:
                add_rel(t.canonical_id, t.claimed_by, "authored_by")

        return entities, relationships, aliases


class RedstringBridge:
    """High-performance bridge managing InMemoryGraphStore and content-addressed cache."""

    def __init__(self, root_dir: Path, tenant_id: UUID | None = None) -> None:
        self.root_dir = root_dir.resolve()
        self.tenant_id = tenant_id or uuid.UUID(int=0)
        self.store = InMemoryGraphStore()
        self.extractor = SpecOpsFrontmatterExtractor(tenant_id=self.tenant_id)
        self.cache_file = self.root_dir / ".specops" / "cache" / "graph.json"
        self._name_to_id: dict[str, UUID] = {}

    async def load_or_compile(self, force_cold: bool = False) -> tuple[InMemoryGraphStore, dict[str, Any]]:
        t0 = time.perf_counter()
        spec_files = self._discover_spec_files()
        cache_data, is_valid = self._read_cache_file()

        if not force_cold and is_valid and cache_data:
            file_hashes = cache_data.get("file_hashes", {})
            current_hashes = {rel: compute_content_sha256(p.read_bytes()) for rel, (_, p) in spec_files.items()}
            if current_hashes == file_hashes:
                self._populate_store_from_cache(cache_data)
                return self.store, {"cold": False, "duration_ms": (time.perf_counter() - t0) * 1000, "cache_hits": len(spec_files)}

        data = self._parse_all_specs(spec_files)
        entities, relationships, aliases = self.extractor.extract(data)
        self.store._entities[self.tenant_id] = {e.id: e for e in entities}
        self.store._relationships[self.tenant_id] = {r.id: r for r in relationships}
        self.store._aliases[self.tenant_id] = {a.alias_entity_id: a for a in aliases}
        self._index_names(entities, aliases)
        self._write_cache_file(spec_files, entities, relationships, aliases)
        return self.store, {"cold": True, "duration_ms": (time.perf_counter() - t0) * 1000, "total_indexed": len(entities)}

    def compile_sync(self, force_cold: bool = False) -> tuple[InMemoryGraphStore, dict[str, Any]]:
        return asyncio.run(self.load_or_compile(force_cold=force_cold))

    def _index_names(self, entities: Sequence[Entity], aliases: Sequence[Alias]) -> None:
        self._name_to_id.clear()
        for e in entities:
            self._name_to_id[e.name.upper()] = self._name_to_id[e.normalized_name.lower()] = e.id
        for a in aliases:
            if a.alias_name:
                self._name_to_id[a.alias_name.upper()] = a.canonical_entity_id
            if a.alias_normalized_name:
                self._name_to_id[a.alias_normalized_name.lower()] = a.canonical_entity_id

    def _populate_store_from_cache(self, payload: dict[str, Any]) -> None:
        ents = [Entity.model_validate(e) for e in payload.get("redstring_entities", [])]
        rels = [Relationship.model_validate(r) for r in payload.get("redstring_relationships", [])]
        aliases = [Alias.model_validate(a) for a in payload.get("redstring_aliases", [])]
        self.store._entities[self.tenant_id] = {e.id: e for e in ents}
        self.store._relationships[self.tenant_id] = {r.id: r for r in rels}
        self.store._aliases[self.tenant_id] = {a.alias_entity_id: a for a in aliases}
        self._index_names(ents, aliases)

    def _read_cache_file(self) -> tuple[dict[str, Any] | None, bool]:
        if not self.cache_file.exists():
            return None, False
        try:
            payload = json.loads(self.cache_file.read_text(encoding="utf-8"))
            if payload.get("checksum") != compute_cache_checksum(payload):
                logger.warning("Graph cache invalid: rebuilding index from source markdown")
                return None, False
            return payload, True
        except Exception as exc:
            logger.warning("Graph cache invalid: rebuilding index from source markdown (%s)", exc)
            return None, False

    def _write_cache_file(self, files: dict[str, tuple[str, Path]], ents: list[Entity], rels: list[Relationship], aliases: list[Alias]) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        file_hashes = {rel: compute_content_sha256(p.read_bytes()) for rel, (_, p) in files.items()}
        cache_dict: dict[str, Any] = {
            "version": 1,
            "file_hashes": file_hashes,
            "entities": {rel: {"sha256": file_hashes[rel], "canonical_id": p.stem, "data": {}} for rel, (_, p) in files.items()},
            "redstring_entities": [e.model_dump(mode="json") for e in ents],
            "redstring_relationships": [r.model_dump(mode="json") for r in rels],
            "redstring_aliases": [a.model_dump(mode="json") for a in aliases],
            "edges": [{"source": str(r.source_entity_id), "target": str(r.target_entity_id), "rel": r.relationship_type} for r in rels],
        }
        cache_dict["checksum"] = compute_cache_checksum(cache_dict)
        self.cache_file.write_text(json.dumps(cache_dict), encoding="utf-8")

    def _discover_spec_files(self) -> dict[str, tuple[str, Path]]:
        docs_dir = self.root_dir / "docs" / "project"
        found: dict[str, tuple[str, Path]] = {}
        if not docs_dir.exists():
            return found
        p_len = len(str(self.root_dir)) + 1
        for root, _, files in os.walk(str(docs_dir)):
            sub = root[p_len:].split(os.sep)
            etype = "story" if "user_stories" in sub else ("prd" if "product" in sub else ("adr" if "adrs" in sub else ("task" if "backlog" in sub else "")))
            for fn in files:
                if fn.endswith(".md") and not fn.startswith(".") and fn not in ("REGISTRY.md", "PRIORITY.md", "ROADMAP.md", "FEATURE_INVENTORY.md"):
                    full = Path(root) / fn
                    rel = str(full)[p_len:]
                    found[rel] = ("persona" if fn == "PERSONAS.md" else etype, full)
        return found

    def _parse_all_specs(self, spec_files: dict[str, tuple[str, Path]]) -> ProjectData:
        data = ProjectData()
        b_dir = self.root_dir / "docs" / "project" / "backlog"
        ranks = parse_priority_ranks(b_dir) if b_dir.exists() else {}
        handlers = {
            "persona": lambda p: data.personas.extend(parse_personas(p)),
            "prd": lambda p: data.prds.append(parse_prd(p)),
            "story": lambda p: data.stories.append(parse_user_story(p)),
            "task": lambda p: data.tasks.append(parse_task(p, priority_rank=ranks.get(p.stem, 999999))),
            "adr": lambda p: data.adrs.append(parse_adr(p)),
        }
        for _, (etype, path) in spec_files.items():
            if fn := handlers.get(etype):
                fn(path)
        return data

    async def resolve_entity(self, query: str) -> Entity | None:
        clean = query.strip()
        eid = self._name_to_id.get(clean.upper()) or self._name_to_id.get(clean.lower())
        if eid:
            return await self.store.get_entity(eid, self.tenant_id)
        alias_eid = make_deterministic_uuid("alias", clean)
        resolved = await self.store.resolve_entity_ids([alias_eid], self.tenant_id)
        if alias_eid in resolved and resolved[alias_eid] != alias_eid:
            if ent := await self.store.get_entity(resolved[alias_eid], self.tenant_id):
                return ent
        for prefix in ("TASK-", "PRD-", "ADR-", "US-"):
            if clean.isdigit():
                attempt = f"{prefix}{clean.zfill(4)}"
                if attempt in self._name_to_id:
                    return await self.store.get_entity(self._name_to_id[attempt], self.tenant_id)
        return None

    async def reach(self, source_query: str, target_query: str) -> tuple[bool, list[str]]:
        src = await self.resolve_entity(source_query)
        dst = await self.resolve_entity(target_query)
        if not src or not dst:
            return False, []
        if src.id == dst.id:
            return True, [src.name]

        queue: deque[tuple[UUID, list[str]]] = deque([(src.id, [src.name])])
        visited: set[UUID] = {src.id}
        while queue:
            curr_id, path = queue.popleft()
            rels = await self.store.get_relationships(curr_id, self.tenant_id, direction="out")
            for r in rels:
                nxt_id = r.target_entity_id
                nxt_ent = await self.store.get_entity(nxt_id, self.tenant_id)
                nxt_name = nxt_ent.name if nxt_ent else str(nxt_id)
                new_path = path + [nxt_name]
                if nxt_id == dst.id:
                    return True, new_path
                if nxt_id not in visited:
                    visited.add(nxt_id)
                    queue.append((nxt_id, new_path))
        return False, []

    def reach_sync(self, source_query: str, target_query: str) -> tuple[bool, list[str]]:
        return asyncio.run(self.reach(source_query, target_query))

    async def blast_radius(self, entity_query: str) -> dict[str, Any]:
        ent = await self.resolve_entity(entity_query)
        if not ent:
            return {"entity": entity_query, "affected": [], "total": 0, "rating": "LOW", "summary": f"Entity '{entity_query}' not found"}

        visited: set[UUID] = set()
        queue = deque([ent.id])
        while queue:
            curr = queue.popleft()
            rels = await self.store.get_relationships(curr, self.tenant_id, direction="in")
            for r in rels:
                if r.source_entity_id not in visited:
                    visited.add(r.source_entity_id)
                    queue.append(r.source_entity_id)

        affected_ents = await self.store.get_entities(list(visited), self.tenant_id)
        tasks = sorted([e.name for e in affected_ents if e.entity_type == "Task"])
        bcs = sorted(list({e.properties.get("target_bc") for e in affected_ents if e.properties.get("target_bc")}))
        total = len(affected_ents)
        rating = "LOW" if total <= 4 else ("MEDIUM" if total <= 10 else "HIGH")
        tasks_disp = f"[{', '.join(tasks[:3])}{', ...' if len(tasks) > 3 else ''}]"
        summary = (
            f"Blast Radius for {ent.name}:\n"
            f"- {len(tasks)} governing tasks: {tasks_disp}\n"
            f"- {len(bcs)} affected bounded contexts: [{', '.join(bcs)}]\n"
            f"Total Downstream Impact: {rating} ({total} nodes affected)"
        )
        return {"entity": ent.name, "affected": [e.name for e in affected_ents], "tasks": tasks, "bcs": bcs, "total": total, "rating": rating, "summary": summary}
