---
id: '0047'
title: Targeted AST Diagnostic Hint Injection, Empty-Diff Guardrails, and Remote CI
  Repair Loop
status: Complete
dependencies:
- TASK-0012
- TASK-0046
governing_adrs:
- ADR-0002
- ADR-0003
- ADR-0004
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0083
- US-0033
target_bc: worker
---

# TASK-0047: Targeted AST Diagnostic Hint Injection, Empty-Diff Guardrails, and Remote CI Repair Loop

## Summary
Implement targeted AST-driven diagnostic hints for file length overruns, empty-diff and cosmetic modification guardrails in agent retry loops, and remote CI failure ingestion via `spec-ops worker ci-heal --task <task-id>` to ingest GitHub Actions step logs directly into worktree repair prompts.

## Problem Statement & Context
When autonomous agents exceed the 500-line limit or encounter complex syntax errors, raw compiler outputs give no hint about architectural modularization, causing agents to thrash or hallucinate repetitive broken fixes. Additionally, commercial LLMs frequently exit with zero modifications while claiming completion, consuming retry cycles fruitlessly. Furthermore, when remote CI fails on pull requests, agents lack automated mechanisms to pull remote log traces into the local worktree for immediate remediation.

## User Stories & Scenarios Satisfied
- **US-0083: Targeted AST Diagnostic Hint Injection and Empty-Diff Guardrails in Self-Healing Loops**
  - *Scenario: Targeted AST Diagnostic Injection for File Length Overruns*
  - *Scenario: Guarding Against Empty or Whitespace-Only Agent Diffs*
- **US-0033: Remote CI Failure Diagnostic Ingestion and In-Worktree Repair Loop**
  - *Scenario: Ingesting Failed GitHub Actions Log for Autonomous CI Repair*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: AST analyzer module in `src/spec_ops/worker/ast_analyzer.py` and CI repair coordinator in `src/spec_ops/worker/ci_repair.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated Python syntax trees assert that the AST analyzer reliably locates top-level classes and functions, computes accurate line ranges, and identifies the largest node without throwing AST parsing exceptions.
- **Mutmut Mutation Scope**: AST decomposition hint generation in `src/spec_ops/worker/ast_analyzer.py` and diff verification in `src/spec_ops/worker/ci_repair.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. When a source file exceeds 500 lines, the worker engine parses the AST, identifies candidate class/function extraction seams, and injects structured decomposition hints into `.task-prompt.md`.
2. If an agent process exits with code 0 but leaves working tree unmodified, the worker marks the attempt as "No Modifications Produced", injects warning feedback, and decrements retry count.
3. Executing `spec-ops worker ci-heal --task TASK-XXXX` queries GitHub CLI (`gh run view --log-failed`), extracts failure trace into `.task-prompt.md`, opens `.worktrees/<task-id>`, and prompts the agent to apply targeted repairs.
4. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
