---
id: 0079
title: External Issue Tracker Ingestion Bridge
status: Complete
dependencies:
- TASK-0067
- TASK-0072
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0079
target_bc: backlog
---

# TASK-0079: External Issue Tracker Ingestion Bridge

## Summary
Implement issue tracker ingestion (`spec-ops bridge import --source github|jira|linear [--file <path>] [--repo <org/repo>]`) to import external issues into schema-compliant proposed task files in `docs/project/backlog/proposed/` with mapped titles, non-colliding numeric IDs, and reference links.

## Problem Statement & Context
While autonomous coding assistants and engineering architects work directly against Git-versioned specifications in `docs/project/backlog/`, external stakeholders, product managers, and enterprise executives often file issues in GitHub Issues, Jira, or Linear. Without automated import tooling, specifications must be manually copied, introducing transcription errors. SpecOps requires an automated bridge to ingest external issues into valid proposed task files.

## User Stories & Scenarios Satisfied
- **US-0079: Brownfield Issue Ingestion and External Backlog Synchronization Bridge**
  - *Scenario: Ingesting GitHub Issues into Validated Proposed Task Files*
    - Given a GitHub repository with labeled issues
    - When the developer runs "spec-ops bridge import --source github --repo org/repo --label specops"
    - Then each imported issue generates a valid Markdown task in "docs/project/backlog/proposed/" with assigned sequential task ID, mapped title, and external reference links.
  - *Scenario: Ingesting Structured CSV/JSON Export from Jira or Linear*
    - Given an exported JSON or CSV export file from Jira or Linear
    - When the developer executes "spec-ops bridge import --file export.json"
    - Then tasks are parsed, validated against the task schema, and placed in "proposed/" without overwriting existing tasks.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: External bridge importer in `src/spec_ops/backlog/bridge/importer.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomized issue payloads assert that imported issues strictly generate valid proposed task Markdown with non-colliding IDs and valid frontmatter schemas.
- **Mutmut Mutation Scope**: Schema mapping and frontmatter serialization in `src/spec_ops/backlog/bridge/importer.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops bridge import` generates valid proposed task markdown files with non-colliding IDs.
2. Ingested tasks pass `spec-ops schema validate` and conform to Definition of Ready metadata standards.
3. All acceptance criteria verified via public CLI frontdoors with `pytest-bdd` (ADR-0003, ADR-0006).
