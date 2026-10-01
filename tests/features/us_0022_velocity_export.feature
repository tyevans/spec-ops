@us_0022
Feature: US-0022: Hybrid Team Velocity and Executive Forecast Exporter
  As an engineering leader or product executive
  I want to run "spec-ops report velocity --export html"
  So that I can generate a self-contained, presentation-ready visual dashboard with interactive SVG charts and delivery forecasts.

  Scenario: Exporting Velocity Trends for Executive Reviews
    Given a project with completed tasks delivered across multiple sprints or milestones
    When the lead runs "spec-ops report velocity --export html --out dist/velocity-report.html"
    Then a standalone, zero-dependency HTML dashboard is generated with interactive charts and throughput forecasts.
    And the HTML artifact operates entirely offline without external CDN script references.

  Scenario: Exporting Velocity with Default File Destination
    Given a project with completed tasks delivered across multiple sprints or milestones
    When the lead runs "spec-ops report velocity --export html"
    Then a standalone, zero-dependency HTML dashboard is generated at "dist/velocity-report.html"

  Scenario: Exporting Velocity with Format Option
    Given a project with completed tasks delivered across multiple sprints or milestones
    When the lead runs "spec-ops report velocity --format html --output dist/custom-velocity.html"
    Then a standalone, zero-dependency HTML dashboard is generated at "dist/custom-velocity.html"
