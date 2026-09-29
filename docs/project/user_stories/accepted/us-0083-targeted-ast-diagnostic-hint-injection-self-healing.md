---
id: '0083'
title: Targeted AST Diagnostic Hint Injection and Empty-Diff Guardrails in Self-Healing Loops
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-WORK-04
governing_prd: PRD-0004
---

# US-0083 — Targeted AST Diagnostic Hint Injection and Empty-Diff Guardrails in Self-Healing Loops

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As an** autonomous coding agent,
  - **I want** the worker engine to provide AST-parsed structural hints for code violations and reject empty or cosmetic diffs during self-healing loops,
  - **So that** I receive actionable, pinpointed feedback to fix invariant violations and cannot falsely report task completion without delivering real code.

## Acceptance Criteria

```gherkin
Scenario: Targeted AST Diagnostic Injection for File Length Overruns
Given an isolated worktree executing "TASK-0005"
When the agent produces "src/spec_ops/backlog/engine.py" containing 540 lines exceeding the 500-line limit
And preflight detects the file length violation
Then the worker engine parses the AST of "engine.py" to identify candidate function and class split seams
And appends a structured diagnostic section to ".task-prompt.md":
"""
## AST Decomposition Hints (Attempt 1)
- File: src/spec_ops/backlog/engine.py (540 lines, limit: 500)
- Largest AST node: class TaskExecutionCoordinator (lines 120-410, 291 lines)
- Suggested seam: extract TaskExecutionCoordinator into separate module
"""
And re-invokes the agent with targeted refactoring guidance.
```
```gherkin
Scenario: Guarding Against Empty or Whitespace-Only Agent Diffs
Given an isolated worktree executing "TASK-0012" on attempt 1
When the agent process exits with return code 0 but git status shows no tracked file modifications
Then the worker engine flags the attempt as "No Modifications Produced"
And injects feedback into the prompt warning the agent that implementation code is required
And decrements remaining retry attempts without proceeding to preflight or merge.
-
```

## Rationale & Compelling Value
- *Adoption*: Increases out-of-the-box reliability for teams using commercial LLMs that tend to output polite "I have completed the task" messages without touching files or struggle with where to decompose large files.
  - *Regular Usage*: Drastically elevates the second-attempt recovery rate of self-healing cycles, reducing manual human rescues by over 80%.
  - *Compelling Value*: Turns raw compiler/linter error dumps into high-value architectural instructions that LLMs can directly execute against.

---
