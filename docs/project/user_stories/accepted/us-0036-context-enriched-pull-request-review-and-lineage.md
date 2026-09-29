---
id: '0036'
title: Context-Enriched Pull Request Review and Architectural Lineage
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-REV-01
governing_prd: PRD-0004
---

# US-0036 — Context-Enriched Pull Request Review and Architectural Lineage

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As an** human software engineer reviewing AI-generated pull requests,  
**I want** `spec-ops review <task-id>` to generate a concise review brief linking the diff directly to its governing PRD, ADRs, Gherkin scenarios, and commit provenance,  
**So that** I eliminate agent PR fatigue by reviewing code against intentional architectural contracts rather than deciphering hundreds of lines of raw AI diffs in isolation.

## Acceptance Criteria

```gherkin
Scenario: Generating an architectural review brief for an agent PR
Given a task branch "task/TASK-0015" created by an autonomous agent for "TASK-0015"
When the engineer executes "spec-ops review TASK-0015"
Then the CLI outputs a structured architectural review summary including:
  | Section               | Content                                                 |
  | Governing PRD         | PRD-0001 (SpecOps Autonomous Project Management Engine) |
  | Governing ADRs        | ADR-0002 (<500 lines limit), ADR-0003 (Frontdoor TDD)   |
  | Acceptance Scenarios  | Executable Gherkin scenarios from governing user story  |
  | Lineage Path          | Persona -> PRD -> User Story -> Task                    |
And all changed source files are summarized with line delta and file-limit headroom
And zero private internal mocks are flagged in the verification report.
```

```gherkin
Scenario: Verifying commit provenance trailers and author distinction
Given a pull request branch containing both human and agent commits
When the engineer executes "spec-ops review TASK-0015 --provenance"
Then the review report identifies which commits were authored by autonomous workers versus human contributors
And any commit missing the "SpecOps-Task: TASK-0015" git trailer is flagged with a warning.
```

## Rationale & Compelling Value
Slashes review time by up to 70%, relieves cognitive fatigue, and prevents agents from quietly introducing unauthorized architectural patterns.
