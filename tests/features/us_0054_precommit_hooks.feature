Feature: Automated Pre-Commit Git Hook Installer and Supply-Chain Sentinel

  Scenario: Installing pre-commit hook in git repository
    Given an initialized SpecOps repository
    When the user runs "spec-ops security hook install"
    Then a pre-commit executable is created in ".git/hooks/pre-commit"
    And the hook invokes security and lockfile verification checks

  Scenario: Blocking commits with unapproved lockfile drift
    Given an active pre-commit hook installed
    When a commit stages an unapproved change to "uv.lock"
    Then the pre-commit hook exits with code 1
    And the git commit is aborted
