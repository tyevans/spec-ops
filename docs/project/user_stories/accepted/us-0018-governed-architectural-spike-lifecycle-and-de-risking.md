---
id: '0018'
title: Governed Architectural Spike Lifecycle and Invariant De-Risking
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-SPK-01
governing_prd: PRD-0005
---

# US-0018 — Governed Architectural Spike Lifecycle and Invariant De-Risking

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect,  
**I want** to scaffold and execute timeboxed architectural spike tasks that test high-risk technical unknowns through disposable frontdoor harnesses,  
**So that** autonomous agents can prove technical feasibility before PRD decomposition while preventing experimental spike code from leaking into production without meeting quality invariants.

## Acceptance Criteria

```gherkin
Scenario: Scaffolding an architectural spike task from an idea-stage PRD
Given an accepted PRD "PRD-0002" with an unverified performance hypothesis regarding WebSockets
When the architect runs "spec-ops spike create --prd PRD-0002 --name 'WebSocket Latency Spike' --timebox 4h"
Then a spike task is created in "docs/project/backlog/proposed/SPIKE-0001-websocket-latency-spike.md"
And the spike frontmatter includes "type: Spike", "timebox: 4h", and "target_hypothesis: WebSockets meet <50ms latency"
And an isolated spike harness template is generated under "spikes/spike_0001/".
```

```gherkin
Scenario: Blocking direct production merge of un-graduated spike code
Given a git branch "spike/SPIKE-0001" containing exploratory prototype code in "spikes/"
When the worker attempts to merge "spike/SPIKE-0001" directly into "main" without graduation
Then the preflight CI gate blocks the merge
And reports "Merge Blocked: Architectural spikes cannot merge directly to main; execute 'spec-ops spike graduate'".
```

```gherkin
Scenario: Graduating a validated spike into an accepted ADR and production tasks
Given a completed spike "SPIKE-0001" with validated findings recorded in its report section
When the architect runs "spec-ops spike graduate SPIKE-0001 --adrs 'ADR-0010' --decompose-tasks"
Then a new draft ADR "ADR-0010" is authored with the proven architectural decision
And production vertical slice tasks are emitted into "docs/project/backlog/proposed/"
And the spike task moves to "complete/" referencing the graduated ADR.
```

## Rationale & Compelling Value
Makes architectural spikes first-class: isolated in worktrees, tied to falsifiable hypotheses, and graduated cleanly into formal ADRs and verified vertical slice tasks.
