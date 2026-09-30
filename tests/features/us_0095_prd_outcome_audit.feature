@us_0095 @prd @audit
Feature: US-0095 Continuous PRD Outcome Coverage Audit and Specification Drift Detection

  Scenario: Auditing an accepted PRD with 100% checkable outcome coverage
    Given an accepted PRD "PRD-0001" with 5 checkable outcomes
    And every checkable outcome is mapped to at least one user story in "docs/project/user_stories/accepted/"
    And every user story has implementing tasks in "docs/project/backlog/"
    When Taylor executes "spec-ops prd audit --deep"
    Then the audit report displays "Outcome Coverage: 100% (5/5 outcomes covered)"
    And outputs "Specification Drift: 0 issues detected"
    And the command exits with exit code 0.

  Scenario: Detecting orphaned outcomes lacking BDD user stories or tasks
    Given an accepted PRD "PRD-0004" where outcome "Multi-tenant workspace isolation" has no linked user story
    When Taylor executes "spec-ops prd audit --deep"
    Then the audit report flags PRD-0004 with a warning
    And displays "Orphaned Outcome: 'Multi-tenant workspace isolation' in PRD-0004 has no linked user story or backlog tasks"
    And suggests "Run 'spec-ops prd decompose PRD-0004 --by-outcomes' to generate missing stories".

  Scenario: Flagging unlinked backlog tasks claiming to implement a PRD without outcome mapping
    Given a backlog task "TASK-0105" with "governing_prds: ['PRD-0001']" but with no valid outcome reference or governing story
    When Taylor executes "spec-ops prd audit --deep"
    Then the audit output flags "Unanchored Task: TASK-0105 references PRD-0001 but is not linked to any checkable outcome"
    And the audit summary marks buffer health as "INCOMPLETE_COVERAGE".
