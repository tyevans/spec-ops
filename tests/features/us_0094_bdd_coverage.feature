Feature: BDD Feature Scenario Coverage Matrix and Living Acceptance Dashboard (TASK-0156 / US-0094)

  Scenario: Auditing BDD coverage across accepted user stories
    Given a set of accepted user stories with executable Gherkin scenarios
    And corresponding pytest-bdd test modules in the test suite
    When the developer runs spec-ops prd coverage
    Then the scenario coverage matrix reports mapped scenarios and overall coverage percentage
    And exits with success code 0

  Scenario: Failing strict coverage check when unimplemented scenarios exist
    Given an accepted user story with scenarios lacking test implementations
    When the developer runs spec-ops prd coverage with strict mode enabled
    Then the command reports the missing scenario bindings
    And terminates with exit code 1
