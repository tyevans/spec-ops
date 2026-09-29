---
id: '0070'
title: Architectural Profile Version Lifecycle, Semantic Diffs, and Invariant Migrations
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-SCAF-05
governing_prd: PRD-0005
---

# US-0070 — Architectural Profile Version Lifecycle, Semantic Diffs, and Invariant Migrations

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect,  
**I want** to inspect version differences across architectural profile releases and execute automated migrations,  
**So that** existing codebases can upgrade to newer profile versions to inherit enhanced invariants and ADR updates without breaking existing repository structures or losing local modifications.

## Acceptance Criteria

```gherkin
Scenario: Inspecting profile upgrades and semantic invariant diffs
Given a repository initialized with profile "core@1.0.0" recorded in "specops.toml"
And a new upstream profile release "core@2.0.0" introducing an updated invariant and ADR
When the architect runs "spec-ops profiles diff core"
Then the terminal outputs a semantic diff of newly added ADRs, modified invariant clauses, and configuration changes
And highlights breaking changes (e.g. decreased file length limit or newly mandated mutation testing).
```
```gherkin
Scenario: Applying profile upgrade and migrating baseline ADRs
Given a project configured with profile "core@1.0.0"
When the architect runs "spec-ops profiles upgrade core"
Then "specops.toml" is updated to "core@2.0.0"
And new baseline ADR files are installed into "docs/project/adrs/accepted/" with sequential numbering
And "docs/project/adrs/REGISTRY.md" is updated atomically
And "AGENTS.md" is re-synchronized to reflect the updated profile invariants.
```
```gherkin
Scenario: Safe migration abort on conflicting local ADR modifications
Given a local project that has modified the content of installed "ADR-0002"
When the architect runs "spec-ops profiles upgrade core" without the force flag
Then the migration pauses and flags a conflict for "ADR-0002"
And prompts the architect to choose between keeping the local override, accepting upstream, or creating a custom ADR diff.
```

## Rationale & Compelling Value
Turns static architecture into a living, versioned product lifecycle. Prevents repositories from becoming stuck on day-one boilerplate.

---
