@security @us_0055 @release_verification
Feature: US-0055 Cryptographic Release Verification and Public Keyring Validator

  Scenario: Verifying valid cryptographic release manifest
    Given a release manifest signed by an authorized key in ".allowed_signers"
    When the auditor executes "spec-ops release verify --manifest release-manifest.json"
    Then the verification succeeds with exit code 0
    And the report confirms cryptographic validity and signer identity

  Scenario: Rejecting tampered release manifest
    Given a release manifest whose payload has been modified post-signing
    When the auditor executes "spec-ops release verify --manifest release-manifest.json"
    Then the verification fails with exit code 1
    And identifies the signature mismatch error
