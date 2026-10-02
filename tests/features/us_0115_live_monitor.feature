Feature: Interactive Terminal Dashboard Multi-Tab Live Monitor and Status Streamer
  As a developer or CI operator
  I want an interactive multi-tab terminal monitor
  So that I can observe active workers, event streams, and system health in headless or multiplexed environments

  Scenario: Rendering terminal monitor dashboard in live mode
    Given active workers executing tasks in isolated worktrees
    When the operator launches spec-ops monitor live
    Then the terminal dashboard renders active worker cards and system metrics
    And updates dynamically as lifecycle events are published

  Scenario: Headless single-shot monitor snapshot
    Given a terminal running in a headless CI environment
    When the operator executes spec-ops monitor live with headless flag
    Then a clean terminal summary table is printed to standard output
    And the command terminates with exit code 0
