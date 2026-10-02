Feature: Public API Contracts for PRD Outcome Test Coverage

  Scenario: Querying PRD outcome coverage via GET REST endpoint
    Given a repository initialized with PRD "PRD-0003" and BDD test suites
    When an API client queries "GET" at "/api/prd/coverage/outcomes" with "PRD-0003"
    Then the response status code is 200
    And the response payload confirms successful coverage computation with valid metrics

  Scenario: Requesting outcome test coverage audit via POST payload
    Given a repository initialized with PRD "PRD-0003" and BDD test suites
    When an API client issues a "POST" to "/api/prd/coverage/outcomes" with payload for "PRD-0003"
    Then the response status code is 200
    And the returned report includes checkable outcome breakdown and BDD scenario counts
