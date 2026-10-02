# How-To: Supersede Architectural Decision Records with Evolution Engine

This guide demonstrates how to supersede legacy Architectural Decision Records (ADRs) with replacement decisions using `spec-ops adr supersede`, governed by [ADR-0001](../project/adrs/accepted/adr-0001-specification-as-code-pmac.md), [ADR-0002](../project/adrs/accepted/adr-0002-modular-source-file-length-guardrails.md), and [ADR-0007](../project/adrs/accepted/adr-0007-domain-driven-design-and-bounded-contexts.md).

---

## Overview

As software architectures evolve, established decisions are replaced or augmented by newer technical standards (e.g. migrating from flat file storage to an embedded database). Manually editing ADRs can lead to broken references, inconsistent status fields, and orphaned task citations.

The ADR Supersession Engine provides:
- Automated scaffolding of new superseding ADRs with decision context and consequences
- In-place status transition of legacy ADRs to `Superseded` with `superseded_by: ADR-YYYY` pointers
- Synchronized updates to `docs/project/adrs/REGISTRY.md`
- Graph cycle prevention ensuring architectural decision lineages remain acyclic Directed Acyclic Graphs (DAGs)
- Backlog impact warnings for tasks that currently cite the superseded decision

---

## Superseding an ADR by Title

To retire an existing ADR and scaffold a new replacement ADR in a single step:

```bash
uv run spec-ops adr supersede --old ADR-0001 --title "SQLite Storage Engine"
```

Output:
```text
✨ Superseded ADR-0001 by ADR-0018
📄 Updated docs/project/adrs/accepted/adr-0001-flat-json.md status to 'Superseded'
📄 Generated docs/project/adrs/accepted/adr-0018-sqlite-storage-engine.md status as 'Accepted'
📋 Synchronized docs/project/adrs/REGISTRY.md
⚠️ Warning: Task TASK-0022 cites superseded ADR-0001; requires architectural re-refinement
```

---

## Superseding with an Existing Proposed ADR

If a proposed ADR has already been authored and is ready to replace an accepted decision:

```bash
uv run spec-ops adr supersede ADR-0001 --by ADR-0015
```

The engine promotes the superseding ADR to `Accepted`, moves it to `docs/project/adrs/accepted/`, marks the old ADR as `Superseded`, and updates the registry table.

---

## Simulating Supersession (Dry Run)

To verify the impact and inspect downstream task citations without modifying any files:

```bash
uv run spec-ops adr supersede --old ADR-0001 --title "PostgreSQL Database Engine" --dry-run
```

Output:
```text
✨ [Simulated] Superseded ADR-0001 by ADR-0019
📄 Updated docs/project/adrs/accepted/adr-0001-flat-json.md status to 'Superseded'
📄 Generated docs/project/adrs/accepted/adr-0019-postgresql-database-engine.md status as 'Accepted'
📋 Synchronized docs/project/adrs/REGISTRY.md
```

---

## Cycle Prevention Guardrail

The supersession engine validates existing and candidate relationships to prevent circular lineages (e.g. `ADR-0001` superseded by `ADR-0002` which is then superseded by `ADR-0001`):

```bash
uv run spec-ops adr supersede ADR-0002 --by ADR-0001
```

Output:
```text
❌ Error: Circular ADR supersession detected: ADR-0001 -> ADR-0002 -> ADR-0001
```

When a cycle is detected, no files are modified and the command exits with code `1`.
