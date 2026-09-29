Feature: Codebase Invariant Health and File Length Limit Verification
  As an engineering lead
  I want to run spec-ops health in CI and local preflights
  So that no source files exceed 500 lines and the backlog index remains 100% synchronized with disk state.

  Scenario: Clean Repository Verification
    Given a repository where all source files contain fewer than 500 lines
    And PRIORITY.md accurately indexes all tasks across complete, refined, and proposed directories
    When the developer runs "spec-ops health"
    Then the command exits with code 0
    And reports "Invariant Met: Zero source files exceed length limit"

  Scenario: Blocking Monolithic Regressions
    Given a source file that expands beyond 500 lines
    When the preflight command runs "spec-ops health"
    Then the command exits with code 1
    And lists the violating file path, exact line count, and configured limit
