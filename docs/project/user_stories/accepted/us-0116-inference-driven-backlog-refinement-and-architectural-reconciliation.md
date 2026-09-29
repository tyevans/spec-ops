---
id: '0116'
title: Inference-Driven Backlog Refinement, Architectural Drift Reconciliation, and Scope Slicing
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
feature: FEAT-CUR-01
governing_prd: PRD-0005
---

# US-0116 — Inference-Driven Backlog Refinement, Architectural Drift Reconciliation, and Scope Slicing

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** AI-native engineering lead and systems architect,  
**I want** `spec-ops curate --infer` and the `/curate` agent skill to utilize LLM inference to critically evaluate proposed tasks against current repository reality,  
**So that** proposed tasks are audited for architectural drift, oversized scopes (>500 lines) are autonomously sliced into thin vertical slices or spikes, and missing Definition of Ready (DoR) criteria (executable Gherkin scenarios and property invariants) are synthesized rather than passively rejected.

## Acceptance Criteria

```gherkin
Scenario: Detecting Architectural Drift and Reconciling Stale Task Specifications
Given a proposed task "TASK-0062" authored against a legacy module that has since been refactored
And the project ADR registry contains superseding decisions adopted since the task was drafted
When the lead runs "spec-ops curate --infer"
Then the curation engine analyzes current repository files, the relational knowledge graph, and recent ADRs
And updates the task frontmatter and specification text to align with active bounded contexts and module paths
And notes reconciled architectural changes in the curation audit trail.
```

```gherkin
Scenario: Autonomously Slicing Oversized Monolithic Tasks into Thin Vertical Slices
Given a proposed task whose specification touches multiple bounded contexts and is estimated to exceed the 500-line modular limit (ADR-0002)
When "spec-ops curate --infer" audits the task for refinement
Then the curation inference engine identifies the scope violation
And decomposes the task into discrete INVEST-compliant vertical slices and an initial architectural spike
And scaffolds sequential child tasks in "docs/project/backlog/proposed/" linked to the parent PRD
And promotes only the initial thin slice or spike to "docs/project/backlog/refined/".
```

```gherkin
Scenario: Generative Definition of Ready (DoR) Synthesis instead of Dumb Rejection
Given a proposed task lacking executable Gherkin scenarios or property-based testing invariants
When "spec-ops curate --infer" processes the task for buffer replenishment
Then rather than aborting with a hard rejection error, the engine inspects the governing PRD checkable outcomes and public frontdoors
And synthesizes executable Gherkin scenarios ("Given ... When ... Then") and Hypothesis invariant specifications
And writes the complete DoR-compliant contract into the task markdown before promoting it to "docs/project/backlog/refined/".
```

```gherkin
Scenario: Interactive AI-Native /curate Slash Command Skill
Given an autonomous coding agent operating in Antigravity or Claude Code
When the developer or lead triggers "/curate"
Then the agent executes an interactive cognitive refinement workflow: auditing the under-buffered queue, evaluating proposed tasks against repository reality, proposing vertical decompositions for oversized tasks, and presenting a human-in-the-loop review before moving tasks to "docs/project/backlog/refined/".
```

## Rationale & Compelling Value
- **Adoption**: Replaces frustrating manual ticket re-authoring with automated, context-aware refinement that keeps backlog items aligned with rapid code evolution.
- **Regular Usage**: Triggered daily during buffer replenishment sweeps (`/curate` or automated CI cron).
- **Compelling Value**: Bridges the gap between static markdown specifications and living code reality. Prevents autonomous workers from hallucinating or failing preflight on outdated or oversized tasks.

---
