---
id: '0089'
title: Safe Worktree Discard with Anti-Loop Failure Memory and Task Reset
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-RESC-03
governing_prd: PRD-0004
---

# US-0089 — Safe Worktree Discard with Anti-Loop Failure Memory and Task Reset

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As a** human software engineer determining that an agent's approach was fundamentally flawed or misaligned with architecture,
  - **I want** to execute `spec-ops rescue reset <task-id>` to safely wipe the failed worktree while recording failure lessons and anti-patterns directly into the task's PMaC specification,
  - **So that** when the task is returned to the `refined/` buffer, future worker sessions are hydrated with explicit negative constraints that prevent infinite failure loops.

## Acceptance Criteria

```gherkin
Scenario: Discarding worktree and capturing failure post-mortem into task frontmatter
Given a stalled worktree ".worktrees/task-0024" where the agent attempted an invalid monkey-patching approach
When the engineer executes:
"""
spec-ops rescue reset TASK-0024 --reason "Agent attempted internal mock backdoors violating ADR-0003 instead of public CLI testing"
"""
Then the git worktree ".worktrees/task-0024" and branch "feat/TASK-0024" are deleted
And the task specification file "docs/project/backlog/refined/0024-*.md" is updated with frontmatter metadata:
"""
failure_history:
- attempt_date: 2026-09-29
reason: "Agent attempted internal mock backdoors violating ADR-0003 instead of public CLI testing"
failed_invariants: [ADR-0003]
"""
And task "TASK-0024" remains in "docs/project/backlog/refined/" for re-assignment.
```
```gherkin
Scenario: Automatic demotion to proposed stage when specification ambiguity is flagged
Given an engineer determines that "TASK-0030" stalled because acceptance criteria were contradictory
When the engineer executes "spec-ops rescue reset TASK-0030 --demote --reason 'Contradictory Gherkin criteria in Scenario 2'"
Then the worktree and branch are cleaned up
And the task file is moved from "docs/project/backlog/refined/" to "docs/project/backlog/proposed/"
And "docs/project/backlog/PRIORITY.md" is synchronized without task "TASK-0030" blocking the refined queue.
```
```gherkin
Scenario: Hydrating subsequent worker prompts with negative constraints from failure history
Given task "TASK-0024" has recorded failure history citing "ADR-0003 violation"
When an autonomous worker claims "TASK-0024" for a new attempt
Then the generated ".task-prompt.md" includes a dedicated section:
"""
## Prior Attempt Failures & Anti-Patterns (DO NOT REPEAT)
- Previous failure: Agent attempted internal mock backdoors violating ADR-0003 instead of public CLI testing.
- Mandate: You must strictly use public frontdoor entrypoints with zero mock backdoors.
"""
-
```

## Rationale & Compelling Value
- **Adoption**: Removes the anxiety of discarding agent work by turning a failed attempt into valuable guidance rather than lost effort.
  - **Regular Usage**: Prevents autonomous worker fleets from burning tokens on circular dead-ends.
  - **Compelling Value**: Eliminates repetitive agent hallucination loops and continuously improves task definition quality through version-controlled institutional memory.

---
