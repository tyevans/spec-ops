---
id: '0151'
title: AST Self-Healing Diagnostic Injector for In-Worktree Preflight Recovery
status: Complete
dependencies:
- TASK-0085
- TASK-0114
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0004
governing_prds:
- PRD-0004
governing_stories:
- US-0085
- US-0086
target_bc: worker
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0151: AST Self-Healing Diagnostic Injector for In-Worktree Preflight Recovery

## Summary
Implement the AST self-healing diagnostic injector for autonomous worktree preflight recovery (`src/spec_ops/worker/diagnostic_injector.py`). Fulfilling ADR-0004 and PRD-0004, this engine parses preflight failure outputs (syntax errors, pytest assertion traces, line length warnings), resolves exact AST node positions, and synthesizes structured healing prompts and targeted fix hints directly into the worker's retry loop.

## Problem Statement & Context
When autonomous agents fail preflight tests or lint gates, feeding raw terminal tracebacks back into the agent context often results in repetitive, unfocused hallucinated changes. Agents lack structural visibility into which exact AST nodes, function signatures, or line ranges triggered the failure. Providing targeted AST node diagnostics and concrete invariant reminders drastically accelerates self-healing convergence.

## Key Requirements & Scope
1. **Diagnostic Parser & AST Mapper (`src/spec_ops/worker/diagnostic_injector.py`)**:
   - Parses pytest, python syntax error, and `spec-ops health` diagnostic outputs.
   - Maps stack traces and line numbers to precise AST nodes (functions, classes, import statements).
   - Generates contextual diagnostic cards: failing assertion, target node source snippet, breached invariant rule.
2. **Retry Prompt Synthesis**:
   - Synthesizes actionable healing instructions injected into the worker's next attempt prompt.
   - Embeds explicit prohibitions preventing known anti-patterns (ADR-0020).
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Diagnostic injector module in `src/spec_ops/worker/diagnostic_injector.py` must stay strictly under 400 lines (ADR-0002).
- **Targeted Diagnostic Invariant (ADR-0004)**: Diagnostics must pinpoint exact AST nodes without synthesizing hallucinated code modifications.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/worker/diagnostic_injector.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Mapping preflight failure trace to target AST node
```gherkin
Given a preflight failure output reporting an AssertionError at line 42 of a source file
When the diagnostic injector processes the failure log
Then the failing function AST node is identified
And a structured diagnostic card includes the node signature and source context
```

### Scenario 2: Injecting actionable fix hints into worker retry prompt
```gherkin
Given a worktree preflight failure violating file length limit ADR-0002
When the diagnostic injector synthesizes retry guidance
Then the retry prompt highlights the exact oversized module
And provides decomposition guidance without modifying source files directly
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary traceback string, diagnostic parsing never raises unhandled exceptions and either extracts valid file/line coordinates or returns a graceful unmapped diagnostic summary.
