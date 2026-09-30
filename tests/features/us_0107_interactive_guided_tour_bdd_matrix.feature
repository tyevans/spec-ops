Feature: Interactive Non-Technical Stakeholder Guided Tour and BDD Acceptance Matrix

  Scenario: First-Time Stakeholder Interactive Onboarding Walkthrough
    Given a non-technical stakeholder opens the visualizer for the first time
    When the stakeholder clicks "Take Guided Tour" in the top navigation
    Then a step-by-step interactive spotlight overlays the screen explaining:
      | Step | Title                                                  |
      | 1    | 1. Philosophy of PMaC (Project Management as Code)    |
      | 2    | 2. Personas, PRDs, Stories & Tasks                     |
      | 3    | 3. Delivery Horizons & Filters                         |
      | 4    | 4. Verifiable Test Evidence & UAT Sign-Off             |
    And the tour can be stepped through, skipped, or restarted at any time with persistent state in localStorage.

  Scenario: Persona-Filtered BDD Acceptance Scenario Exploration
    Given the stakeholder navigates to the "personas" tab
    When the stakeholder clicks on persona "Alex"
    Then the view filters down exclusively to the user stories authored for Alex
    And selecting a story opens an accordion displaying its exact Gherkin scenarios:
      """
      Given ... When ... Then ...
      """
    And each scenario displays a green verification badge indicating passing blackbox test coverage.

  Scenario: Executable UAT Sign-Off Verification Matrix and Receipt Export
    Given all acceptance criteria for a release feature have passed blackbox verification
    When Sasha or Taylor reviews the feature in the visualizer and clicks "Export UAT Verification Receipt"
    Then the visualizer generates a cryptographically hashed, timestamped compliance summary:
      | Component                                         |
      | Feature ID and governing PRD                      |
      | Executable Gherkin scenarios verified             |
      | Git commit SHAs and test run timestamps           |
      | Dual sign-off signature block                     |
    And the receipt downloads as a tamper-evident Markdown artifact for SOC2/ISO compliance audit archives.
