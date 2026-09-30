@security @us_0113
Feature: US-0113 Cryptographic Commit Verification and Dual-Custody Human Sign-Off Gate

  Scenario: Blocking integration of unsigned git commits into main
    Given a project configured with "[security.compliance] require_signed_commits = true"
    When "spec-ops queue complete <task-id>" or worker squash-merge is executed on a branch with unsigned commits
    Then the command aborts with returncode 1
    And outputs "Compliance Violation: Commit <commit-sha> lacks valid cryptographic signature (GPG/SSH)".

  Scenario: Enforcing dual-custody human review sign-off on autonomous agent tasks
    Given an autonomous agent has passed all preflight checks on a feature branch for task "TASK-0042"
    When the agent attempts to finalize and merge the task via "spec-ops queue complete TASK-0042"
    Then SpecOps blocks the task transition to "complete/"
    And outputs "Dual-Custody Gate: Autonomous agent task requires verified human review sign-off. Run 'spec-ops review sign TASK-0042 --identity <key-id>'".

  Scenario: Recording verified human reviewer signature into task metadata and git commit
    Given an authorized human reviewer executes "spec-ops review sign TASK-0042 --identity 'Riley <riley@example.com>'"
    When the cryptographic signature is verified against the authorized signers keyring
    Then task frontmatter records "signed_off_by: 'Riley <riley@example.com>'" and sign-off timestamp
    And subsequent execution of "spec-ops queue complete TASK-0042" merges cleanly to "main" with the structured "SpecOps-Signed-By" git trailer.
