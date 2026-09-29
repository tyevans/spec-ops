---
id: '0017'
title: Specification Frontmatter Schema Validation and Automated In-Place Migration
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-SCH-01
governing_prd: PRD-0005
---

# US-0017 — Specification Frontmatter Schema Validation and Automated In-Place Migration

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect,  
**I want** to validate and automatically migrate YAML frontmatter in all specification documents against evolving schema versions,  
**So that** changes to SpecOps metadata structures or custom enterprise frontmatter fields never corrupt existing Markdown documentation or break downstream parser tools.

## Acceptance Criteria

```gherkin
Scenario: Validating specification frontmatter against current schema
Given specification documents in "docs/project/" containing valid YAML frontmatter matching current models
When the architect runs "spec-ops schema check"
Then the command exits with code 0
And reports "Schema Check Passed: All specification documents conform to schema v2.0".
```

```gherkin
Scenario: Performing dry-run migration to inspect schema updates
Given an older task document using legacy field "governing_adr: 0001" instead of "governing_adrs: ['ADR-0001']"
When the architect runs "spec-ops schema migrate --dry-run"
Then the command outputs a unified diff showing projected frontmatter transformations
And leaves files on disk unmodified.
```

```gherkin
Scenario: Executing in-place frontmatter migration preserving Markdown body contents
Given an older task document with legacy frontmatter fields and a 100-line Markdown technical specification
When the architect runs "spec-ops schema migrate --in-place"
Then the YAML frontmatter is rewritten to the new schema format
And the exact Markdown body, headings, and code blocks below the frontmatter are preserved byte-for-byte.
```

## Rationale & Compelling Value
As PMaC metadata schemas evolve across an enterprise, deterministic in-place migration ensures frontmatter stays valid without requiring tedious, error-prone manual edits.
