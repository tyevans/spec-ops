@us_0066 @scaffold
Feature: Interactive Guided Initialization Wizard and Headless CI Automation Scaffolding
  As a software engineer setting up or onboarding a project to SpecOps,
  I want an interactive terminal initialization wizard that prompts for project topology, profiles, and workflow tooling, alongside headless flags for automated scripting,
  So that I can effortlessly bootstrap a compliant Project Management as Code environment with full visibility into generated artifacts without memorizing complex CLI syntax.

  Scenario: Interactive terminal onboarding wizard with live configuration preview
    Given a clean terminal session in an uninitialized directory
    When the developer runs "spec-ops init --interactive" in an interactive TTY selecting "core,security" profiles and declaring a "billing" bounded context
    Then the wizard renders a formatted preview of "specops.toml"
    And displays a dry-run summary tree of files and baseline ADRs to be generated
    And upon user confirmation scaffolds the configured directory layout, "specops.toml", "AGENTS.md", and workflow files.

  Scenario: Unattended headless initialization for CI and automation templates
    Given an automated CI provisioning pipeline in a blank directory
    When the container executes "spec-ops init --headless --name PaymentService --profile core"
    Then the repository is scaffolded non-interactively without stdin blocking in under 2 seconds.

  Scenario: Unattended headless initialization with custom flags
    Given a blank project directory in an automated script or CI runner
    When the automation executes "spec-ops init --non-interactive --name MicroApp --profile core,bdd --ci github --diataxis --yes"
    Then the command executes without prompting for stdin
    And scaffolds the exact specified files with exit code 0
    And writes a machine-readable initialization receipt to ".specops-scaffold.json" detailing created paths and profile checksums.

  Scenario: Initialization dry-run preview mode
    Given a developer testing initialization parameters
    When they run "spec-ops init --dry-run --profile core,bdd"
    Then the system prints planned files and generated "specops.toml" without creating files on disk.

  Scenario: Initialization dry-run preview mode with collisions
    Given an existing codebase
    When the developer runs "spec-ops init --profile core,bdd,ddd --dry-run"
    Then no files or directories are written to disk
    And the terminal outputs the planned file manifest, detected profile configurations, and any potential filename collisions.

  Scenario: Validation error aborts cleanly on invalid profile
    Given an uninitialized directory
    When the developer runs "spec-ops init --profile core,unknown_profile"
    Then the command aborts with exit code 1
    And displays an explanatory validation diagnostic.

  Scenario: Validation error aborts cleanly on duplicate bounded context
    Given an uninitialized directory
    When the developer runs "spec-ops init --bc billing --bc billing"
    Then the command aborts with exit code 1
    And displays an explanatory validation diagnostic.
