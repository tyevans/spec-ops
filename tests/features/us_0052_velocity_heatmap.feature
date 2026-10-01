@US-0052 @PRD-0005 @ADR-0008
Feature: Team Delivery Velocity Engine and Cognitive Churn Heatmap
  As an engineering lead or system architect
  I want to analyze delivery throughput, task lead times, and file modification churn
  So that I can identify developer cognitive bottlenecks and modules approaching complexity thresholds

  Scenario: Computing delivery velocity metrics from git history
    Given a project repository with completed tasks and git commits
    When the engineering lead executes "spec-ops release velocity"
    Then a delivery velocity report is generated
    And displays task completion rates, lead time, and high-churn source files

  Scenario: Exporting standalone HTML churn heatmap
    Given completed project delivery milestones
    When the user runs "spec-ops release velocity --format html"
    Then a standalone HTML heatmap report is generated
    And visualizes file modification churn without external CDN dependencies
