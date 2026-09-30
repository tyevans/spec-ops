@us_0019 @audit @traceability @provenance
Feature: US-0019 Bidirectional End-to-End Traceability and Contributor Provenance Audit

  Scenario: Verifying Unbroken Traceability from Persona to Merged Commits
    Given a project repository with accepted Personas, PRDs, User Stories, and Backlog Tasks
    And git history containing merged commits with structured trailers referencing task IDs
    When the lead runs "spec-ops audit traceability"
    Then the command exits with code 0
    And outputs a verified traceability matrix linking each Persona to its PRDs, Stories, Tasks, and Git Commits
    And reports "Traceability Integrity: 100% (0 unanchored commits, 0 orphaned stories)".

  Scenario: Flagging Unanchored Commits and Orphaned Tasks
    Given a git commit merged to "main" without a "Task-ID" or "SpecOps-Task" trailer
    And a completed task in "docs/project/backlog/complete/" with no linked git commits
    When the lead runs "spec-ops audit traceability"
    Then the command exits with code 1
    And reports a warning identifying the unanchored commit hash and author
    And highlights the orphaned task as missing delivery provenance.

  Scenario: Contributor Provenance Attribution
    Given a repository with commits authored by autonomous workers containing "Provenance: spec-ops autonomous worker"
    And commits authored by human developers
    When the lead runs "spec-ops audit traceability --contributions"
    Then the output breaks down delivered tasks by contributor type:
      | Contributor Class   | Tasks Delivered | Merged Commits | Verification Pass Rate |
      | Autonomous Agents   | 14              | 28             | 93.3%                  |
      | Human Developers    | 9               | 15             | 100.0%                 |
    And updates the visualizer Traceability view with contributor filter chips.
