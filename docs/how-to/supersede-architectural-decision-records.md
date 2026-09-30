# How to Supersede Architectural Decision Records

This guide explains how to supersede an existing Architectural Decision Record (ADR) with a new decision, update the ADR registry, audit active backlog citations, and synchronize the living constitution (`AGENTS.md`).

---

## Overview

As software architecture evolves, previous architectural decisions are superseded by new paradigms (for example, graduating an architectural spike or migrating from an in-memory cache to a content-addressed storage engine). In SpecOps, architectural decisions govern both human developers and autonomous coding agents through `AGENTS.md` and PMaC task frontmatter (ADR-0001, ADR-0008). 

The `spec-ops adr supersede` command provides an automated workflow to supersede older ADRs safely without leaving broken citations in the backlog.

---

## Step 1: Draft the New Decision Record

Before superseding an existing decision, author the new ADR in `docs/project/adrs/proposed/`:

```markdown
---
id: '0020'
title: Streaming Real-Time Graph Event Bus
status: Proposed
governing_prds:
  - PRD-0005
---

# ADR-0020: Streaming Real-Time Graph Event Bus
...
```

Ensure the proposed decision documents the context, trade-offs, and consequences of superseding the older decision.

---

## Step 2: Execute ADR Supersession

Run the supersession command pointing from the old ADR to the newly proposed decision:

```bash
spec-ops adr supersede ADR-0010 --by ADR-0020
```

This command executes the following operations:
1. **Status Transition**: Moves the old ADR file to `docs/project/adrs/superseded/` and updates its frontmatter to `status: Superseded` with a bidirectional link `superseded_by: ADR-0020`.
2. **Acceptance Promotion**: Moves the new ADR file from `proposed/` to `accepted/` and sets its frontmatter to `status: Accepted` with `supersedes: ADR-0010`.
3. **Registry Synchronization**: Updates `docs/project/adrs/REGISTRY.md` to reflect the new statuses and supersession linkages.
4. **Backlog Citation Audit**: Scans active tasks in `docs/project/backlog/` citing `ADR-0010` and prints warnings or updates citations to prevent broken architectural assumptions.

---

## Step 3: Synchronize Living Constitution and Verify Health

If the superseded ADR defined non-negotiable Hard Invariants in `AGENTS.md`, update or synchronize the living constitution:

```bash
uv run spec-ops health
```

The health check validates that no active task files point to non-existent ADRs and confirms 0 constitution drift warnings.
