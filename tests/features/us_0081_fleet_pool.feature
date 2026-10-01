Feature: Dynamic Multi-Worker Fleet Concurrency and Adaptive Worktree Pool Sizing

  Scenario: Dynamically throttling worker concurrency under high load
    Given a system running with CPU utilization exceeding 85%
    When the fleet pool controller evaluates concurrency capacity
    Then available worker slots are throttled down to prevent resource exhaustion
    And active running worktrees continue execution unimpeded

  Scenario: Scaling worker capacity when resources are abundant
    Given a quiescent system with low CPU and memory utilization
    When the cycle command runs with adaptive pooling enabled
    Then concurrency scales up to the configured maximum limit
    And multiple parallel worktrees execute concurrently
