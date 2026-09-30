@us_0058 @us_0114 @visualizer @security
Feature: US-0058 and US-0114 Living Security Posture and Compliance Radar in Project Visualizer

  Scenario: Rendering the Security & Compliance Radar view
    Given the standalone visualizer is open in a web browser
    When the user navigates to the "Security & Compliance" tab or URL hash "#tab=security"
    Then the view renders five summary metric cards:
      | Metric                     | Indicator                   |
      | Secret Scan Status         | Pass / Fail                 |
      | Lockfile Integrity         | Synchronized / Modified     |
      | Signed Commit Coverage     | Percentage (e.g., 100%)     |
      | Human Sign-off Rate        | Percentage (e.g., 95%)      |
      | Known Vulnerability Count  | Count of Low/Med/High CVEs  |
    And tasks pending human sign-off are listed in an interactive triage table.

  Scenario: Filtering tasks by compliance readiness
    Given the user is on the Security & Compliance tab
    When the user toggles the "Show Only Unsigned / Unreviewed" filter
    Then the board filters to display only tasks lacking cryptographic signatures or human sign-off approvals
    And clicking any row opens the task drawer displaying the exact missing compliance artifacts.

  Scenario: Rendering the Security & Compliance Radar view in the visualizer for release cut-offs
    Given the standalone visualizer is open in a web browser
    When the user navigates to the "Security & Compliance" tab or URL hash "#tab=security"
    Then the view renders five summary metric cards:
      | Metric                     | Indicator                   |
      | Secret Scan Status         | Pass / Fail                 |
      | Lockfile Integrity         | Synchronized / Modified     |
      | Signed Commit Coverage     | Percentage (e.g., 100%)     |
      | Human Sign-off Rate        | Percentage (e.g., 98%)      |
      | Known Vulnerability Count  | Count of Low/Med/High CVEs  |
    And toggling "Show Only Unsigned / Unreviewed" filters tasks to display only non-compliant items blocking release cut-off.
