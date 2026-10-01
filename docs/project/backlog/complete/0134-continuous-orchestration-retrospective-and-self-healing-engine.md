---
id: '0134'
title: Continuous Orchestration Retrospective and Self-Healing Engine
status: Complete
dependencies:
- TASK-0125
- TASK-0111
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
- ADR-0007
- ADR-0008
- ADR-0020
governing_prds:
- PRD-0001
- PRD-0006
governing_stories:
- US-0117
target_bc: worker
---

# TASK-0134: Continuous Orchestration Retrospective and Self-Healing Engine

## Summary
Implement the continuous orchestration retrospective and self-healing diagnostic engine (`spec-ops orchestrate retrospect` and `spec-ops orchestrate health`). In accordance with the SpecOps SDLC Orchestration Failure Protocol in `AGENTS.md`, the engine analyzes recent agent session transcripts, git worktree rescue events, and preflight test failures to detect recurring failure patterns (e.g. mock backdoors, secret leaks, line limit breaches) and automatically synthesizes high-priority remediation tasks in `docs/project/backlog/proposed/`.

## Problem Statement & Context
When human leads or orchestrator skills drive multi-agent work, orchestration and preflight failures can stall progress if not systematically harvested and turned into actionable backlog items. The dogfooding invariant in `AGENTS.md` mandates that any orchestration failure is an actionable task. An autonomous retrospective engine makes this self-healing loop continuous and automatic.

## Key Requirements & Scope
1. **Orchestration Retrospective CLI (`spec-ops orchestrate retrospect`)**:
   - Parses recent session artifacts, preflight failure logs, and `.worktrees/*/.security-audit.log` files.
   - Detects recurrent invariant breaches across 5 failure categories:
     1. Mock backdoors / private internal tampering (ADR-0003)
     2. File length limit violations (ADR-0002)
     3. Diff secret / high-entropy credential scanner triggers (ADR-0019)
     4. Unstaged dependency lockfile drifts (ADR-0018)
     5. DAG dependency cycle deadlocks (ADR-0017)
2. **Automated Remediation Task Synthesis**:
   - Synthesizes fully-formed PMaC task specifications in `docs/project/backlog/proposed/` linked to governing ADRs and PRDs.
   - Formats failure context and negative prompt constraints (`failure_history`) according to ADR-0020.
3. **Orchestration Health Summary (`spec-ops orchestrate health`)**:
   - Displays real-time pass/fail rates of recent agent worktree attempts.
   - Flags stalled worktrees and unaddressed orchestration bugs.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: New orchestration retrospective module in `src/spec_ops/worker/retrospective.py` must stay strictly under 400 lines (ADR-0002).
- **Dogfooding Failure Invariant**: Every orchestration failure must synthesize an actionable task file under `docs/project/backlog/proposed/`.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/worker/retrospective.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Retrospective Detection of Orchestration Failures
```gherkin
Given recent worktree failure logs containing secret scanner leak alerts or mock backdoor errors
When the engineer runs "spec-ops orchestrate retrospect"
Then the failure patterns are categorized by invariant ID
And high-priority remediation tasks are scaffolded in "docs/project/backlog/proposed/"
```

### Scenario 2: Retrospective Negative Prompt Constraint Hydration
```gherkin
Given a proposed remediation task scaffolded by the retrospective engine
When the task frontmatter is inspected
Then the failure history records the breached invariant and negative prompt guidance
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that any arbitrary error log string is parsed deterministically without exceptions and mapped to known invariant categories or generic fallback.
