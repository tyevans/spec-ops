Feature: Multi-Agent Collaborative Review Radar and Cross-Context Interface Auditor
  As an agentic systems architect
  I want an automated review radar that audits cross-context boundaries and public interface mutations
  So that parallel autonomous worktrees prevent ADR-0007 boundary violations and breaking changes before merge

  Scenario: Auditing cross-context boundary violations in active worktree diffs
    Given an active worktree introducing an import from "infrastructure" into a pure "domain" module
    When the engineer runs "spec-ops review radar"
    Then an architectural boundary violation is reported citing ADR-0007
    And the review radar returns exit code 1

  Scenario: Clean review radar on compliant interface changes
    Given a worktree modifying internal logic within a single bounded context without public API breaks
    When the engineer runs "spec-ops review radar"
    Then zero cross-context violations are reported
    And the radar returns exit code 0
