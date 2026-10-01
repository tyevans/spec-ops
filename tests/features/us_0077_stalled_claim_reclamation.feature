@us_0077 @backlog @queue @reclaim
Feature: Stalled Worker Claim Reclamation and Lease Heartbeat Watcher
  As an AI-native engineering lead,
  I want to execute "spec-ops queue reclaim-stalled",
  So that abandoned task claims and crashed worker leases are safely revoked, restored to Refined, and logged without blocking backlog progression.

  Scenario: Reclaiming an abandoned task claim exceeding timeout
    Given a task "TASK-0020" in "refined/" has status "In-Progress" and is claimed by "stalled-worker-01" with claim timestamp 5 hours ago
    When the engineering lead runs "spec-ops queue reclaim-stalled --timeout-hours 4.0"
    Then the command output confirms 1 task claim was reclaimed
    And task "TASK-0020" claimed_by is reset to empty
    And task "TASK-0020" status is restored to "Refined" in the task file and PRIORITY.md

  Scenario: Active claims with fresh heartbeats are never reclaimed
    Given a task "TASK-0021" in "refined/" is claimed by "active-worker-02" with claim timestamp 6 hours ago and heartbeat timestamp 15 minutes ago
    When the engineering lead runs "spec-ops queue reclaim-stalled --timeout-hours 4.0"
    Then zero task claims are reclaimed
    And task "TASK-0021" remains claimed by "active-worker-02"

  Scenario: Dry run preview does not modify disk state
    Given a task "TASK-0022" in "refined/" has status "In-Progress" and is claimed by "stalled-worker-03" with claim timestamp 8 hours ago
    When the engineering lead runs "spec-ops queue reclaim-stalled --dry-run --timeout-hours 4.0"
    Then the command output previews reclamation of "TASK-0022"
    And task "TASK-0022" remains claimed by "stalled-worker-03" on disk
    And PRIORITY.md remains unmodified for "TASK-0022"

  Scenario: Structured JSON output format
    Given a task "TASK-0023" in "refined/" has status "In-Progress" and is claimed by "stalled-worker-04" with claim timestamp 5 hours ago
    When the engineering lead runs "spec-ops queue reclaim-stalled --json --timeout-hours 4.0"
    Then the output is valid JSON with reclaimed_count 1 containing "TASK-0023"
    And the JSON output includes audit_trail entries
