---
id: '0091'
title: Sub-Second Incremental Invariant Diagnostics for Editor and IDE Feedback
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-RESC-05
governing_prd: PRD-0004
---

# US-0091 — Sub-Second Incremental Invariant Diagnostics for Editor and IDE Feedback

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As a** human software engineer writing code in my local IDE (VS Code, Neovim, Zed),
  - **I want** a single-file invariant diagnostic command (`spec-ops check --fast --file <path>`) that executes in under 50 milliseconds,
  - **So that** my editor can run it on file-save to flag file-length warnings (>=400 lines), hard violations (>=500 lines), and bounded context boundary breaches inline as real-time diagnostics before I ever run `git commit`.

## Acceptance Criteria

```gherkin
Scenario: Blazing fast single-file invariant evaluation on save
Given an open source file "src/spec_ops/backlog/curator.py" with 415 lines
When the editor executes "spec-ops check --fast --file src/spec_ops/backlog/curator.py --format json"
Then the process exits in under 50 milliseconds with code 0
And the stdout returns a diagnostic payload:
"""
{
"file": "src/spec_ops/backlog/curator.py",
"lines": 415,
"status": "warning",
"threshold": 400,
"limit": 500,
"message": "Approaching file length limit (415/500 lines). Consider decomposing into submodules."
}
"""
```
```gherkin
Scenario: Immediate diagnostic error on hard invariant violation
Given a developer adds code making "src/spec_ops/core/graph.py" reach 508 lines
When the editor runs "spec-ops check --fast --file src/spec_ops/core/graph.py --format sarif"
Then the process exits with code 1
And outputs a SARIF diagnostic indicating a hard error on line 501:
"Hard Invariant Violation: File exceeds 500 lines (508 lines). Commit will be rejected."
```
```gherkin
Scenario: Bounded context boundary import validation
Given a file in "src/spec_ops/visualizer/generator.py" within bounded context "visualizer"
When the file introduces an unauthorized direct import from "src/spec_ops/backlog/worker.py"
Then "spec-ops check --fast --file src/spec_ops/visualizer/generator.py" flags an architectural breach:
"Bounded Context Violation: 'visualizer' cannot directly import internal module 'backlog.worker' (governed by ADR-0007)."
-
```

## Rationale & Compelling Value
- **Adoption**: Moves compliance feedback from slow pre-commit hooks and remote CI directly into the developer's typing loop.
  - **Regular Usage**: Runs automatically hundreds of times per day on every save event with zero perceived latency.
  - **Compelling Value**: Enforces architectural invariants (ADR-0002, ADR-0007) painlessly; developers never get surprised by pre-commit or CI rejections.

---
