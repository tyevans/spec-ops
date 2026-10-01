---
id: TASK-0179
title: Ensure sys.path Includes Workspace Root and src in Property Test Runner Discovery
status: Proposed
target_bc: core
dependencies: []
---

## Summary
In `src/spec_ops/core/properties_runner.py`, `discover_property_tests` attempts to dynamically load test modules via `importlib.util.spec_from_file_location` and `spec.loader.exec_module(module)`.

However:
1. Neither the project `root_dir` nor `root_dir / "src"` is ensured in `sys.path`, causing test modules that import the local library under test (e.g. `import my_pkg` or `from my_pkg.domain import ...`) to fail with `ImportError`.
2. The dynamic loader catches `except Exception: continue` without logging or surfacing the import error, causing the command to report `Discovered 0 property test suite(s)` without indicating why files failed to import.

## Requirements
1. Add `str(root)` and `str(root / "src")` (if existing) to `sys.path` before scanning test files.
2. Log or surface import warnings/errors when a user explicitly specifies a target path that fails to load.
