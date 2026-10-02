Feature: Automated Conventional Commit RFC-822 Trailer Sanitizer and Signer Pre-Gate
  As a release engineer and compliance auditor
  I want to validate conventional commit headers and RFC-822 SpecOps traceability trailers
  So that all git commit messages are structured and linked to governing tasks before integration

  Scenario: Validating compliant commits with full trailers
    Given a git branch with conventional commit messages and valid SpecOps trailers
    When the trailer sanitizer validates the commit range
    Then all commits pass validation
    And the command terminates with exit code 0

  Scenario: Rejecting commits missing required task trailers
    Given a git commit lacking the required "SpecOps-Task" trailer
    When the trailer sanitizer runs with strict mode
    Then the non-compliant commit is flagged with missing trailer details
    And the command terminates with exit code 1
