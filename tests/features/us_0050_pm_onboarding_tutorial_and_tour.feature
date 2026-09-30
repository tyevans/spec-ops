Feature: Non-Technical PMaC Onboarding Tutorial and Interactive Guided Tour

  Scenario: Accessing the Product Manager Diataxis Onboarding Tutorial
    Given a SpecOps documentation site compiled with "spec-ops docs build"
    When Taylor navigates to "docs/tutorials/02-product-manager-onboarding.md" in the browser
    Then a step-by-step tutorial is displayed covering PMaC philosophy, reading PRDs, writing Gherkin stories, and conducting UAT
    And all instructions avoid low-level terminal jargon in favor of browser and editor workflows.

  Scenario: Launching Interactive In-Browser Visualizer Guided Tour
    Given Taylor opens the SpecOps visualizer for the first time
    When the application detects no prior tour completion flag in localStorage
    Then a lightweight welcome modal offers: "Take a 2-minute tour of SpecOps for Product Managers"
    And stepping through the tour highlights PRDs & Features, Gantt timelines, UAT matrix, and deep-link permalinks
    And clicking "Finish Tour" saves the preference and dismisses the highlights.

  Scenario: Completing the Guided First PRD Shaping Exercise
    Given Taylor is following the onboarding tutorial in the visualizer sandbox
    When Taylor completes the interactive exercise "Create your first Idea PRD"
    Then the tutorial verifies the generated Markdown structure locally
    And displays a celebratory confirmation badge: "PMaC Ready: Your first specification is git-locked!".
