---
id: '0012'
title: GitHub Actions CI Quality Gate and Preflight Template
status: Complete
created: 2026-09-29
completed: 2026-09-29
dependencies:
  - TASK-0005
governing_adrs:
  - ADR-0002
  - ADR-0004
governing_prds:
  - PRD-0001
governing_stories:
  - US-0002
target_bc: scaffold
---

# TASK-0012: GitHub Actions CI Quality Gate and Preflight Template

## Summary
Provide automated GitHub Actions workflow scaffolding (`.github/workflows/ci.yml`) enforcing `spec-ops health`, test suite execution, and file length invariant verification on pull requests and pushes.

## Definition of Done
1. Scaffold option to emit `.github/workflows/ci.yml`.
2. Workflow runs `uv run spec-ops health` and `uv run pytest`.
3. Workflow verifies that no PR introduces files >500 lines or breaks PRIORITY.md sync.
4. SpecOps' own repository configured with this workflow.

## Completion Summary
- Created [`src/spec_ops/scaffold/ci_workflow.py`](../../../src/spec_ops/scaffold/ci_workflow.py) generating an opinionated `.github/workflows/ci.yml` that installs `uv`, runs `uv sync`, checks lockfile integrity with `uv lock --check`, verifies health invariants with `uv run spec-ops health`, and runs `uv run pytest`.
- Integrated CI workflow generation into `init_project` in [`src/spec_ops/scaffold/init.py`](../../../src/spec_ops/scaffold/init.py).
- Scaffolding `.github/workflows/ci.yml` directly in the SpecOps repository.
- Added comprehensive unit tests in [`tests/test_scaffold.py`](../../../tests/test_scaffold.py).
- Fixed worker command invocation formatting (`build_agent_cmd`) to safely handle quotes and multiline prompts without shell interpolation issues, and verified `.task-prompt.md` exclusion and cleanup.
- Verified 100% test pass rate and 0 file invariant violations (<500 lines).
