---
id: TASK-0179
title: Ensure sys.path Includes Workspace Root and src in Property Test Runner Discovery
status: Refined
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
---

## Summary
In `src/spec_ops/core/properties_runner.py`, `discover_property_tests` attempts to dynamically load test modules via `importlib.util.spec_from_file_location` and `spec.loader.exec_module(module)`.

However:
1. Neither the project `root_dir` nor `root_dir / "src"` is ensured in `sys.path`, causing test modules that import the local library under test (e.g. `import my_pkg` or `from my_pkg.domain import ...`) to fail with `ImportError`.
2. The dynamic loader catches `except Exception: continue` without logging or surfacing the import error, causing the command to report `Discovered 0 property test suite(s)` without indicating why files failed to import.

## Requirements
1. Add `str(root)` and `str(root / "src")` (if existing) to `sys.path` before scanning test files.
2. Log or surface import warnings/errors when a user explicitly specifies a target path that fails to load.

## Acceptance Criteria

```gherkin
Scenario: Verify Ensure sys.path Includes Workspace Root and src in Property Test Runner Discovery
  Given the system is initialized and ready
  When the user executes the workflow for "Ensure sys.path Includes Workspace Root and src in Property Test Runner Discovery"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/core/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).

## Scope & Architectural Invariants
- Target Bounded Context: `core` (single bounded context)
- Estimated Implementation Diff: <400 lines
- File Length Limit: all touched source files strictly <500 lines (ADR-0002).
