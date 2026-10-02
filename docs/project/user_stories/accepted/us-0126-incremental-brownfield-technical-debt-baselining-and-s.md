---
id: '0126'
title: "Incremental Brownfield Technical Debt Baselining and Seam Refactoring Synthesis"
status: Accepted
created: 2026-10-02
persona: "Devon"
target_bc: "core"
feature: "FEAT-ADOPT-01"
governing_prd: "PRD-0007"
scenarios:
  - "Baselining oversized legacy files into persistent debt manifest"
  - "Enforcing technical debt ratchet preventing legacy file growth"
  - "Emitting structured AST seam decomposition refactor tasks"
---

# US-0126 — Incremental Brownfield Technical Debt Baselining and Seam Refactoring Synthesis

## Governing PRD
- [`PRD-0007: Brownfield Codebase Adoption, Technical Debt Baselining & Documentation Bridging Engine`](../../product/accepted/prd-0007-brownfield-codebase-adoption-and-onboarding-engine.md)

## User Story

**As a** brownfield migration engineer (Devon),  
**I want** `spec-ops adopt --grandfather-debt` to baseline existing oversized legacy files into a persistent debt manifest and generate actionable AST decomposition tasks,  
**So that** mature codebases can adopt SpecOps governance without immediate CI breakage while enforcing an architectural ratchet that prevents further debt expansion.

## Acceptance Criteria

```gherkin
Scenario: Baselining oversized legacy files into persistent debt manifest
  Given an existing codebase containing source files exceeding the 500-line architectural limit
  When running "spec-ops adopt --grandfather-debt"
  Then ".spec-ops/debt_baseline.json" is created recording relative paths and baselined line counts
  And "spec-ops health" reports 0 file limit violations.
```

```gherkin
Scenario: Enforcing technical debt ratchet preventing legacy file growth
  Given a codebase with baselined files in ".spec-ops/debt_baseline.json"
  When a grandfathered file has additional lines added exceeding its baselined line count
  Then "spec-ops health" flags the file as an unapproved debt regression violation
  And newly added files exceeding 500 lines are strictly rejected.
```

```gherkin
Scenario: Emitting structured AST seam decomposition refactor tasks
  Given grandfathered files detected during adoption
  When "spec-ops adopt" scans file syntax trees
  Then actionable refactoring tasks are emitted into "docs/project/backlog/proposed/"
  And each task includes concrete AST seam suggestions, extractable classes, and target line reductions.
```
