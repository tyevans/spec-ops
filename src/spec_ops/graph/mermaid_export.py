"""Relational knowledge graph subgraph exporter and Mermaid / Graphviz diagram generator.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0011, ADR-0015, and PRD-0005.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any, Sequence
from uuid import UUID

from redstring import Entity, Relationship

from ..config.models import SpecOpsConfig
from .redstring_bridge import RedstringBridge

STYLE_CLASSES: dict[str, str] = {
    "prd": "fill:#4a90e2,stroke:#1d5bbf,color:#fff",
    "userstory": "fill:#7ed321,stroke:#417505,color:#fff",
    "task": "fill:#f5a623,stroke:#bd7101,color:#fff",
    "adr": "fill:#9013fe,stroke:#600ba4,color:#fff",
    "persona": "fill:#50e3c2,stroke:#26937c,color:#000",
    "outcome": "fill:#f8e71c,stroke:#c4b407,color:#000",
    "painpoint": "fill:#e74c3c,stroke:#c0392b,color:#fff",
}


def sanitize_node_id(name: str) -> str:
    """Sanitizes an entity name into a valid alphanumeric identifier for graph diagram formats."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip())
    if not clean or clean[0].isdigit():
        clean = f"node_{clean}"
    return clean


def sanitize_label(label: str) -> str:
    """Escapes problematic quotation marks and bracket characters for diagram engines."""
    clean = label.replace('"', "'")
    clean = clean.replace("[", "(").replace("]", ")")
    clean = clean.replace("{", "(").replace("}", ")")
    return clean.strip()


async def traverse_subgraph_async(
    bridge: RedstringBridge,
    root_query: str | None = None,
    depth: int = 2,
) -> tuple[list[Entity], list[Relationship]]:
    """Traverses the redstring knowledge graph up to a depth limit, returning entities and edges."""
    tenant_id = bridge.tenant_id
    all_ents = list(bridge.store._entities.get(tenant_id, {}).values())
    all_rels = list(bridge.store._relationships.get(tenant_id, {}).values())

    if not root_query:
        return all_ents, all_rels

    root_ent = await bridge.resolve_entity(root_query)
    if not root_ent:
        return [], []

    ent_by_id: dict[UUID, Entity] = {e.id: e for e in all_ents}
    visited_ents: set[UUID] = {root_ent.id}
    current_level: set[UUID] = {root_ent.id}
    if depth <= 0:
        return [root_ent], []

    for _ in range(depth):
        next_level: set[UUID] = set()
        for rel in all_rels:
            if rel.source_entity_id in current_level:
                tgt = rel.target_entity_id
                if tgt in ent_by_id and tgt not in visited_ents:
                    visited_ents.add(tgt)
                    next_level.add(tgt)
            elif rel.target_entity_id in current_level:
                src = rel.source_entity_id
                if src in ent_by_id and src not in visited_ents:
                    visited_ents.add(src)
                    next_level.add(src)
        current_level = next_level
        if not current_level:
            break

    sub_ents = [ent_by_id[eid] for eid in visited_ents if eid in ent_by_id]
    sub_rels = [
        r
        for r in all_rels
        if r.source_entity_id in visited_ents and r.target_entity_id in visited_ents
    ]
    return sub_ents, sub_rels


def traverse_subgraph(
    bridge: RedstringBridge,
    root_query: str | None = None,
    depth: int = 2,
) -> tuple[list[Entity], list[Relationship]]:
    """Synchronous runner for knowledge graph subgraph traversal."""
    return asyncio.run(traverse_subgraph_async(bridge, root_query=root_query, depth=depth))


def generate_mermaid(
    entities: Sequence[Entity],
    relationships: Sequence[Relationship],
    direction: str = "TD",
) -> str:
    """Renders entities and relationships into valid Mermaid flowchart syntax."""
    lines: list[str] = [f"flowchart {direction.upper()}"]

    for cat, style in STYLE_CLASSES.items():
        lines.append(f"    classDef {cat} {style};")

    ent_map = {e.id: e for e in entities}
    node_id_map: dict[UUID, str] = {e.id: sanitize_node_id(e.name) for e in entities}

    for ent in sorted(entities, key=lambda x: x.name):
        nid = node_id_map[ent.id]
        raw_title = ent.properties.get("title") or ent.description or ent.name
        label = sanitize_label(f"{ent.name}: {raw_title}" if raw_title and raw_title != ent.name else ent.name)
        lines.append(f'    {nid}["{label}"]')
        cat = ent.entity_type.lower()
        if cat in STYLE_CLASSES:
            lines.append(f"    class {nid} {cat};")

    for rel in sorted(relationships, key=lambda r: (str(r.source_entity_id), str(r.target_entity_id))):
        src_id = node_id_map.get(rel.source_entity_id)
        tgt_id = node_id_map.get(rel.target_entity_id)
        if src_id and tgt_id:
            rel_label = sanitize_label(rel.relationship_type)
            lines.append(f"    {src_id} -->|{rel_label}| {tgt_id}")

    return "\n".join(lines) + "\n"


def generate_dot(
    entities: Sequence[Entity],
    relationships: Sequence[Relationship],
    direction: str = "TD",
) -> str:
    """Renders entities and relationships into Graphviz DOT syntax."""
    lines: list[str] = [
        "digraph G {",
        f'    rankdir="{direction.upper()}";',
        '    node [shape="box", style="rounded,filled", fontname="sans-serif"];',
    ]

    node_id_map: dict[UUID, str] = {e.id: sanitize_node_id(e.name) for e in entities}

    for ent in sorted(entities, key=lambda x: x.name):
        nid = node_id_map[ent.id]
        raw_title = ent.properties.get("title") or ent.description or ent.name
        label = sanitize_label(f"{ent.name}: {raw_title}" if raw_title and raw_title != ent.name else ent.name)
        lines.append(f'    {nid} [label="{label}"];')

    for rel in sorted(relationships, key=lambda r: (str(r.source_entity_id), str(r.target_entity_id))):
        src_id = node_id_map.get(rel.source_entity_id)
        tgt_id = node_id_map.get(rel.target_entity_id)
        if src_id and tgt_id:
            rel_label = sanitize_label(rel.relationship_type)
            lines.append(f'    {src_id} -> {tgt_id} [label="{rel_label}"];')

    lines.append("}")
    return "\n".join(lines) + "\n"


def export_diagram(
    root_dir: Path | str,
    root_entity: str | None = None,
    depth: int = 2,
    format_type: str = "mermaid",
    direction: str = "TD",
) -> str:
    """Loads relational graph bridge and generates diagram syntax."""
    bridge = RedstringBridge(root_dir=Path(root_dir))
    bridge.compile_sync()
    ents, rels = traverse_subgraph(bridge, root_query=root_entity, depth=depth)

    fmt = format_type.strip().lower()
    if fmt == "dot":
        return generate_dot(ents, rels, direction=direction)
    return generate_mermaid(ents, rels, direction=direction)


def handle_mermaid_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Dispatches 'spec-ops graph mermaid' CLI command."""
    root_entity = getattr(args, "root", None)
    raw_depth = getattr(args, "depth", 2)
    depth = 2 if raw_depth is None else int(raw_depth)
    fmt = getattr(args, "format", "mermaid") or "mermaid"
    direction = getattr(args, "direction", "TD") or "TD"
    output_path = getattr(args, "output", None)

    try:
        content = export_diagram(
            root_dir=config.root_dir,
            root_entity=root_entity,
            depth=depth,
            format_type=fmt,
            direction=direction,
        )
    except Exception as exc:
        print(f"❌ Failed exporting graph diagram: {exc}", file=sys.stderr)
        return 1

    if output_path:
        out = Path(output_path)
        if not out.is_absolute():
            out = config.root_dir / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"✨ Exported {fmt.capitalize()} diagram to {out}")
    else:
        print(content, end="")

    return 0
