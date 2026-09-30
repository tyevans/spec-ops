@security @us_0055
Feature: US-0055 Cryptographic Commit Verification and Dual-Custody Human Sign-Off Gate

  Scenario: Blocking integration of unsigned git commits into main
    Given a project configured with "[security.compliance] require_signed_commits = true"
    When "spec-ops queue complete <task-id>" or worker squash-merge is executed on a branch with unsigned commits
    Then the command aborts with returncode 1
    And outputs "Compliance Violation: Commit lacks valid cryptographic signature (GPG/SSH)".

  Scenario: Enforcing dual-custody human review sign-off
    Given an autonomous agent has passed all preflight checks on a feature branch
    When the agent attempts to finalize the task without human approval
    Then SpecOps blocks task transition to "complete/"
    And requires an authorized human reviewer to execute "spec-ops review sign <task-id> --identity <key-id>"
    And once signed, task frontmatter records "signed_off_by: <reviewer>" and the task merges cleanly.
