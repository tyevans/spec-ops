---
id: '0076'
title: Specification Frontmatter Schema Validation and Automated In-Place Migration
status: Refined
dependencies:
- TASK-0058
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0017
target_bc: core
claimed_by: worker-3
branch: feat/0076-specification-frontmatter-schema-validat
---

# TASK-0076: Specification Frontmatter Schema Validation and Automated In-Place Migration

## Summary
Implement automated specification frontmatter schema validation and safe in-place migration (`spec-ops schema validate`, `spec-ops schema migrate [--dry-run] [--in-place]`). Audit specification frontmatter across `docs/project/` against active Pydantic schema models, report line and column pointers for malformed YAML or missing required fields, and provide safe atomic frontmatter rewrites that preserve Markdown body content, headings, tables, and fenced code blocks byte-for-byte.

## Problem Statement & Context
As PMaC schemas evolve across an organization (adding required fields, renaming statuses, or refining metadata arrays), specifications authoring drift occurs. Manual frontmatter updates across dozens or hundreds of Markdown files are tedious, error-prone, and risk stripping out markdown formatting or comments. SpecOps requires a dedicated schema validator and migration engine that performs dry-run diffing and safe in-place schema upgrades without risking documentation corruption.

## User Stories & Scenarios Satisfied
- **US-0017: Specification Frontmatter Schema Validation and Automated In-Place Migration**
  - *Scenario: Validating specification frontmatter against current schema*
    - Given specification documents in "docs/project/" containing valid YAML frontmatter matching current models
    - When the architect runs "spec-ops schema check"
    - Then the command exits with code 0 and reports "Schema Check Passed: All specification documents conform to schema v2.0".
  - *Scenario: Performing dry-run migration to inspect schema updates*
    - Given an older task document using legacy field "governing_adr: 0001" instead of "governing_adrs: ['ADR-0001']"
    - When the architect runs "spec-ops schema migrate --dry-run"
    - Then the command outputs a unified diff showing projected frontmatter transformations and leaves files on disk unmodified.
  - *Scenario: Executing in-place frontmatter migration preserving Markdown body contents*
    - Given an older task document with legacy frontmatter fields and a 100-line Markdown technical specification
    - When the architect runs "spec-ops schema migrate --in-place"
    - Then the YAML frontmatter is rewritten to the new schema format and the exact Markdown body, headings, and code blocks below the frontmatter are preserved byte-for-byte.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Schema validator in `src/spec_ops/core/schema_validator.py` and migration transformer in `src/spec_ops/core/migration.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that for any valid Markdown specification, `migrate(parse(spec))` preserves 100% of non-frontmatter body tokens verbatim (idempotent body preservation invariant).
- **Mutmut Mutation Scope**: Frontmatter parser and rewrite logic in `src/spec_ops/core/migration.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops schema check` audits all specification files in `docs/project/` against active Pydantic models, exiting with code 0 on compliance or code 1 with line/column diagnostic pointers if invalid.
2. Executing `spec-ops schema migrate --dry-run` displays a unified diff of proposed frontmatter upgrades without modifying disk state.
3. Executing `spec-ops schema migrate --in-place` rewrites outdated frontmatter fields atomically while preserving Markdown bodies, headings, tables, and fenced code blocks byte-for-byte.
4. Generative property tests with Hypothesis confirm idempotent body preservation across randomized Markdown documents.
5. All scenarios executed via `pytest-bdd` against CLI frontdoors with zero mock backdoors (ADR-0003, ADR-0006).
