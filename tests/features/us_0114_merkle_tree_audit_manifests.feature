@us_0114 @security @audit
Feature: US-0114 Tamper-Evident Merkle Tree Compliance Audit Manifests

  Scenario: Generating a deterministic SOC2/ISO 27001 compliance audit package
    Given a repository with completed tasks, linked user stories, test execution records, and signed commits
    When the security officer executes "spec-ops audit export --standard soc2 --output dist/compliance/"
    Then a cryptographic audit manifest "soc2-audit-manifest.json" is generated in "dist/compliance/"
    And every completed deliverable records PRD ID, User Story Gherkin scenarios, Task metadata, agent prompt SHA-256, test execution logs, human reviewer signature, and git commit SHA
    And a top-level Merkle root hash is computed and written to "dist/compliance/MERKLE_ROOT".

  Scenario: Detecting out-of-band audit trail tampering or broken traceability
    Given a task file in "docs/project/backlog/complete/" whose commit SHA or sign-off signature has been modified out-of-band
    When the security officer or auditor executes "spec-ops audit verify --manifest dist/compliance/soc2-audit-manifest.json"
    Then the verification command fails with returncode 1
    And outputs the corrupted task ID alongside the expected and computed SHA-256 integrity digests.
