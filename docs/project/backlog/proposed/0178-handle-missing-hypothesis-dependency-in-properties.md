---
id: TASK-0178
title: Handle Missing Hypothesis Dependency Gracefully in Property Runner and Tool Installs
status: Proposed
target_bc: core
allows_dependencies: true
dependencies: []
---

## Summary
When running `spec-ops verify`, `src/spec_ops/cli/main.py` imports `src/spec_ops/core/properties_runner.py`, which unconditionally executes `from hypothesis import HealthCheck, settings` at module import time.

Because `hypothesis` is currently specified under `[dependency-groups] dev` rather than runtime `dependencies` or an optional extra in `pyproject.toml`, executing `spec-ops verify` from a standalone tool installation (`uv tool install spec-ops`) immediately crashes with `ModuleNotFoundError: No module named 'hypothesis'`.

## Requirements
1. In `src/spec_ops/core/properties_runner.py`, defer the import of `hypothesis` or catch `ImportError` gracefully, displaying a user-friendly error message guiding the user to install `hypothesis` or run via their environment (e.g., `uv run spec-ops verify` within their workspace virtualenv).
2. Consider adding `hypothesis` to runtime dependencies or an optional extra (`spec-ops[verify]`) in `pyproject.toml`.
