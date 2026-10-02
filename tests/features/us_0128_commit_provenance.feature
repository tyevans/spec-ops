@us_0128 @adoption @audit
Feature: Brownfield Commit Provenance Baselining and Rev-Range Auditing

  Scenario: Auditing commit provenance with adoption baseline commit
    Given an existing git repository adopted into SpecOps at commit "adoption_commit_hash"
    And "specops.toml" contains "[audit.provenance] baseline_commit = 'adoption_commit_hash'"
    When running "spec-ops audit provenance --strict"
    Then commits preceding the baseline commit are marked as grandfathered legacy history
    And only commits from the baseline forward are audited for "SpecOps-Task" RFC-822 trailers
    And the provenance integrity report outputs 100% compliant lineage.

  Scenario: Verifying unbroken task trailers across specified revision ranges
    Given a brownfield repository with unanchored historical commits
    When running "spec-ops audit provenance --since main"
    Then the audit evaluates only commits in the specified range
    And ignores pre-existing unanchored history outside the range.
