---
id: '0020'
title: Git Pre-Commit Hook Scaffolding and Proactive Invariant Warnings
status: Complete
created: 2026-09-29
completed: 2026-09-29
dependencies:
- TASK-0005
governing_adrs:
- ADR-0002
governing_prds:
- PRD-0001
governing_stories:
- US-0002
target_bc: backlog
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0020: Git Pre-Commit Hook Scaffolding and Proactive Invariant Warnings

## Summary
Add pre-commit hook scaffolding to `spec-ops init` and enhance `spec-ops health` with a proactive warning threshold (e.g., >400 lines) to alert developers before files breach the 500-line limit.

## Definition of Done (Blackbox Frontdoor TDD)
1. `spec-ops health` reports both hard violations (>500 lines) and proactive warnings (>400 lines).
2. `spec-ops init` scaffolds `.pre-commit-config.yaml` with passing hook validation.
3. Tests verify hook configuration and warning thresholds.

## Completion Summary
- Added `file_warning_threshold: int = 400` to [`ArchitectureSettings`](../../../src/spec_ops/config/models.py) and configured loader parsing.
- Enhanced [`HealthChecker`](../../../src/spec_ops/backlog/health.py) with proactive file length warning scanning, returning `warnings: list[FileLengthWarning]` on [`HealthCheckReport`](../../../src/spec_ops/backlog/health.py) for files between 400 and 500 lines without breaking build health.
- Updated `spec-ops health` CLI output in [`src/spec_ops/cli/main.py`](../../../src/spec_ops/cli/main.py) to prominently display proactive refactoring alerts with warning thresholds.
- Created [`src/spec_ops/scaffold/pre_commit.py`](../../../src/spec_ops/scaffold/pre_commit.py) generating opinionated `.pre-commit-config.yaml` with Ruff formatters and `uv run spec-ops health` local quality gates.
- Added `--pre-commit` and `--no-pre-commit` scaffolding flags to `spec-ops init` and [`init_project`](../../../src/spec_ops/scaffold/init.py).
- Configured `.pre-commit-config.yaml` directly in the `spec-ops` repository.
- Decomposed visualizer client scripts into [`gantt_script.py`](../../../src/spec_ops/visualizer/gantt_script.py) and [`views_script.py`](../../../src/spec_ops/visualizer/views_script.py), ensuring every single source file in `spec-ops` is strictly under 400 lines (0 warnings, 0 violations).
- Added comprehensive unit tests in [`tests/test_backlog_health_and_curator.py`](../../../tests/test_backlog_health_and_curator.py) and [`tests/test_scaffold.py`](../../../tests/test_scaffold.py).
