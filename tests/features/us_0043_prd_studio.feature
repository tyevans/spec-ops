Feature: Interactive Web-Based PRD Studio and Template Scaffolder

  Scenario: Scaffolding a New PRD Draft via Visualizer Web Studio
    Given the SpecOps standalone visualizer is open in a web browser
    When Taylor navigates to the "PRDs & Features" tab and clicks "New PRD"
    And fills in the guided template form fields:
      | Field                 | Value                                              |
      | Title                 | Self-Service Customer Billing Portal               |
      | Target Persona        | Alex                                               |
      | Component             | billing                                            |
      | Problem Statement     | Customers cannot update payment methods self-serve |
      | Checkable Outcome 1   | User updates credit card via web dashboard         |
      | Checkable Outcome 2   | Stripe webhook confirms card update with 200 OK    |
    And clicks "Save PRD Draft"
    Then a new Markdown file is created at "docs/project/product/idea/prd-0002-self-service-customer-billing-portal.md"
    And the generated document contains valid YAML frontmatter with status "Idea" and target persona "Alex"

  Scenario: Enforcing PRD Structural Quality Invariants in Real Time
    Given Taylor is authoring a PRD in the Web Studio
    When Taylor attempts to submit a PRD with missing "Checkable Outcomes" or an unmapped "Target Persona"
    Then the editor displays a validation alert highlighting the missing mandatory sections
    And prevents document creation until at least one falsifiable outcome is specified
    And cites the governing specification standard (ADR-0001).

  Scenario: Split-Pane Markdown Preview and Direct Git Commit
    Given an existing PRD "PRD-0001" open in the visualizer PRD Studio
    When Taylor updates the problem statement in the form editor
    Then the live Markdown preview pane re-renders the Diataxis formatting in real time
    And clicking "Commit Specification" records the changes directly to the active feature branch with git author attribution.
