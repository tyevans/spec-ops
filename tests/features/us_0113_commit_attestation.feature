Feature: Cryptographic Commit Attestation and Sigstore Keyring Validator

  Scenario: Verifying authentically signed commit ranges
    Given a git branch containing cryptographically signed commits
    And an authorized keyring containing the signer public key
    When the developer runs spec-ops security verify-commits
    Then all commits in the range are verified
    And the command terminates with exit code 0

  Scenario: Rejecting unsigned or forged commits in branch
    Given a branch containing an unsigned commit
    When the developer runs spec-ops security verify-commits with strict mode
    Then the unsigned commit is flagged
    And the command exits with error status 1
