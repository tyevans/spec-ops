@us_0114 @security @merkle_proof
Feature: US-0114 Merkle Inclusion Proof Generation and Partial Verification

  Scenario: Generating a self-contained Merkle inclusion proof for a single deliverable
    Given an exported compliance manifest with multiple SDLC deliverables and known root hash
    When the auditor executes "spec-ops audit proof --deliverable TASK-0030 --manifest dist/compliance/soc2-audit-manifest.json --out dist/compliance/proof-0030.json"
    Then a self-contained Merkle inclusion proof "dist/compliance/proof-0030.json" is generated
    And the proof records deliverable ID, leaf index, leaf hash, audit path, and root hash

  Scenario: Verifying an inclusion proof offline against a trusted Merkle root
    Given a valid self-contained Merkle inclusion proof for "TASK-0030" and a trusted Merkle root hash
    When the auditor executes "spec-ops audit verify-proof dist/compliance/proof-0030.json --root TRUSTED_ROOT --json"
    Then the verification command succeeds with returncode 0
    And the JSON output confirms verification status "ok"

  Scenario: Detecting tampered inclusion proof or root hash mismatch during offline verification
    Given an inclusion proof file whose leaf hash has been modified
    When the auditor executes "spec-ops audit verify-proof dist/compliance/tampered-proof.json --root TRUSTED_ROOT --json"
    Then the verification command fails with returncode 1
    And the JSON output reports "ok" as false
