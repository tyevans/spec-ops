@us_0105 @visualizer
Feature: Executive Milestone Burndown and Multi-Format Presentation Deck Exporter

  Scenario: Generating Milestone Executive Summary via CLI
    Given a project repository with documented milestones in "docs/project/backlog/ROADMAP.md"
    When Taylor runs "spec-ops report milestone --milestone M1-MVP --format digest"
    Then the CLI outputs a clean executive briefing containing:
      """
      - Target milestone name, horizon, and overall percentage completion
      - Quantified value delivered broken down by primary persona (Alex, Jordan, Morgan, Riley, Taylor)
      - Total verified public frontdoor test count and mutation testing kill score
      - Remaining critical path deliverables and projected delivery horizon
      - Blocked dependencies or pending architectural decisions
      """
    And the output is formatted cleanly with Markdown tables and bulleted highlights for email or Slack distribution.

  Scenario: Interactive Zero-Dependency Slide Deck Export from Visualizer
    Given the visualizer is loaded on the "Gantt & Timeline" tab
    When Taylor clicks "Export Presentation Deck" and selects milestone "M1-MVP"
    Then the browser initiates a download of a single-file HTML presentation "m1-mvp-executive-briefing.html"
    And the downloaded presentation contains:
      """
      - An executive overview slide with interactive radial progress meters
      - A visual delivery horizon Gantt timeline
      - A persona value delivered matrix citing customer quotes and accepted user stories
      - Codebase health metrics (0 file limit violations, 100% blackbox test pass rate)
      """
    And the slide deck presents cleanly with keyboard slide navigation (Arrow keys / Spacebar) and zero external network calls.

  Scenario: Automated Detection of Unanchored Scope Creep
    Given 3 completed tasks in the backlog that are not associated with any milestone in "ROADMAP.md"
    When Taylor runs "spec-ops report milestone --check-alignment"
    Then the report flags an alert: "⚠️ Scope Alignment Warning: 3 completed tasks unanchored from ROADMAP.md"
    And provides a table listing the unanchored tasks, their target bounded contexts, and authoring commits.
