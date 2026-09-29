@security @us_0052
Feature: Automated Secret and Credential Leak Detection in Agent Worktrees

  Scenario: Blocking commits containing high-entropy secrets or private tokens
    Given an autonomous agent worktree where the agent has written an OpenAI API key or AWS secret access key into a source file
    When the worker engine executes preflight verification prior to git commit
    Then "spec-ops health --security" detects the high-entropy credential pattern
    And the preflight check exits with returncode 1, aborting the commit
    And diagnostic feedback listing the offending file path and masked token snippet is returned to the agent prompt for self-healing remediation.

  Scenario: Clean worktree passes preflight credential scan
    Given an autonomous agent worktree with valid feature modifications containing zero credentials, private keys, or tracked .env files
    When the preflight command "spec-ops health --security" executes
    Then the check exits with returncode 0
    And reports "Security Invariant Met: 0 credential leaks detected".
