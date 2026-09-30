@us_0073 @backlog @queue
Feature: Automated Reactive Unblocking and Cascading Buffer Replenishment upon Task Completion
  As an AI-native engineering lead,
  I want spec-ops queue complete to reactively re-evaluate dependency graphs and auto-promote newly unblocked tasks into the ready buffer,
  So that autonomous coding agents never sit idle waiting for manual curation sweeps after prerequisite tasks are integrated.

  Scenario: Reactive Promotion of Newly Unblocked Downstream Task upon Prerequisite Merge
    Given task "TASK-0013" is in "docs/project/backlog/refined/" and currently claimed
    And proposed task "TASK-0014" has "dependencies: [TASK-0013]" in "docs/project/backlog/proposed/"
    And the refined buffer currently has 2 available ready tasks (below buffer target of 10)
    When the orchestrator executes "spec-ops queue complete TASK-0013"
    Then "TASK-0013" is moved to "docs/project/backlog/complete/"
    And the cascade unblocking evaluator identifies "TASK-0014" as newly unblocked
    And "TASK-0014" is automatically promoted to "docs/project/backlog/refined/"
    And "PRIORITY.md" is updated atomically to reflect "TASK-0014 (Refined)".

  Scenario: Maintaining Ready Buffer Ceiling During Cascading Unblocking
    Given the ready buffer already contains 10 tasks (at target buffer capacity)
    And proposed task "TASK-0025" depends solely on completed task "TASK-0024"
    When "TASK-0024" is completed via "spec-ops queue complete TASK-0024"
    Then "TASK-0025" frontmatter is tagged with "unblocked: true"
    But "TASK-0025" remains in "docs/project/backlog/proposed/" to prevent over-buffering beyond the target limit of 10
    And a log message reports "TASK-0025 unblocked but held in proposed to preserve lean ready buffer (10/10)".

  Scenario: Emitting Unblocking Telemetry Event for Autonomous Agent Dispatchers
    Given autonomous agent workers are registered to listen for queue events
    When "TASK-0030" completes and reactively promotes "TASK-0031" into "refined/"
    Then SpecOps emits a machine-readable JSON event to ".spec-ops/events/unblocked.json"
    And the event payload contains the unblocked task ID, target bounded context, and priority rank.
