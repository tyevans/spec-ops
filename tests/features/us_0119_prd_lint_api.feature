Feature: Public API Contracts for PRD Linting and Remediation

  Scenario: Querying PRD lint status via GET API endpoint
    Given a repository initialized with PRD documents
    When an API client issues a "GET" request to "/api/prd/lint"
    Then the response status code is 200
    And the response payload contains success status and lint reports

  Scenario: Submitting in-memory PRD content for linting via POST API endpoint
    Given an in-memory PRD document with subjective outcomes
    When an API client issues a "POST" request to "/api/prd/lint" with the content payload
    Then the response status code is 200
    And the lint report detects unfalsifiable outcomes with line-level suggestions

  Scenario: Applying automated line-level remediation via POST API endpoint
    Given an in-memory PRD document needing line-level remediation
    When an API client issues a "POST" request to "/api/prd/lint/remediate"
    Then the response status code is 200
    And the response provides remediated content with positive applied count
    And the new lint report shows improved outcome falsifiability
