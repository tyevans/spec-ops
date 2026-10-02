---
id: TASK-0178
title: Handle Missing Hypothesis Dependency Gracefully in Property Runner and Tool
  Installs
status: Complete
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0004
governing_prds:
- PRD-0003
governing_stories:
- US-0001
target_bc: core
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T02:48:10.380705+00:00'
commit_signature_status: SIGNED
allows_dependencies: true
has_signed_commits: true
---

## Summary
When running `spec-ops verify`, `src/spec_ops/cli/main.py` imports `src/spec_ops/core/properties_runner.py`, which unconditionally executes `from hypothesis import HealthCheck, settings` at module import time.

Because `hypothesis` is currently specified under `[dependency-groups] dev` rather than runtime `dependencies` or an optional extra in `pyproject.toml`, executing `spec-ops verify` from a standalone tool installation (`uv tool install spec-ops`) immediately crashes with `ModuleNotFoundError: No module named 'hypothesis'`.

## Requirements
1. In `src/spec_ops/core/properties_runner.py`, defer the import of `hypothesis` or catch `ImportError` gracefully, displaying a user-friendly error message guiding the user to install `hypothesis` or run via their environment (e.g., `uv run spec-ops verify` within their workspace virtualenv).
2. Consider adding `hypothesis` to runtime dependencies or an optional extra (`spec-ops[verify]`) in `pyproject.toml`.

## Acceptance Criteria

```gherkin
Scenario: Verify Handle Missing Hypothesis Dependency Gracefully in Property Runner and Tool Installs
  Given the system is initialized and ready
  When the user executes the workflow for "Handle Missing Hypothesis Dependency Gracefully in Property Runner and Tool Installs"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/core/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Scope & Architectural Invariants
- Target Bounded Context: `core` (single bounded context)
- Estimated Implementation Diff: <400 lines
- File Length Limit: all touched source files strictly <500 lines (ADR-0002).
