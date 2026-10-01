Feature: INVEST Task Decomposition and Automated DoR Contract Synthesis

  Scenario: INVEST Slicing and DoR Synthesis from PRD
    Given an accepted PRD with multiple checkable outcomes
    When the orchestrator executes "spec-ops task decompose --prd PRD-0006"
    Then the engine slices the scope into INVEST-compliant vertical tasks <500 lines
    And generates executable Gherkin scenarios and property test targets for each task.

  Scenario: Identifying Architectural Uncertainty and Scaffolding Spikes
    Given an accepted PRD containing an outcome with architectural uncertainty
    When the orchestrator executes "spec-ops task decompose --prd PRD-0006"
    Then an architectural spike is scaffolded in proposed backlog
    And an empirical benchmark test harness is initialized in "spikes/".

  Scenario: Automated DoR Contract Synthesis for Incomplete Proposed Tasks
    Given an unrefined proposed task lacking DoR acceptance criteria
    When the orchestrator executes "spec-ops task synthesize-dor TASK-0099"
    Then missing Gherkin scenarios, mutation scopes, and property invariants are synthesized
    And the task satisfies all Definition of Ready rules for queue refinement.
