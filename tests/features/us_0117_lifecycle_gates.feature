@us-0117 @TASK-0188 @orchestrator @gates
Feature: Embedded Definition of Ready (DoR) and Definition of Done (DoD) Lifecycle Gates (US-0117)
  As an AI-native engineering lead and autonomous SDLC orchestrator
  I want Definition of Ready and Definition of Done gates rigorously evaluated across the orchestration lifecycle
  So that unrefined tasks are blocked from execution and incomplete implementations are prevented from integration.

  Scenario: Definition of Ready Gate blocks unrefined tasks with incomplete contracts
    Given a backlog task missing required governing artifacts and BDD specifications
    When the lifecycle orchestrator evaluates the Definition of Ready gate
    Then the task fails the DoR gate check
    And actionable violations and recommendations are reported for remediation.

  Scenario: Definition of Ready Gate approves fully refined tasks
    Given a fully refined backlog task satisfying all 7 DoR rules
    When the lifecycle orchestrator evaluates the Definition of Ready gate
    Then the task passes the DoR gate check
    And is approved for in-worktree active implementation.

  Scenario: Definition of Done Gate blocks implementations with failing verification criteria
    Given an implementation diff missing blackbox frontdoor tests or mutation kill thresholds
    When the lifecycle orchestrator evaluates the Definition of Done gate
    Then the task fails the DoD gate check
    And integration is blocked until all 10 DoD rules pass.

  Scenario: Definition of Done Gate approves compliant implementations
    Given an implementation that satisfies 100% frontdoor tests, health, lockfile, and human sign-off
    When the lifecycle orchestrator evaluates the Definition of Done gate
    Then the task passes the DoD gate check
    And is approved for integration into main.
