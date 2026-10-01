---
id: '0172'
title: Fix Numbering Integrity Regex Collision on Non-Numeric Stems and Embedded Digits
status: Proposed
governing_adrs:
- ADR-0001
- ADR-0002
target_bc: core
---

# TASK-0172: Fix Numbering Integrity Regex Collision on Non-Numeric Stems and Embedded Digits

## Summary
In `src/spec_ops/core/numbering.py`, `audit_numbering_uniqueness` uses an unanchored regex `r"(?:task-)?(\d+)"` when extracting numbers from task filenames. Because `(?:task-)?` is optional and unanchored, `re.search` matches the first digit anywhere in any filename stem. In brownfield codebases with refactoring tasks like `TASK-REFACTOR-redstring-graph-adapters-neo4j.md` or files containing version numbers/names with digits, the digit `4` in `neo4j` is matched as task number `4` (`TASK-0004`), causing spurious duplicate collision errors during `spec-ops health`.

## Problem Statement & Reproduction
1. In `src/spec_ops/core/numbering.py`:
   ```python
   groups: list[tuple[str, Path, str, str]] = [
       ("adrs", project_docs / "adrs", "ADR", r"adr-(\d+)"),
       ("prds", project_docs / "product", "PRD", r"(?:prd-)?(\d+)"),
       ("tasks", project_docs / "backlog", "TASK", r"(?:task-)?(\d+)"),
       ("stories", project_docs / "user_stories", "US", r"(?:us-)?(\d+)"),
   ]
   ```
2. When scanning `docs/project/backlog/proposed/TASK-REFACTOR-...neo4j.md`, `extract_numbers_for_file` calls:
   ```python
   m_stem = re.search(stem_regex, file_path.stem, re.IGNORECASE)
   ```
3. Since `(?:task-)?` can match 0 characters at index 0..N, `re.search` finds `4` from `neo4j`.
4. If multiple refactoring tasks exist for files with `neo4j` (or other files with the same digit), `spec-ops health` fails with:
   ```text
   ❌ 1 Numbering Collision(s) Detected:
      - Group 'TASKS': TASK-0004 duplicated across 6 files
   ```

## Proposed Fix
1. Anchor task stem regex to start or explicit prefixes:
   Use `r"^(?:task-)?(\d+)"` or `r"(?:^|[\b_-])task-(\d+)"` rather than unanchored `r"(?:task-)?(\d+)"`.
2. Skip non-numeric task stems (such as `TASK-REFACTOR-*` or `TASK-SPLIT-*`) from numeric ID indexing, or handle non-numeric slugs separately so arbitrary embedded digits in file paths do not get treated as sequential task numbers.
3. Apply similar anchoring to PRDs (`r"^(?:prd-)?(\d+)"`) and stories (`r"^(?:us-)?(\d+)"`).

## Definition of Done (Blackbox Frontdoor TDD)
1. Add unit/property tests in `tests/test_numbering.py` or equivalent verifying that `TASK-REFACTOR-redstring-graph-adapters-neo4j.md` does not extract task number `4`.
2. Ensure `spec-ops health` passes without numbering collision false positives when refactoring tasks exist.
3. All source files strictly under 500 lines.
