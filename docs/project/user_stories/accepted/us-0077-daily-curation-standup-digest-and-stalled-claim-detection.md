---
id: '0077'
title: Daily Curation Standup Digest, Stalled Claim Detection, and Milestone Scope Transition
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-BACK-05
governing_prd: PRD-0005
---

# US-0077 — Daily Curation Standup Digest, Stalled Claim Detection, and Milestone Scope Transition

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** AI-native engineering lead,
  - **I want** to execute `spec-ops backlog sweep` and `spec-ops backlog milestone transition`,
  - **So that** daily progress, stalled worker claims, and milestone boundary transitions are managed systematically without manual ticket shuffling.

## Acceptance Criteria

```gherkin
Scenario: Generating Daily Standup Curation Digest
Given a repository with 3 tasks completed in the last 24 hours, 6 tasks in the ready buffer, and 1 claimed task with no git commits for 48 hours
When the lead runs "spec-ops backlog sweep"
Then the command outputs a concise terminal standup digest:
| Metric               | Current State               | Recommended Action       |
| Ready Buffer Level   | 6/10 (Under-buffered)       | Promote 4 proposed tasks |
| Velocity (24h)       | 3 tasks completed           | On track                 |
| Stalled Worktrees    | TASK-0013 (48h no activity) | Trigger human rescue     |
And highlights candidate proposed tasks ready for immediate refinement.
```
```gherkin
Scenario: Flagging and Reclaiming Abandoned Task Claims
Given task "TASK-0013" in "refined/" has frontmatter "claimed_by: agent-01" with timestamp older than 24 hours
And the associated worktree ".worktrees/task-0013" has zero unstaged diffs and no running processes
When the lead runs "spec-ops backlog sweep --reclaim-stalled"
Then SpecOps resets "claimed_by" to empty
And restores "TASK-0013" status to "Refined" in "PRIORITY.md"
Making it immediately available for other workers.
```
```gherkin
Scenario: Transitioning Backlog Scope Across Milestone Boundaries
Given "Milestone 1" has 100% of tasks in "docs/project/backlog/complete/"
And "Milestone 2" has 8 tasks in "proposed/" with satisfied dependencies
When the lead executes "spec-ops backlog milestone transition --from M1 --to M2"
Then SpecOps verifies Milestone 1 completion criteria
And bulk-evaluates Milestone 2 proposed tasks against the Definition of Ready
And replenishes the ready buffer with Milestone 2 tasks up to the target buffer limit of 10.
-
```

## Rationale & Compelling Value
- **Adoption**: Replaces 30-minute manual Jira sprint transitions and standups with a 5-second CLI operation.
  - **Regular Usage**: Run every morning during team standup and at every milestone release cutoff.
  - **Compelling Value**: Prevents abandoned worker branches from locking tasks indefinitely, ensuring steady flow and reliable delivery cadence.

---
