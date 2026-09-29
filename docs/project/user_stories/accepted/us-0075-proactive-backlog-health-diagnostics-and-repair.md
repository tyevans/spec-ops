---
id: '0075'
title: Proactive Backlog Health Diagnostics, Dangling Dependency Auditing, and Self-Healing Repair
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-BACK-03
governing_prd: PRD-0005
---

# US-0075 — Proactive Backlog Health Diagnostics, Dangling Dependency Auditing, and Self-Healing Repair

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** AI-native engineering lead,
  - **I want** to run `spec-ops backlog doctor` with an automated `--repair` flag,
  - **So that** orphaned task files, broken dependency references, ghost index entries, and stale proposed tasks are diagnosed and remediated before they cause worker failures.

## Acceptance Criteria

```gherkin
Scenario: Detecting Broken and Dangling Dependency Pointers
Given task "TASK-0050" in "docs/project/backlog/proposed/" lists "dependencies: [TASK-9999]"
And "TASK-9999" does not exist in complete, refined, or proposed backlog folders
When the lead executes "spec-ops backlog doctor"
Then the command exits with code 1
And reports "Backlog Defect: TASK-0050 references non-existent dependency 'TASK-9999'"
And suggests removing the dangling reference or authoring the missing task specification.
```
```gherkin
Scenario: Detecting Ghost Entries and Unindexed Files in PRIORITY.md
Given file "0099-orphan-task.md" exists in "docs/project/backlog/proposed/" but is missing from "PRIORITY.md"
And "PRIORITY.md" lists a reference to "TASK-0088" whose file has been deleted from disk
When the lead runs "spec-ops backlog doctor"
Then the diagnostic report highlights 1 unindexed task file and 1 ghost index reference
And warns of backlog synchronization drift.
```
```gherkin
Scenario: Automated Self-Healing Repair
Given backlog synchronization drift with 1 unindexed file and 1 ghost entry
When the lead runs "spec-ops backlog doctor --repair"
Then "PRIORITY.md" is cleaned of the ghost reference to "TASK-0088"
And "0099-orphan-task.md" is deterministically appended to "PRIORITY.md" under proposed status
And the command exits with code 0 and reports "Backlog self-healing complete: 2 issues remediated".
-
```

## Rationale & Compelling Value
- **Adoption**: Provides an ergonomic `doctor` entrypoint familiar to modern developers (`brew doctor`, `flutter doctor`), easing PMaC onboarding.
  - **Regular Usage**: Embedded into preflight health checks (`spec-ops health`) and sprint grooming rituals.
  - **Compelling Value**: Prevents worker crashes and merge rejections by catching specification rot, broken links, and ghost files before code is written.

---
