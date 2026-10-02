@us_0126 @adoption @core
Feature: Incremental Brownfield Technical Debt Baselining and Seam Refactoring Synthesis

  Scenario: Baselining oversized legacy files into persistent debt manifest
    Given an existing codebase containing source files exceeding the 500-line architectural limit
    When running "spec-ops adopt --grandfather-debt"
    Then ".spec-ops/debt_baseline.json" is created recording relative paths and baselined line counts
    And "spec-ops health" reports 0 file limit violations.

  Scenario: Enforcing technical debt ratchet preventing legacy file growth
    Given a codebase with baselined files in ".spec-ops/debt_baseline.json"
    When a grandfathered file has additional lines added exceeding its baselined line count
    Then "spec-ops health" flags the file as an unapproved debt regression violation
    And newly added files exceeding 500 lines are strictly rejected.

  Scenario: Emitting structured AST seam decomposition refactor tasks
    Given grandfathered files detected during adoption
    When "spec-ops adopt" scans file syntax trees
    Then actionable refactoring tasks are emitted into "docs/project/backlog/proposed/"
    And each task includes concrete AST seam suggestions, extractable classes, and target line reductions.
