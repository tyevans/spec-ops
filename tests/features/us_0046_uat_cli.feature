Feature: US-0046 Customer-Ready User Acceptance Testing Verification and Sign-Off Matrix CLI

  Scenario: Inspecting Customer UAT Readiness Matrix via CLI
    Given a project with accepted PRDs, user stories, and passing CI runs
    When Taylor runs "spec-ops prd uat status"
    Then the UAT readiness table displays checkable outcomes with their linked stories
    And overall customer delivery readiness is reported as 50.0%

  Scenario: Recording PM Business Acceptance Sign-Off via CLI
    Given a checkable outcome whose automated Gherkin scenario is "Passed (CI)"
    When Taylor runs "spec-ops prd uat sign --prd PRD-0001 --outcome 1 --reviewer Taylor <taylor@specops.local> --notes Verified multi-tab switching and drawer responsiveness on Chromium"
    Then the sign-off metadata is recorded in "docs/project/product/uat-signoff.json"
    And running "spec-ops prd uat status" reports 100.0% delivery readiness

  Scenario: Preventing Release Integration without Mandatory PM UAT Sign-Off
    Given an engineering pull request attempting to mark a milestone complete
    When the CI preflight gate runs "spec-ops health --check-uat"
    And any high-priority checkable outcome lacks approved PM UAT sign-off
    Then the preflight check fails with: "Release blocked: UAT sign-off missing for PRD-0001 Outcome 2"
    And instructs the team to request Taylor's sign-off via the UAT visualizer matrix.

  Scenario: Generating and Verifying Cryptographic Customer UAT Receipt
    Given a project with approved PM UAT sign-offs
    When Taylor runs "spec-ops prd uat receipt --prd PRD-0001"
    Then a tamper-evident Customer UAT receipt is generated with valid SHA-256 tree digest
    And verifying the receipt with "spec-ops prd uat receipt --prd PRD-0001 --verify" succeeds
