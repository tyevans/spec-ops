@us_0025 @backlog @milestone @studio
Feature: Interactive Milestone Planning and Workload Balancing Studio
  As an engineering lead,
  I want to run "spec-ops milestone plan" and simulate delivery feasibility,
  So that I can assign tasks to release milestones and execution profiles, simulate confidence intervals, and sync atomically to repository markdown.

  Scenario: Allocating Tasks to Milestones and Execution Profiles
    Given a repository with unassigned backlog tasks and milestones in "docs/project/backlog/ROADMAP.md"
    When the lead runs "spec-ops milestone plan --assign TASK-0045=M2-Q4-Release:agent-autonomous --json --non-interactive"
    Then the planning matrix reports task "TASK-0045" assigned to milestone "M2-Q4-Release"
    And the execution lane is designated as "agent-autonomous"

  Scenario: Simulating Delivery Horizon and Bottleneck Feasibility
    Given milestone "M2-Q4-Release" has assigned tasks with a dependency chain of 4 levels
    When the lead runs "spec-ops milestone plan --simulate --json --non-interactive"
    Then the simulation computes delivery confidence intervals for P50, P80, and P95
    And flags dependency depth bottlenecks for milestone "M2-Q4-Release"

  Scenario: Atomic Synchronization to Repository Markdown
    Given a repository with unassigned backlog tasks
    When the lead runs "spec-ops milestone plan --assign TASK-0045=M2-Q4-Release --save --json --non-interactive"
    Then task "TASK-0045" frontmatter is atomically updated with milestone "M2-Q4-Release"
    And "docs/project/backlog/ROADMAP.md" is synchronized with task "TASK-0045"
