Feature: Modularity Debt Scoring and Source File Growth Proactive Telemetry
  As an engineering architect or autonomous coding agent
  I want proactive telemetry scoring modularity decay and tracking file line count growth
  So that I can identify decomposing seams and prevent files from breaching hard line count limits

  Scenario: Computing modularity debt scores across project modules
    Given a project repository with source files of varying lengths
    When the engineer runs "spec-ops health --modularity"
    Then a modularity debt report is displayed
    And files approaching 400 lines are flagged with proactive decomposition warnings

  Scenario: Structured JSON modularity telemetry export
    Given active codebase files analyzed for modularity health
    When the user executes "spec-ops health --modularity --json"
    Then a valid JSON payload containing per-file risk scores and line counts is emitted
    And returns exit code 0
