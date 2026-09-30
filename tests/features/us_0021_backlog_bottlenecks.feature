Feature: Autonomous Backlog Bottleneck and Critical Path Deadlock Detection

  Scenario: Identifying High-Fanout Dependency Choke Points
    Given a backlog where multiple proposed tasks in different bounded contexts depend on a single unrefined task "TASK-0013"
    When the lead runs "spec-ops backlog bottlenecks"
    Then the command outputs a prioritized bottleneck analysis:
      | Choke Task | Downstream Blocked Tasks | Critical Path Delay | Recommended Action    |
      | TASK-0013  | 6 tasks                  | 3 delivery horizons | Prioritize Refinement |
    And highlights TASK-0013 as a primary choke point in the visualizer graph with a pulsing alert aura.

  Scenario: Detecting Circular Dependency Deadlocks
    Given task "TASK-0021" lists "TASK-0022" in its dependencies
    And task "TASK-0022" directly or transitively depends on "TASK-0021"
    When the lead runs "spec-ops backlog bottlenecks"
    Then the command exits with code 1
    And displays the exact circular cycle: "TASK-0021 -> TASK-0022 -> TASK-0021"
    And provides actionable CLI suggestions to break the dependency cycle.

  Scenario: Pre-empting Ready Buffer Starvation
    Given a refined queue containing only 1 unassigned task
    And all remaining proposed tasks are blocked by pending in-flight tasks
    When the lead executes "spec-ops backlog bottlenecks --forecast"
    Then the command warns: "Buffer Starvation Imminent: Ready queue will deplete in 1 cycle with zero unblocked candidates"
    And suggests which in-flight tasks require immediate unblocking or rescue to replenish the ready buffer.
