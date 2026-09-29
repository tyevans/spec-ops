---
id: '0003'
title: PRD Vertical Slice Decomposition into Spikes and Tasks
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-PRD-01
governing_prd: PRD-0001
---

# US-0003 — PRD Vertical Slice Decomposition into Spikes and Tasks

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** engineering lead,  
**I want** to execute `spec-ops prd decompose PRD-XXXX`,  
**So that** high-level product requirements are automatically broken down into thin, single-pass vertical slices and architectural spike tasks with governing ADR links.

## Acceptance Criteria

### Scenario 1: Decomposing an Accepted PRD
```gherkin
Given an accepted PRD with linked user stories and checkable outcomes
When the developer runs "spec-ops prd decompose PRD-0001 --spikes"
Then vertical slice tasks are generated in "docs/project/backlog/proposed/"
And an architectural spike task is generated for unverified invariants
And each generated task cites its governing PRD, stories, and baseline ADRs.
```
