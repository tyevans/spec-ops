Feature: Dynamic Worker Lease Heartbeat and Zombie Claim Auto-Reclaimer
  As an autonomous worker orchestrator
  I want to track worker leases and automatically reclaim zombie task claims
  So that crashes or abandoned tasks do not indefinitely block the queue

  Scenario: Reclaiming expired zombie worker claim
    Given a claimed task with an expired lease token and no active host process
    When the worker lease manager executes claim reconciliation
    Then the zombie lease is revoked
    And the task is safely restored to refined status for reallocation
    And the command terminates with exit code 0

  Scenario: Preserving active worker leases
    Given an actively running worker updating its lease heartbeat
    When the lease manager evaluates active worker leases
    Then the active lease is confirmed valid and unexpired
    And the task claim remains actively held
