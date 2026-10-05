---
id: '0131'
title: Relational Graph Traceability and Architecture Radar Visualization for ADR Amendments
status: Accepted
created: 2026-10-04
persona: Alex (The Agentic Systems Architect)
target_bc: visualizer
feature: FEAT-ADR-03
governing_prd: PRD-0005
scenarios:
  - Compiling bidirectional ADR-to-ADR amends and supersedes edges into relational graph
  - Rendering amended ADRs with distinct active badges and evolution drawers in Architecture Radar
  - Hydrating amending ADR context into pathfinder and autonomous worker contracts
---

# US-0131 — Relational Graph Traceability and Architecture Radar Visualization for ADR Amendments

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect (Alex) or engineering lead (Jordan),  
**I want** the relational graph, living 2D visualizer, and Architecture Radar to compile and display `amends` and `supersedes` edges between ADRs,  
**So that** human reviewers and autonomous coding agents can visually explore the decision evolution DAG and understand the complete delta context behind living architectural standards.

## Acceptance Criteria

```gherkin
Scenario: Compiling bidirectional ADR-to-ADR amends and supersedes edges into relational graph
  Given a set of ADRs where ADR-0116 has frontmatter "amends: [ADR-0102]" and ADR-0120 has "supersedes: [ADR-0118]"
  When the relational graph compiler runs via "spec-ops graph compile"
  Then the graph includes directed edge "(ADR-0116)-[:amends]->(ADR-0102)"
  And the graph includes directed edge "(ADR-0120)-[:supersedes]->(ADR-0118)"
  And "spec-ops trace --verify" passes with 100% graph connectivity.
```

```gherkin
Scenario: Rendering amended ADRs with distinct active badges and evolution drawers in Architecture Radar
  Given an ADR "ADR-0101" that is amended by "ADR-0135" and "ADR-0136"
  When viewing the Architecture Radar or ADR tab in the living visualizer
  Then ADR-0101 is rendered with an active status badge (e.g. green or cyan with an "Amended" chip) rather than a strikethrough red badge
  And opening the ADR detail drawer displays an "Amendments" lineage section linking directly to ADR-0135 and ADR-0136
  And viewing ADR-0135 in the drawer displays "Amends: ADR-0101".
```

```gherkin
Scenario: Hydrating amending ADR context into pathfinder and autonomous worker contracts
  Given task "TASK-0012" cites "governing_adrs: [ADR-0102]"
  And ADR-0102 has recorded amendments [ADR-0116, ADR-0127]
  When an autonomous worker session or "spec-ops pathfinder inspect TASK-0012" runs
  Then the hydrated task context includes both the primary governing decision ADR-0102 and the active amending decisions ADR-0116 and ADR-0127
  So that the autonomous coding agent is fully aware of recent signature and capability refinements.
```

## Rationale & Compelling Value
Provides clear visibility into living architecture. When an autonomous coding agent picks up a task governed by an amended ADR, it must not only read the original decision but also receive the active amendments. Rendering these relationships in the living graph visualizer transforms isolated Markdown documents into a coherent architectural knowledge network.
