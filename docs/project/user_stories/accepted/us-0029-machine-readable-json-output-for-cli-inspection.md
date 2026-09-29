---
id: '0029'
title: Machine-Readable JSON Output for Autonomous CLI Inspection
status: Accepted
created: 2026-09-29
persona: Morgan (The Autonomous Coding Agent)
feature: FEAT-CLI-01
governing_prd: PRD-0001
---

# US-0029 — Machine-Readable JSON Output for Autonomous CLI Inspection

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** autonomous coding agent,  
**I want** all SpecOps inspection commands to support a `--json` output flag,  
**So that** I can reliably parse backlog items, queue state, health violations, and project metadata programmatically without fragile regex scraping of ANSI-styled terminal text.

## Acceptance Criteria

```gherkin
Scenario: Inspecting Next Backlog Task with Machine-Readable JSON
Given a project backlog with refined tasks in "docs/project/backlog/refined/"
When the agent runs "spec-ops curate next --json"
Then the command exits with return code 0
And the output is valid JSON conforming to the Task schema
And the JSON payload includes fields "id", "canonical_id", "title", "target_bc", "dependencies", and "governing_adrs"
And no ANSI color codes or decorative terminal banners are present in the output.
```

```gherkin
Scenario: Parsing Health Violations via Structured JSON
Given a repository containing one file exceeding 500 lines and one unsynced priority task
When the agent runs "spec-ops health --json"
Then the command exits with return code 1
And the output is a valid JSON object containing "status: error"
And the "violations" array contains the violating file path, line count, and offending rule "ADR-0002"
And the "priority_sync" object reports the mismatched task IDs.
```

## Rationale & Compelling Value
First-class `--json` flags across the entire CLI surface eliminate fragile regex scraping and token waste, enabling programmatic parsing of repository state.
