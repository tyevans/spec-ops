---
id: TASK-0180
title: Support Test Classes and Modern Hypothesis Method Attributes in Property Runner Discovery
status: Proposed
target_bc: core
dependencies: []
---

## Summary
In `src/spec_ops/core/properties_runner.py`, `discover_property_tests` only inspects module-level attributes matching `attr_name.startswith("test_")`.

This causes tests structured within test classes (e.g. `class TestIntervalProperties: def test_...`) or standard `pytest` class fixtures to be completely ignored.

Additionally, detection of Hypothesis tests uses:
`is_hypo = getattr(fn, "is_hypothesis_test", False) or hasattr(fn, "hypothesis") or "property" in attr_name`
which does not detect modern Hypothesis decorators (which attach `_hypothesis_internal_use_raw_state` or `@given` wrapped attributes) unless `"property"` is literally in the function name.

## Requirements
1. In `discover_property_tests`, inspect both module-level test functions and methods of test classes (`class Test...:`).
2. Expand Hypothesis test detection to inspect `getattr(fn, "_hypothesis_internal_use_raw_state", None)` or check if `@given` wrapped the callable.
