---
id: '0108'
title: Enterprise Security Profile Scaffolding and Living Constitution Guardrails
status: Accepted
created: 2026-09-29
persona: Sasha (The Trust & Security Officer)
feature: FEAT-SEC-01
governing_prd: PRD-0002
---

# US-0108 — Enterprise Security Profile Scaffolding and Living Constitution Guardrails

## Governing PRD
- [`PRD-0002: Enterprise Security, Supply-Chain & Compliance Engine`](../../product/accepted/prd-0002-enterprise-security-supply-chain-and-compliance-engine.md)

## User Story

**As a** trust and security officer (Sasha),
  - **I want** `spec-ops init --profile security` (or `spec-ops profile apply security`) to scaffold baseline security ADRs, a Diataxis-compliant `docs/project/SECURITY.md` vulnerability disclosure policy, pre-commit secret detection hooks, and non-negotiable security invariants into `AGENTS.md`,
  - **So that** every new or existing enterprise repository immediately adopts standardized, zero-trust autonomous execution guardrails from day zero without manual policy authoring.

## Acceptance Criteria

```gherkin
Scenario: Scaffolding a repository with the security architectural profile
Given a blank or existing project directory for "SecureEnterpriseApp"
When the security officer executes "spec-ops init --name SecureEnterpriseApp --profile core,bdd,ddd,security"
Then "docs/project/adrs/accepted/" includes baseline security ADRs for process sandboxing, lockfile immutability, and credential leak defense
And "docs/project/SECURITY.md" is scaffolded with vulnerability disclosure workflows, PGP key fingerprints, and incident reporting contacts
And "specops.toml" is generated containing an active "[security]" configuration block enabling secret scanning and lockfile immutability
And the command exits with returncode 0.
```
```gherkin
Scenario: Dynamic injection of security invariants into AGENTS.md
Given a project configured with the security architectural profile
When the developer or orchestrator executes "spec-ops scaffold agents"
Then the generated "AGENTS.md" at the repository root contains a "Security & Supply-Chain Hard Invariants" section
And the constitution explicitly forbids agents from hardcoding credentials, modifying unapproved lockfiles, or executing non-allowlisted shell commands
And running "spec-ops health" reports 0 file limit violations (<500 lines) and 0 constitution drift warnings.
```
```gherkin
Scenario: Preflight detection of degraded or missing security configuration
Given a repository configured with the security profile where "docs/project/SECURITY.md" was removed or modified out-of-spec
When "spec-ops health --security" executes
Then the command exits with returncode 1
And reports "Security Policy Invariant Violated: docs/project/SECURITY.md is missing or invalid. Run 'spec-ops profile sync security' to restore".
-
```

## Rationale & Compelling Value
- **Enterprise Adoption**: Solves corporate-wide rollout friction. Security teams can execute a single CLI command across hundreds of microservices or brownfield repositories to instantly install uniform security policies and configs.
  - **Regular Usage**: Embedded in `spec-ops health` and local pre-commit hooks. Every developer and autonomous worker preflight asserts that `AGENTS.md` and `SECURITY.md` remain intact.
  - **Compelling Value**: Converts security directives from static, ignored wiki documents into machine-executable constitutional rules that autonomous agents and human contributors cannot bypass.

---
