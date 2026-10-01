@us_0022
Feature: US-0022: Hybrid Team Velocity and Autonomous Agent Rescue Analytics
  As an engineering lead
  I want to run "spec-ops report velocity"
  So that I can measure cycle time, autonomous self-healing success rates, human worktree rescue frequency, and net delivered value across human and agent workflows.

  Scenario: Generating Hybrid Velocity and Throughput Metrics
    Given a project with completed tasks delivered across multiple sprints or milestones
    When the lead runs "spec-ops report velocity"
    Then the system calculates and prints hybrid delivery KPIs:
      | Metric                         |
      | Tasks Delivered                |
      | Merged Commits                 |
      | Tasks Delivered per Week       |
      | Average Task Cycle Time        |
      | First-Pass Preflight Pass Rate |
      | Self-Healing Resolution Rate   |
      | Human Rescue Escalation Rate   |
    And saves a structured historical snapshot to ".spec-ops/metrics/velocity.json".

  Scenario: Visualizing Rescue Burden and Failure Clustering
    Given multiple autonomous worker runs required human rescue via "spec-ops rescue"
    When the lead runs "spec-ops report velocity --rescues"
    Then the report identifies recurring failure clusters and computes rescue burden telemetry
    And lists the top failure reasons including preflight test failures and file length violations.

  Scenario: Structured JSON Output for Fleet Automation
    Given a project with completed tasks delivered across multiple sprints or milestones
    When the lead runs "spec-ops report velocity --json"
    Then the command outputs valid JSON containing contributor velocity and throughput metrics.
