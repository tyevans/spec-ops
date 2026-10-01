Feature: Continuous Orchestration Retrospective and Self-Healing Engine
  As an AI-native engineering lead or autonomous orchestrator
  I want continuous retrospective analysis of worktree failures
  So that recurrent invariant breaches are automatically converted into actionable remediation tasks with negative prompt constraints.

  Scenario: Retrospective Detection of Orchestration Failures
    Given recent worktree failure logs containing secret scanner leak alerts or mock backdoor errors
    When the engineer runs "spec-ops orchestrate retrospect"
    Then the failure patterns are categorized by invariant ID
    And high-priority remediation tasks are scaffolded in "docs/project/backlog/proposed/"

  Scenario: Retrospective Negative Prompt Constraint Hydration
    Given a proposed remediation task scaffolded by the retrospective engine
    When the task frontmatter is inspected
    Then the failure history records the breached invariant and negative prompt guidance
