Feature: Customer UAT Sign-Off Cryptographic Token Exporter and Release Gatekeeper

  Scenario: Authorizing release when all checkable outcomes have verified UAT receipts
    Given a PRD where 100% of checkable outcomes possess valid cryptographic UAT receipts
    When the gatekeeper evaluates release readiness
    Then the release gate returns PASS with verification details
    And the command terminates with exit code 0

  Scenario: Blocking release when unverified checkable outcomes remain
    Given a PRD containing unverified checkable outcomes
    When the gatekeeper evaluates release readiness with strict mode
    Then the unverified criteria are listed as release blockers
    And the command terminates with exit code 1
