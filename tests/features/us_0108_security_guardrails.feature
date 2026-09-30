Feature: Enterprise Security Profile Scaffolding and Living Constitution Guardrails
  As a trust and security officer
  I want spec-ops init --profile security to scaffold baseline security ADRs, a Diataxis-compliant docs/project/SECURITY.md vulnerability disclosure policy, pre-commit secret detection hooks, and non-negotiable security invariants into AGENTS.md
  So that every new or existing enterprise repository immediately adopts standardized, zero-trust autonomous execution guardrails from day zero without manual policy authoring.

  Scenario: Scaffolding a repository with the security architectural profile
    Given a blank or existing project directory for "SecureEnterpriseApp"
    When the security officer executes "spec-ops init --name SecureEnterpriseApp --profile core,bdd,ddd,security"
    Then "docs/project/adrs/accepted/" includes baseline security ADRs for process sandboxing, lockfile immutability, and credential leak defense
    And "docs/project/SECURITY.md" is scaffolded with vulnerability disclosure workflows, PGP key fingerprints, and incident reporting contacts
    And "specops.toml" is generated containing an active "[security]" configuration block enabling secret scanning and lockfile immutability
    And the command exits with returncode 0.

  Scenario: Dynamic injection of security invariants into AGENTS.md
    Given a project configured with the security architectural profile
    When the developer or orchestrator executes "spec-ops scaffold agents"
    Then the generated "AGENTS.md" at the repository root contains a "Security & Supply-Chain Hard Invariants" section
    And the constitution explicitly forbids agents from hardcoding credentials, modifying unapproved lockfiles, or executing non-allowlisted shell commands
    And running "spec-ops health" reports 0 file limit violations (<500 lines) and 0 constitution drift warnings.

  Scenario: Preflight detection of degraded or missing security configuration
    Given a repository configured with the security profile where "docs/project/SECURITY.md" was removed or modified out-of-spec
    When "spec-ops health --security" executes
    Then the command exits with returncode 1
    And reports "Security Policy Invariant Violated: docs/project/SECURITY.md is missing or invalid. Run 'spec-ops profile sync security' to restore".

  Scenario: Synchronizing security profile across active worker worktrees and rescue preflight
    Given a repository configured with the security profile having an active worktree missing "docs/project/SECURITY.md"
    When the developer executes "spec-ops profile sync security"
    Then "docs/project/SECURITY.md" is restored in both the root repository and the active worktree
    And executing "spec-ops health --security" in the worktree succeeds with returncode 0

