# ADR-0011: Relational Knowledge Graph Substrate with redstring

## Status
Accepted

## Context
PRD-0005 (*Relational Knowledge Graph, Architectural Profiles & Living Reporting*) and US-0059 (*Incremental Relational Graph Caching*) mandate a high-performance relational knowledge graph spanning all project management specifications:
$$\text{Persona} \longrightarrow \text{PRD} \longrightarrow \text{User Story} \longrightarrow \text{Task} \longrightarrow \text{ADR} \longrightarrow \text{Commit}$$

The previous graph implementation in `src/spec_ops/core/graph.py` presented several architectural challenges:
1. **Brittle String & Regex Linking**: Relationships were discovered through ad-hoc regex expressions (`re.findall(r"PRD-\d+", ...)`), easily broken by aliases, typos, or casing variations.
2. **Lack of Entity Consolidation**: SpecOps lacked mechanisms to unify aliases (e.g. resolving persona nicknames or alternative task identifiers) without hardcoded dictionary lookups.
3. **Full Re-scan Overhead**: Lacking an incremental, event-driven graph projection, every CLI call re-parsed all markdown documents from scratch, risking violation of the <50ms compilation goal on large repositories.

`tyevans/redstring` is a knowledge graph library built natively on `eventsource-py`. It provides:
- Core graph value models (`Entity`, `Relationship`, `Alias`).
- In-memory and persistent graph store ports (`GraphStore`, `InMemoryGraphStore`).
- Event-sourced graph synchronization via `GraphProjection` responding to domain events (`DocumentExtracted`, `EntitiesMerged`, `MergeUndone`).
- Fast neighbor traversal, relationship querying, and entity alias resolution.

## Decision
We adopt **`redstring` as the knowledge graphing substrate** for SpecOps:

1. **Direct Event-Sourced Alignment**:
   - Because `redstring` is built on `eventsource-py`, the SpecOps relational graph operates as a pure CQRS read model projection over our domain events.
   - Graph updates are folded through `GraphProjection`, enabling incremental updates without full repository re-scans.

2. **Deterministic AST Extraction (Zero-LLM Requirement for Core SDLC)**:
   - While `redstring` supports LLM-driven entity extraction, SpecOps implements a deterministic `SpecOpsFrontmatterExtractor` for local CLI execution (`spec-ops graph compile`, `spec-ops health`, `spec-ops curate`).
   - This ensures instant, sub-50ms offline execution without requiring external network calls or API keys.

3. **In-Memory GraphStore & Content-Addressed Caching**:
   - SpecOps utilizes `redstring.InMemoryGraphStore` as the primary runtime graph store.
   - Graph snapshots are cached to `.specops/cache/graph.json` keyed by SHA-256 file hashes in accordance with US-0059.

4. **Blast Radius & Topology Traversal**:
   - Reachability queries, orphan detection, and blast radius analysis leverage `redstring`'s graph navigation APIs (`neighbors`, `get_relationships_for`) rather than ad-hoc nested list iterations.

## Consequences
- **Positive**:
  - Seamless architectural cohesion between `eventsource-py` and `redstring`.
  - Enables sub-50ms incremental graph compilation fulfilling PRD-0005 and US-0059.
  - Replaces brittle regexes with formal entity and relationship models.
  - Zero server daemons (operates purely in memory with optional local disk cache).
- **Negative**:
  - Adds `redstring` and its lightweight parsing dependencies (`dateparser`, `jellyfish`) to the project.
  - Requires maintaining the bridge between SpecOps AST models and `redstring.Entity` / `redstring.Relationship`.
