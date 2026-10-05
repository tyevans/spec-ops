# How-To: Incrementally Amend Architectural Decision Records with Evolution Engine

This guide demonstrates how to incrementally refine active Architectural Decision Records (ADRs) using `spec-ops adr amend`, governed by [ADR-0001](../project/adrs/accepted/adr-0001-specification-as-code-pmac.md), [ADR-0002](../project/adrs/accepted/adr-0002-modular-source-file-length-guardrails.md), and [ADR-0007](../project/adrs/accepted/adr-0007-domain-driven-design-and-bounded-contexts.md).

---

## Overview

Unlike total supersession (which retires a predecessor ADR as `Superseded` and flags citing tasks for re-refinement), real-world software architectures frequently evolve through **non-destructive incremental amendments**.

For example:
- **ADR-0101** establishes the foundational event log schema and aggregate boundaries.
- **ADR-0136** refines how canonical fields merge during conflict resolution, amending ADR-0101's version table while ADR-0101's core aggregate boundaries stand 100%.

The ADR Amendment Engine provides:
- Automated scaffolding or promotion of amending ADRs with `amends: [ADR-XXXX]`
- Non-destructive updates to predecessor ADRs recording `amended_by: [ADR-YYYY]` while retaining active `Accepted` status
- Synchronized updates to `docs/project/adrs/REGISTRY.md` maintaining active status
- Graph cycle prevention (`CircularAmendmentError`) ensuring decision DAGs remain acyclic
- Preservation of task governance under Definition of Ready (DoR) gates
- Automated amendment delta hydration into autonomous worker prompt contracts (`.task-prompt.md`) and `spec-ops pathfinder inspect`

---

## Amending an ADR by Title

To scaffold a new incremental amendment decision while keeping the target ADR active:

```bash
uv run spec-ops adr amend ADR-0101 --title "Provenance Value Object Schema"
```

Output:
```text
✨ Amended ADR-0101 with new ADR-0135
📄 Generated docs/project/adrs/accepted/adr-0135-provenance-value-object-schema.md status as 'Accepted' with 'amends: [ADR-0101]'
📄 Updated docs/project/adrs/accepted/adr-0101-event-log-schema.md with 'amended_by: [ADR-0135]' (status remains 'Accepted')
📋 Synchronized docs/project/adrs/REGISTRY.md
```

---

## Amending with an Existing Proposed ADR

If a proposed draft ADR has already been authored in `docs/project/adrs/proposed/`:

```bash
uv run spec-ops adr amend ADR-0102 --by docs/project/adrs/proposed/adr-0116-graph-capabilities.md
```

The engine promotes the proposed ADR to `Accepted`, moves it to `docs/project/adrs/accepted/`, injects `amends: [ADR-0102]`, records `amended_by: [ADR-0116]` in the predecessor ADR, and updates `REGISTRY.md`.

---

## Inspecting Decision Lineage with Pathfinder

To inspect the governing architectural decisions and active amendments for any task or entity:

```bash
uv run spec-ops pathfinder inspect TASK-0012
```

Output displays the entity card with both primary and active amending decisions:
```text
+-----------------+---------------------------------------------+
| Field            | Value                         |
+-----------------+---------------------------------------------+
| Entity ID        | TASK-0012                     |
| Type             | Task (Refined)                |
| Target BC        | core                          |
| Governing ADRs   | ADR-0102 (active amendments: ADR-0116, ADR-0127) |
| Governing Story  | US-0001                       |
| Persona Lineage  | Alex (via US-0001)            |
+-----------------+---------------------------------------------+
```

---

## Autonomous Worker Context Hydration

When an autonomous coding agent claims a task (`spec-ops queue claim`), the task prompt contract (`.task-prompt.md`) automatically discovers all active amendments for cited governing ADRs:

```markdown
## Architectural Context
- Target Bounded Context: core
- Governing ADRs: ADR-0102 (active amendments: ADR-0116, ADR-0127)
- Active ADR Amendments: ADR-0116, ADR-0127 (incorporate active delta refinements from amending decisions).
```

This guarantees the autonomous worker incorporates recent signature and capability refinements without requiring manual backlog re-refinement.
