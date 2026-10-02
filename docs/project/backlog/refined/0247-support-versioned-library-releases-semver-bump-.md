---
id: '0247'
title: Support Versioned Library Releases, SemVer Bump Workflows, and Git Tag Orchestration
status: Refined
governing_adrs:
- ADR-0001
- ADR-0004
governing_prds:
- PRD-0001
- PRD-0003
governing_stories:
- US-0122
target_bc: core
persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
---

# TASK-0247: Support Versioned Library Releases, SemVer Bump Workflows, and Git Tag Orchestration

## Summary
Introduce first-class support for versioned software libraries and SDKs in the `spec-ops release` subsystem, enabling automated SemVer version bumping, multi-file version declaration synchronization (e.g. `pyproject.toml` and `__init__.py`), changelog compilation, and cryptographic git tag management.

## Problem Statement & Context
SpecOps today focuses primarily on continuous application deployment and milestone burndown decks (`spec-ops release notes`, `velocity`, `verify`). When managing reusable libraries (such as `redstring`), maintainers must manually update language manifests, ensure dual-declaration agreement across files, and cut git tags out-of-band. SpecOps lacks commands to:
1. Validate SemVer bump progression (`patch`, `minor`, `major`) and flag breaking changes against ADRs/public API contracts.
2. Synchronize version declarations across multiple project files (guarded by drift detection tests).
3. Cut release branches and trigger tag-driven CI publishing pipelines (such as PyPI/OIDC).

## Proposed Solution & Remediation Plan
1. Add `[project.versioning]` configuration to `specops.toml` defining version file targets (e.g. `pyproject.toml:project.version`, `src/<pkg>/__init__.py:__version__`).
2. Implement `spec-ops release bump --patch|minor|major` or `spec-ops release cut --version <X.Y.Z>` to atomically update version declarations, execute preflight test suites, and generate release commit trailers.
3. Provide `spec-ops release tag` to cryptographically sign and push release tags matching the verified release manifest.
4. Support clean changelog splicing into existing `CHANGELOG.md` alongside release notes.

## Definition of Done (Blackbox Frontdoor TDD)
1. CLI command `spec-ops release bump` and `spec-ops release cut` exercised via blackbox CLI tests.
2. Multi-file version synchronization verified against test project with dual declarations.
3. Git tag creation and signature verification pass preflight checks.
4. Code strictly adheres to ADR-0002 (<500 lines limit).

## Acceptance Criteria

```gherkin
Scenario: Verify Support Versioned Library Releases, SemVer Bump Workflows, and Git Tag Orchestration
  Given the system is initialized and ready
  When the user executes the workflow for "Support Versioned Library Releases, SemVer Bump Workflows, and Git Tag Orchestration"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/core/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).
