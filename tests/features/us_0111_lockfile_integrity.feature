@security @us_0111
Feature: Supply-Chain Lockfile Integrity Sentinel and Attestation Audit

  Scenario: Verifying authentic lockfile integrity
    Given a verified repository with an intact uv.lock file
    When the security lockfile auditor runs verification
    Then the calculated digest matches the recorded attestation
    And the command exits with status 0

  Scenario: Detecting unauthorized lockfile tampering
    Given a lockfile modified with unauthorized dependency alterations
    When the security lockfile auditor runs verification
    Then the discrepancy is flagged as an unauthorized supply-chain modification
    And the command terminates with exit code 1
