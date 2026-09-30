Feature: Customer-Ready User Acceptance Testing Verification and Sign-Off Matrix

  Scenario: Inspecting Customer UAT Readiness Matrix
    Given a project with accepted PRDs, user stories, and passing CI runs
    When Taylor opens the visualizer and clicks the "UAT Readiness" tab
    Then each PRD checkable outcome is displayed with its linked Gherkin scenario execution status:
      | PRD Outcome                                  | Linked Story | Test Status | UAT Status   |
      | Visualizer renders 2D force-directed canvas  | US-0006      | Passed (CI) | Pending PM   |
      | Deep linking opens entity detail drawer      | US-0010      | Passed (CI) | Approved     |
    And overall customer delivery readiness is calculated as a percentage.

  Scenario: Recording PM Business Acceptance Sign-Off
    Given a checkable outcome whose automated Gherkin scenario is "Passed (CI)"
    When Taylor reviews the running application and toggles the outcome status to "Approved (PM UAT)"
    And enters review notes: "Verified multi-tab switching and drawer responsiveness on Chromium"
    Then the sign-off metadata (timestamp, reviewer: Taylor, outcome ID) is recorded in "docs/project/product/uat-signoff.json"
    And the UAT matrix updates immediately with a green acceptance badge.

  Scenario: Preventing Release Integration without Mandatory PM UAT Sign-Off
    Given an engineering pull request attempting to mark a milestone complete
    When the CI preflight gate runs "spec-ops health --check-uat"
    And any high-priority checkable outcome lacks approved PM UAT sign-off
    Then the preflight check fails with: "Release blocked: UAT sign-off missing for PRD-0001 Outcome 2"
    And instructs the team to request Taylor's sign-off via the UAT visualizer matrix.
