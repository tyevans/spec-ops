@us_0068 @scaffold
Feature: Living Constitution Synchronization, Extension Preservation, and CI Drift Gate
  As an autonomous coding agent,
  I want the repository's AGENTS.md operating constitution and Diataxis operating manual to automatically re-synchronize when project settings or profiles change while preserving human-authored custom invariant sections,
  So that I always execute work against the authoritative, up-to-date architectural laws without stale instructions or accidentally clobbering team-specific operational guidelines.

  Scenario: Re-synchronizing constitution when specops.toml settings change
    Given an existing project where "specops.toml" has updated "file_length_limit = 350" and added a new quality preflight command "ruff check"
    When the developer or agent runs "spec-ops scaffold agents" (or "spec-ops constitution sync")
    Then "AGENTS.md" is regenerated with the updated 350-line limit and new preflight command in the Hard Invariants and Task Workflow sections
    And "docs/operating-manual.md" is updated synchronously with adjusted relative documentation links
    And all unchanged sections remain structurally intact.

  Scenario: Preserving human-authored custom invariant extensions across sync
    Given an "AGENTS.md" containing a marked user section "<!-- BEGIN CUSTOM INVARIANTS -->" with team-specific guidelines "Always run local emulator on port 9090"
    When "spec-ops scaffold agents" is executed after profile updates
    Then the regenerated "AGENTS.md" retains the exact contents within the custom invariants block
    And updates the profile-driven sections around it without data loss.

  Scenario: CI constitution drift detection gate
    Given a pull request where "specops.toml" architectural settings were modified without re-running constitution sync
    When "spec-ops constitution check" runs during CI preflight
    Then the command detects a mismatch between "specops.toml" and root "AGENTS.md"
    And exits with code 1
    And outputs "Constitution Drift Error: AGENTS.md is out of sync with specops.toml. Run 'spec-ops scaffold agents' to update."
