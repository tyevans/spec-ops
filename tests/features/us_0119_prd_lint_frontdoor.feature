Feature: Blackbox Frontdoor CLI Test Suite for PRD Linting

  Scenario: Running spec-ops prd lint on clean compliant PRD specifications
    Given a repository with valid PRD specifications
    When the user runs "spec-ops prd lint"
    Then the process exit code is 0
    And the output indicates all outcomes are falsifiable and valid

  Scenario: Running spec-ops prd lint detects unfalsifiable outcomes with line-level hints
    Given a repository with PRD specifications containing subjective adjectives
    When the user runs "spec-ops prd lint"
    Then the process exit code is 1
    And line-level diagnostics, suggested rewrites, and remediation hints are displayed

  Scenario: Running spec-ops prd lint with automated remediation writes fixes to disk
    Given a repository with PRD specifications needing quality remediation
    When the user runs "spec-ops prd lint --remediate"
    Then the process exit code is 0
    And the files on disk have their subjective terms replaced with falsifiable criteria

  Scenario: Running spec-ops prd lint with JSON flag produces machine-readable payload
    Given a repository with PRD specifications
    When the user runs "spec-ops prd lint --json"
    Then the output is valid JSON containing reports and summary statistics
