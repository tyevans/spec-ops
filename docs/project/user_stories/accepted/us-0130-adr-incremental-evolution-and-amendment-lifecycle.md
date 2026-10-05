---
id: '0130'
title: Architectural Decision Record Amendment Workflow and Frontmatter Lineage Tracking
status: Accepted
created: 2026-10-04
persona: Alex (The Agentic Systems Architect)
target_bc: core
feature: FEAT-ADR-03
governing_prd: PRD-0005
scenarios:
  - Amending an accepted ADR with a new incremental decision via CLI
  - Linking an amendment to an existing draft ADR
  - Preserving active status and backlog task validity for amended ADRs
  - Detecting and rejecting circular amendment chains
---

# US-0130 — Architectural Decision Record Amendment Workflow and Frontmatter Lineage Tracking

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect (Alex),  
**I want** to execute `spec-ops adr amend <old-adr> [--by <new-adr> | --title <title>]` and maintain bidirectional `amends` / `amended_by` frontmatter metadata,  
**So that** architectural decisions can evolve incrementally without falsely marking foundational decisions as dead or invalidating active backlog tasks.

## Acceptance Criteria

```gherkin
Scenario: Amending an accepted ADR with a new incremental decision via CLI
  Given an accepted ADR "ADR-0101: Event Log Schema and Granularity" in "docs/project/adrs/accepted/"
  When the architect runs "spec-ops adr amend ADR-0101 --title 'Provenance Value Object Schema'"
  Then a new ADR is scaffolded in "docs/project/adrs/accepted/" with frontmatter "amends: [ADR-0101]"
  And the target ADR "ADR-0101" frontmatter appends the new ADR to its "amended_by" list
  And the target ADR "ADR-0101" maintains status "Accepted" (or "Accepted (Amended)")
  And "docs/project/adrs/REGISTRY.md" is synchronized to reflect the amendment relationship without marking ADR-0101 as Superseded.
```

```gherkin
Scenario: Linking an amendment to an existing draft ADR
  Given an accepted ADR "ADR-0102: Two Store Ports"
  And a drafted ADR "docs/project/adrs/proposed/adr-0116-graph-store-is-five-capabilities.md"
  When the architect runs "spec-ops adr amend ADR-0102 --by docs/project/adrs/proposed/adr-0116-graph-store-is-five-capabilities.md"
  Then "ADR-0116" is promoted to "docs/project/adrs/accepted/" with frontmatter "amends: [ADR-0102]"
  And "ADR-0102" records "amended_by: [ADR-0116]" in its YAML frontmatter
  And both decisions remain active architectural authorities.
```

```gherkin
Scenario: Preserving active status and backlog task validity for amended ADRs
  Given an accepted ADR "ADR-0101" that has been amended by "ADR-0135" and "ADR-0136"
  And an active task "TASK-0042" in "docs/project/backlog/refined/" citing "governing_adrs: [ADR-0101]"
  When the architect runs "spec-ops health" or "spec-ops check"
  Then the task passes the Definition of Ready (DoR) governing ADR gate
  And "spec-ops reconciler" does not replace ADR-0101 with ADR-0136
  And the audit report notes that ADR-0101 has active amendments [ADR-0135, ADR-0136].
```

```gherkin
Scenario: Detecting and rejecting circular amendment chains
  Given ADR-0110 already amends ADR-0105
  When an attempt is made to execute "spec-ops adr amend ADR-0110 --by ADR-0105"
  Then the amendment operation is aborted with a CircularAmendmentError
  And all existing ADR frontmatters remain unmodified.
```

## Rationale & Compelling Value
In real-world software architecture, decisions are rarely completely discarded; they are refined and extended. Pure supersession is destructive because it flags foundational decisions as obsolete and breaks downstream task governance. Supporting incremental amendments preserves decision lineage, keeps foundational contracts active, and prevents spurious backlog task invalidation.
