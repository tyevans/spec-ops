@us_0047 @prd
Feature: Executive Roadmap Exporter and Zero-Overhead Presentation Generator

  Scenario: Exporting Executive Roadmap Visual via CLI
    Given a project with documented milestones in "docs/project/backlog/ROADMAP.md"
    When Taylor runs "spec-ops export roadmap --format svg --out dist/executive-roadmap.svg"
    Then a high-resolution vector roadmap graphic is generated
    And the graphic illustrates milestones grouped by delivery horizon (M1 Foundations, M2 Agent Ecosystem)
    And completed tasks are marked with progress bars based on git commit history
    And zero manual configuration files are required.

  Scenario: Generating Standalone Stakeholder Slide Deck in the Visualizer
    Given the SpecOps visualizer is open on the "Gantt & Timeline" tab
    When Taylor clicks "Export Executive Summary"
    And selects audience "Leadership / Non-Technical" with granularity "Milestones & PRD Outcomes"
    Then a self-contained, single-file HTML presentation is downloaded
    And the slide deck contains interactive progress dials, horizon milestones, and persona impact summaries
    And opens cleanly in any web browser without server dependencies.

  Scenario: Automated CI Synchronization of Stakeholder Visuals
    Given a repository configured with the GitHub Pages deployment workflow
    When changes merge into "main" updating task completion states
    Then the documentation pipeline automatically generates updated roadmap SVG artifacts in "site/assets/roadmap.svg"
    And executive bookmarks always reflect current git ground truth without double-entry.
