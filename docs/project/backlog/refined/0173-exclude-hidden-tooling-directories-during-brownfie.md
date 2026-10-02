---
id: '0173'
title: Exclude Hidden Tooling Directories During Brownfield Debt Scanning
status: Refined
governing_adrs:
- ADR-0001
- ADR-0002
governing_prds:
- PRD-0003
governing_stories:
- US-0001
target_bc: core
persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
---

# TASK-0173: Exclude Hidden Tooling Directories During Brownfield Debt Scanning

## Summary
`spec-ops adopt` and `spec-ops health` scan source files across the repository to determine line lengths and grandfathered debt baselines. In `src/spec_ops/core/debt_baseline.py` (and related scanners in `health_handler.py`, `modularity_debt.py`, and `anti_mock.py`), `EXCLUDE_DIRS` only excludes a hardcoded list of directories (`.git`, `.venv`, `.pytest_cache`, `.worktrees`, etc.). Hidden directories such as `.claude/`, `.superpowers/`, `.cursor/`, `.vscode/`, or temporary worktrees in `.claude/worktrees/` are not excluded, causing legacy or duplicate files inside hidden tool workspaces to be baselined into `grandfathered_debt.json` and generating noisy refactoring tasks.

## Problem Statement & Context
1. In `src/spec_ops/core/debt_baseline.py`:
   ```python
   EXCLUDE_DIRS = {
       ".git",
       ".venv",
       "venv",
       "node_modules",
       "dist",
       "site",
       "storybook-static",
       "__pycache__",
       ".pytest_cache",
       ".ruff_cache",
       "mutants",
       ".mutmut-cache",
       ".hypothesis",
       ".worktrees",
   }
   ```
2. When `scan_and_record_grandfathered_debt()` traverses `root.rglob("*")`, any file under `.claude/worktrees/...` is included because `.claude` is not in `EXCLUDE_DIRS`.
3. In contrast, `src/spec_ops/core/arch_checker.py` explicitly ignores directories starting with `.`:
   ```python
   if child.is_dir() and not child.name.startswith(".") and child.name not in EXCLUDE_DIRS:
   ```
4. Scanners should uniformly exclude any directory component that starts with `.` (hidden directories) or explicitly include `.claude`, `.cursor`, `.vscode`, `.idea`, etc.

## Proposed Fix
1. In `src/spec_ops/core/debt_baseline.py`, update directory filtering:
   ```python
   if any(part in EXCLUDE_DIRS or (part.startswith(".") and part != ".") for part in rel_p.parts):
       continue
   ```
2. Apply the same check in `health_handler.py`, `modularity_debt.py`, `anti_mock.py`, and `git_hooks.py` to ensure consistent file scanning across all commands.

## Definition of Done (Blackbox Frontdoor TDD)
1. Unit test verifying that files under `.claude/` or other dot-directories are not included in `scan_and_record_grandfathered_debt()`.
2. Running `spec-ops adopt` on a codebase with `.claude/worktrees/` does not grandfather files inside `.claude/`.
3. All source files strictly under 500 lines.

## Acceptance Criteria

```gherkin
Scenario: Verify Exclude Hidden Tooling Directories During Brownfield Debt Scanning
  Given the system is initialized and ready
  When the user executes the workflow for "Exclude Hidden Tooling Directories During Brownfield Debt Scanning"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Scope & Architectural Invariants
- Target Bounded Context: `core` (single bounded context)
- Estimated Implementation Diff: <400 lines
- File Length Limit: all touched source files strictly <500 lines (ADR-0002).
