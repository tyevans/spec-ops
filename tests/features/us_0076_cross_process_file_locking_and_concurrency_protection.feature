Feature: Cross-Process File Locking and Concurrency Protection
  As an autonomous coding agent running in a parallel multi-agent fleet,
  I want SpecOps to enforce cross-process atomic file locking and two-phase commits on shared backlog indices,
  So that concurrent worker processes claiming tasks or recording task completions never clobber each other's state or corrupt PRIORITY.md.

  Scenario: Mutual Exclusion During Concurrent Task Claiming
    Given two independent worker processes "worker-alpha" and "worker-beta" running simultaneously
    And task "TASK-0014" is the highest-priority unassigned task in "docs/project/backlog/refined/"
    When both workers invoke "spec-ops worker claim --auto" at the exact same instant
    Then the first worker acquires the cross-process lock at ".spec-ops/locks/backlog.lock"
    And assigns "TASK-0014" to "worker-alpha" with status "claimed"
    And the second worker waits on the lock, refreshes queue state upon acquisition, and claims the subsequent task "TASK-0015"
    And zero race conditions or double-claims occur.

  Scenario: Two-Phase Atomic Write and Rollback on Interrupted Index Updates
    Given a worker process updating "PRIORITY.md" under lock
    When the worker writes the updated index to a temporary staging file ".spec-ops/tmp/PRIORITY.md.tmp"
    And an unexpected termination signal occurs before completion
    Then the original "PRIORITY.md" remains intact and uncorrupted
    And stale lock detection releases the lock after the process heartbeat expires.

  Scenario: Stale Lock Auto-Recovery on Worker Process Crash
    Given a lockfile at ".spec-ops/locks/backlog.lock" holding PID 12345
    And process 12345 no longer exists in the operating system process table
    When a new worker attempts to claim a task
    Then SpecOps detects the dead PID
    And automatically reclaims the stale lock with warning "Recovered stale backlog lock from terminated process 12345"
    And proceeds with the operation without requiring manual human intervention.

  Scenario: 4 Concurrent Worker Processes Claiming via queue claim
    Given 4 concurrent worker processes running "spec-ops queue claim" simultaneously
    When processes contend for the queue lock
    Then operations execute with mutual exclusion without race conditions or duplicate task assignments.
