@us_0029 @cli @json
Feature: Machine-Readable JSON Output for Autonomous CLI Inspection

  Scenario: Inspecting Next Backlog Task with Machine-Readable JSON
    Given a project backlog with refined tasks in "docs/project/backlog/refined/"
    When the agent runs "spec-ops queue next --json"
    Then the command exits with return code 0
    And the output is valid JSON conforming to the Task schema
    And the JSON payload includes fields "id", "canonical_id", "title", "target_bc", "dependencies", and "governing_adrs"
    And no ANSI color codes or decorative terminal banners are present in the output.

  Scenario: Parsing Health Violations via Structured JSON
    Given a repository containing one file exceeding 500 lines and one unsynced priority task
    When the agent runs "spec-ops health --json"
    Then the command exits with return code 1
    And the output is a valid JSON object containing "status: error"
    And the "violations" array contains the violating file path, line count, and offending rule "ADR-0002"
    And the "priority_sync" object reports the mismatched task IDs.
