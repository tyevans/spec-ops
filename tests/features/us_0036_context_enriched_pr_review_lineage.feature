@us_0036
Feature: US-0036 Context-Enriched Pull Request Review and Architectural Lineage

  Scenario: Generating an architectural review brief for an agent PR
    Given a task branch "task/TASK-0015" created by an autonomous agent for "TASK-0015"
    When the engineer executes "spec-ops review TASK-0015"
    Then the CLI outputs a structured architectural review summary including:
      | Section               | Content                                                 |
      | Governing PRD         | PRD-0001 (SpecOps Autonomous Project Management Engine) |
      | Governing ADRs        | ADR-0002 (<500 lines limit), ADR-0003 (Frontdoor TDD)   |
      | Acceptance Scenarios  | Executable Gherkin scenarios from governing user story  |
      | Lineage Path          | Persona -> PRD -> User Story -> Task                    |
    And all changed source files are summarized with line delta and file-limit headroom
    And zero private internal mocks are flagged in the verification report.

  Scenario: Verifying commit provenance trailers and author distinction
    Given a pull request branch containing both human and agent commits
    When the engineer executes "spec-ops review TASK-0015 --provenance"
    Then the review report identifies which commits were authored by autonomous workers versus human contributors
    And any commit missing the "SpecOps-Task: TASK-0015" git trailer is flagged with a warning.
