---
id: '0053'
title: 'Architectural Spike: Anti-Loop Worktree Failure Memory Schema and Negative Prompt Synthesis'
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0052
governing_adrs:
  - ADR-0001
  - ADR-0003
  - ADR-0007
  - ADR-0009
governing_prds:
  - PRD-0004
governing_stories:
  - US-0089
target_bc: rescue
---

# TASK-0053: Architectural Spike: Anti-Loop Worktree Failure Memory Schema and Negative Prompt Synthesis

## Summary
Conduct an architectural spike to design, evaluate, and benchmark a lossless YAML frontmatter schema for capturing failure post-mortems (`failure_history`, `failed_invariants`, `reason`) inside PMaC task specifications when a worktree is reset. Prototype round-trip markdown parsing to ensure zero formatting corruption, evaluate automated queue demotion mechanics from `refined/` to `proposed/`, and design the synthesis of explicit negative prompt constraints (`## Prior Attempt Failures & Anti-Patterns (DO NOT REPEAT)`) during `.task-prompt.md` hydration. Author findings into ADR-0011: Version-Controlled Failure Post-Mortems and Anti-Loop Memory.

## Problem Statement & Context
When human developers wipe an irreparably broken agent worktree (`spec-ops rescue reset`), the lessons of that failure are discarded. If the task is reset to `refined/` without memory, the next autonomous agent pulls the task and attempts the exact same flawed approach (e.g. creating private test mocks violating ADR-0003, monkey-patching libraries, or hallucinating files). SpecOps requires an institutional memory schema embedded directly in the task's markdown frontmatter to synthesize negative prompt constraints that break repetitive failure loops.

## User Stories & Scenarios Satisfied
- **US-0089: Safe Worktree Discard with Anti-Loop Failure Memory and Task Reset**
  - *Scenario: Discarding worktree and capturing failure post-mortem into task frontmatter*
  - *Scenario: Automatic demotion to proposed stage when specification ambiguity is flagged*
  - *Scenario: Hydrating subsequent worker prompts with negative constraints from failure history*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Spike prototype in `src/spec_ops/rescue/memory_spike.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary markdown task files and repeated reset iterations assert that frontmatter serialization and deserialization is perfectly round-trippable: task title, dependencies, and markdown body remain byte-identical while `failure_history` entries append monotonically without data corruption.
- **Mutmut Mutation Scope**: Frontmatter mutation and negative prompt synthesis logic in `src/spec_ops/rescue/memory_spike.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Spike proves lossless round-trip persistence of `failure_history` list items in task frontmatter across multiple simulated failure-reset cycles.
2. Prototype verifies automated demotion logic: passing `--demote` moves the task file from `refined/` to `proposed/` and updates `PRIORITY.md` safely.
3. Prototype validates negative prompt generation: reading `failure_history` produces a structured section `## Prior Attempt Failures & Anti-Patterns (DO NOT REPEAT)` in `.task-prompt.md` with explicit prohibitions.
4. Benchmark demonstrates frontmatter update executes in under 15ms.
5. Findings and final frontmatter schema specification published into `docs/project/adrs/proposed/adr-0011-version-controlled-failure-post-mortems-and-anti-loop-memory.md`.
