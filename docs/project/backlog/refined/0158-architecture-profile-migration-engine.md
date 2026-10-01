---
id: 0158
title: Living Architecture Profile Migration Engine and Schema Evolvability
status: Refined
dependencies:
- TASK-0077
- TASK-0078
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
governing_prds:
- PRD-0005
governing_stories:
- US-0106
target_bc: core
---

# TASK-0158: Living Architecture Profile Migration Engine and Schema Evolvability

## Summary
Implement an architectural profile migration engine and schema evolvability validator (`src/spec_ops/core/profile_migration.py`). Governed by ADR-0001 and PRD-0005, this engine validates project architectural profile configurations (`.spec-ops/profile.yaml`), checks backward compatibility against semantic schema versions, and automatically upgrades legacy schema definitions (`spec-ops profile migrate`).

## Problem Statement & Context
As SpecOps evolves across minor and major versions, architectural profile definitions and rule specifications gain new capabilities and field schemas. Projects configured on older schema revisions need non-destructive automated migrations to adopt new governance features without manual YAML editing or syntax errors.

## Key Requirements & Scope
1. **Profile Migration Engine (`src/spec_ops/core/profile_migration.py`)**:
   - Defines schema migration steps across profile versions (e.g. v1 -> v2).
   - Validates profile YAML against the target schema specification.
   - Applies forward migrations while preserving custom user overrides and comments.
   - Detects incompatible configuration keys and provides remediation recommendations.
2. **Profile Migration CLI (`spec-ops profile migrate [--check] [--target-version <ver>] [--dry-run]`)**:
   - Inspects active configuration, detects version drift, and executes schema migration.
   - When `--check` is specified, exits with code 0 if up to date, or code 1 if migration is required.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate verifying public CLI interface and migration pipeline.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Migration engine module in `src/spec_ops/core/profile_migration.py` must stay strictly under 400 lines (ADR-0002).
- **Domain-Driven Design (ADR-0007)**: Core migration domain models isolated from CLI formatting and I/O.
- **Mutation Testing Scope**: Target module `src/spec_ops/core/profile_migration.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Migrating legacy profile configuration to current schema
```gherkin
Given a project configured with a legacy v1 profile.yaml
When the developer runs spec-ops profile migrate
Then the configuration is upgraded to the current schema version
And all custom project rules and frontmatter settings are preserved intact
```

### Scenario 2: Checking profile version currency
```gherkin
Given a project profile already synchronized with the current schema
When the developer runs spec-ops profile migrate with check flag
Then the command confirms profile is up to date
And terminates with exit code 0
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that migrating any valid legacy profile configuration produces a schema-valid target profile without data loss or key corruption.
