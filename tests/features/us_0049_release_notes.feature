@us_0049 @release_notes
Feature: Automated Customer-Facing Release Notes and Business Value Changelog Generator

  Scenario: Generating Customer Release Notes for a Completed Milestone
    Given a completed milestone "Milestone 1: Foundations" in "ROADMAP.md" with linked PRDs and stories
    When Taylor executes "spec-ops release notes --milestone M1 --format markdown"
    Then a release notes document is generated at "docs/reference/release-notes-m1.md"
    And the content categorizes changes by customer-visible outcome:
      | Section              | Content Source                              |
      | New Capabilities     | Shipped PRD "What good looks like" sections |
      | User Scenarios Added | Passed Gherkin user story summaries         |
      | Persona Impacts      | Persona benefits from "PERSONAS.md"         |
    And internal developer refactors and invisible spike commits are excluded.

  Scenario: Exporting Clean HTML for Stakeholder Newsletters
    Given generated release notes for an accepted release
    When Taylor runs "spec-ops release notes --milestone M1 --format html --branded"
    Then a styled, standalone HTML email template is created
    And links each new capability directly to the live GitHub Pages documentation and visualizer permalink.
