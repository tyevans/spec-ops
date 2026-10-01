@us_0056 @security @merkle
Feature: US-0056 Tamper-Evident Merkle Tree Compliance Manifest Generator

  Scenario: Generating deterministic Merkle root digest for project repository
    Given a project repository with accepted PRDs, ADRs, and tasks
    When the auditor runs "spec-ops audit merkle"
    Then a deterministic Merkle root hash is generated
    And each leaf node corresponds to a version-controlled specification or source artifact

  Scenario: Detecting unauthorized file tampering via Merkle verification
    Given a verified Merkle compliance manifest
    When a file in "docs/project/" is modified without updating the manifest
    Then running "spec-ops audit merkle --verify manifest.json" detects a digest mismatch
    And identifies the exact tampered file path
