---
id: 0118
title: Resolve High-Entropy Test Literals Triggering Security Health Scanner in Multi-Platform
  CI Properties
status: Complete
dependencies:
- TASK-0083
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0009
- ADR-0010
governing_prds:
- PRD-0005
governing_stories:
- US-0069
target_bc: scaffold
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T00:22:42.585672+00:00'
---

# TASK-0118: Resolve High-Entropy Test Literals Triggering Security Health Scanner in Multi-Platform CI Properties

## Summary
Refactor Hypothesis generative property tests in `tests/test_ci_multi_properties.py` to replace long hardcoded alphanumeric alphabet strings with composable Hypothesis character strategies (`st.characters(...)`). This prevents false-positive high-entropy secret detection by `spec-ops health --security` during preflight and rescue stages.

## Problem Statement & Context
During dogfooding of `spec-ops rescue TASK-0083 --complete`, the preflight stage `security` (`spec-ops health --security`) failed due to high-entropy string literals detected in `tests/test_ci_multi_properties.py` at lines 17, 26, 65, and 74:
- `alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"`
- `alphabet="abcdefghijklmnopqrstuvwxyz0123456789"`

The security scanner inspects source and test files for high-entropy strings and credential patterns (ADR-0010, ADR-0019). Long contiguous character set definitions exceed entropy thresholds and trigger false-positive leak alerts. Per the SpecOps SDLC Orchestration Failure Protocol in `AGENTS.md`, this orchestration failure was documented as an actionable task and resolved by migrating test strategies to native Hypothesis character filters.

## User Stories & Scenarios Satisfied
- **US-0069: Multi-Platform CI/CD Pipeline Scaffolding Across GitHub Actions and GitLab CI**
  - *Scenario: Generative property invariant verification without secret scanner false-positives*
    - Given a suite of generative property tests verifying CI pipeline scaffolding
    - When `uv run spec-ops health --security` scans test files
    - Then zero high-entropy secret leak warnings are raised
    - And all Hypothesis generative tests pass with valid character spaces.

## Architectural Invariants & Seams
- **Security & Secret Scanner Invariant (ADR-0010, ADR-0019)**: Zero credential or high-entropy string leaks in repository source or test files.
- **Hypothesis Generative Property Invariant (ADR-0009)**: Generative strategies define valid inputs using unicode/ASCII character categories without raw literal entropy.
- **File Length Limit (<500 lines)**: `tests/test_ci_multi_properties.py` remains under 150 lines (ADR-0002).

## Definition of Done (Blackbox Frontdoor TDD)
1. Replace all hardcoded alphabet strings in `tests/test_ci_multi_properties.py` with `st.characters(...)` strategies.
2. `uv run spec-ops health --security` passes with 0 secret leaks detected.
3. `uv run pytest tests/test_ci_multi_properties.py` passes all generative test cases cleanly.
