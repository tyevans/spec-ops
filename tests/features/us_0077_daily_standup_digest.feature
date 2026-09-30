@us_0077 @backlog @queue
Feature: Daily Curation Standup Digest, Stalled Claim Detection, and Milestone Scope Transition
  As an AI-native engineering lead,
  I want to generate an automated daily standup digest via "spec-ops queue digest",
  So that completed throughput, active worker leases, blocker bottlenecks, and ready buffer capacity are synthesized without manual git inspection.

  Scenario: Generating Daily Standup Curation Digest in Markdown
    Given a repository with completed tasks in the last 24 hours, active in-progress worktree claims, and blocked proposed items
    When the engineering lead runs "spec-ops queue digest"
    Then the command outputs a formatted Markdown standup digest highlighting completed throughput, active worker leases, blocker bottlenecks, and ready buffer capacity.

  Scenario: Generating Daily Standup Digest as Structured JSON
    Given a repository with completed tasks in the last 24 hours, active in-progress worktree claims, and blocked proposed items
    When the engineering lead runs "spec-ops queue digest --format json"
    Then the output is valid JSON containing metrics, completed throughput, active worker leases, blocker bottlenecks, and ready buffer health.

  Scenario: Generating Daily Standup Digest with Custom Time Window
    Given a repository with completed tasks in the last 24 hours, active in-progress worktree claims, and blocked proposed items
    When the engineering lead runs "spec-ops queue digest --window 48h"
    Then the standup digest reflects the 48h analysis window.
