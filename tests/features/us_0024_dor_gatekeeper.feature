Feature: Automated Definition of Ready Gatekeeper and Ticket Health Audit
  As an engineering lead
  I want "spec-ops queue refine" to enforce strict Definition of Ready (DoR) compliance
  So that proposed tasks lacking executable Gherkin acceptance criteria, linked personas, cited ADRs, or bounded contexts are blocked from entering the ready buffer.

  Scenario: Promoting Only Fully Compliant Tasks to Refined Buffer
    Given an under-buffered ready queue (< 3 tasks)
    And proposed task "0024-implement-audit.md" satisfies all 7 DoR rules:
      | Rule Check                     | Status |
      | Complete YAML frontmatter      | Pass   |
      | Linked Persona & PRD           | Pass   |
      | Cited Governing ADRs           | Pass   |
      | Executable Gherkin Scenarios   | Pass   |
      | Defined Target Bounded Context | Pass   |
      | Feasible File Limit Scope      | Pass   |
      | Mutation Testing Scope Defined | Pass   |
    When the lead executes "spec-ops queue refine TASK-0024"
    Then "TASK-0024" is promoted to "docs/project/backlog/refined/"
    And "PRIORITY.md" is updated atomically.

  Scenario: Rejecting Half-Baked Proposed Tasks Lacking Gherkin Criteria
    Given a proposed task "0025-ambiguous-task.md" containing only bullet points and no "Given ... When ... Then" scenarios
    When the lead executes "spec-ops queue refine TASK-0025"
    Then the command exits with code 1
    And flags "TASK-0025: DoR Violation - Missing executable Gherkin acceptance criteria (ADR-0006)"
    And the task remains in "docs/project/backlog/proposed/"

  Scenario: Rejecting Tasks Violating Single-Responsibility Scope
    Given a proposed task whose specification proposes modifying 8 different bounded contexts spanning >500 expected lines
    When the lead executes "spec-ops queue refine TASK-0026"
    Then the task is rejected with advice to decompose into thin vertical slices or architectural spikes (ADR-0002).
