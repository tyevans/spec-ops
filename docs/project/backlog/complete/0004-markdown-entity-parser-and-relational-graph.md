---
id: '0004'
title: Unified Markdown Entity Parser and Relational Graph
status: Complete
created: 2026-09-29
dependencies:
  - TASK-0001
governing_adrs:
  - ADR-0001
governing_prds:
  - PRD-0001
governing_stories:
  - US-0001
target_bc: core
---

# TASK-0004: Unified Markdown Entity Parser and Relational Graph

## Summary
Build universal Markdown entity parser and bi-directional graph builder linking Personas, PRDs, User Stories, Tasks, ADRs, and git commits.

## Definition of Done
1. `SpecOpsParser` safely parses YAML frontmatter and markdown sections.
2. `ProjectGraph` builds bi-directional adjacency matrices and cross-references.
3. Graph calculates project metrics (completion rate, orphan entities, edge counts).
4. Unit tests pass with realistic multi-entity structures.
