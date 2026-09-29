---
id: '0068'
title: Living Constitution Synchronization, Extension Preservation, and CI Drift Gate
status: Accepted
created: 2026-09-29
persona: Morgan (The Autonomous Coding Agent)
feature: FEAT-SCAF-03
governing_prd: PRD-0005
---

# US-0068 — Living Constitution Synchronization, Extension Preservation, and CI Drift Gate

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** autonomous coding agent,  
**I want** the repository's `AGENTS.md` operating constitution and Diataxis operating manual to automatically re-synchronize when project settings or profiles change while preserving human-authored custom invariant sections,  
**So that** I always execute work against the authoritative, up-to-date architectural laws without stale instructions or accidentally clobbering team-specific operational guidelines.

## Acceptance Criteria

```gherkin
Scenario: Re-synchronizing constitution when specops.toml settings change
Given an existing project where "specops.toml" has updated "file_length_limit = 350" and added a new quality preflight command "ruff check"
When the developer or agent runs "spec-ops scaffold agents" (or "spec-ops constitution sync")
Then "AGENTS.md" is regenerated with the updated 350-line limit and new preflight command in the Hard Invariants and Task Workflow sections
And "docs/operating-manual.md" is updated synchronously with adjusted relative documentation links
And all unchanged sections remain structurally intact.
```
```gherkin
Scenario: Preserving human-authored custom invariant extensions across sync
Given an "AGENTS.md" containing a marked user section "<!-- BEGIN CUSTOM INVARIANTS -->" with team-specific guidelines "Always run local emulator on port 9090"
When "spec-ops scaffold agents" is executed after profile updates
Then the regenerated "AGENTS.md" retains the exact contents within the custom invariants block
And updates the profile-driven sections around it without data loss.
```
```gherkin
Scenario: CI constitution drift detection gate
Given a pull request where "specops.toml" architectural settings were modified without re-running constitution sync
When "spec-ops constitution check" runs during CI preflight
Then the command detects a mismatch between "specops.toml" and root "AGENTS.md"
And exits with code 1
And outputs "Constitution Drift Error: AGENTS.md is out of sync with specops.toml. Run 'spec-ops scaffold agents' to update."
```

## Rationale & Compelling Value
Protects human customizations through delimiter boundaries while guaranteeing that AI agents never hallucinate or follow obsolete operational invariants.

---
