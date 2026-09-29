---
id: '0014'
title: Architectural Decision Record Supersession and Living Constitution Synchronization
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-ADR-02
governing_prd: PRD-0005
---

# US-0014 — Architectural Decision Record Supersession and Living Constitution Synchronization

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect,  
**I want** to execute `spec-ops adr supersede <old-adr> --with <new-adr>`,  
**So that** the ADR registry updates atomically, affected active user stories and tasks are flagged for review, and `AGENTS.md` is re-synchronized to replace obsolete rules.

## Acceptance Criteria

```gherkin
Scenario: Superseding an ADR and updating registry links
Given an accepted ADR "ADR-0003: Blackbox Frontdoor Verification"
And a newly drafted ADR "docs/project/adrs/proposed/adr-0015-enhanced-frontdoor-contracts.md"
When the architect runs "spec-ops adr supersede ADR-0003 --with docs/project/adrs/proposed/adr-0015-enhanced-frontdoor-contracts.md"
Then "ADR-0003" status is updated to "Superseded" with frontmatter "superseded_by: ADR-0015"
And "ADR-0015" is moved to "docs/project/adrs/accepted/" with status "Accepted"
And "docs/project/adrs/REGISTRY.md" is updated to reflect the supersession link.
```

```gherkin
Scenario: Re-synchronizing AGENTS.md constitution upon ADR supersession
Given ADR-0003 has been superseded by ADR-0015
When the system updates the agent constitution via "spec-ops scaffold agents"
Then the Hard Invariants section in "AGENTS.md" replaces the rules of ADR-0003 with the rules of ADR-0015
And commits the change cleanly with trailer "SpecOps-ADR: ADR-0015".
```

```gherkin
Scenario: Flagging active backlog tasks citing superseded ADRs
Given task "TASK-0014" in "docs/project/backlog/refined/" cites "governing_adr: ADR-0003"
When the architect runs "spec-ops adr supersede ADR-0003 --with ADR-0015"
Then "TASK-0014" is flagged with a warning in "spec-ops health"
And reports "Task TASK-0014 cites superseded ADR-0003; requires architectural re-refinement".
```

## Rationale & Compelling Value
Prevents architectural decay. Updating an ADR automatically updates the agent constitution and highlights affected tasks before any agent works on them.
