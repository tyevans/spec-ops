---
id: '0058'
title: Living Security Posture and Compliance Radar in Project Visualizer
status: Accepted
created: 2026-09-29
persona: Sasha (The Trust & Security Officer)
feature: FEAT-SEC-08
governing_prd: PRD-0001
---

# US-0058 — Living Security Posture and Compliance Radar in Project Visualizer

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** trust and security officer,  
**I want** the SpecOps project visualizer to provide a dedicated 'Security & Compliance Radar' tab displaying real-time secret scan health, lockfile integrity, signed commit coverage, and human sign-off completion metrics,  
**So that** I can assess organizational security posture at a glance and identify non-compliant tasks before release cut-offs.

## Acceptance Criteria

```gherkin
Scenario: Rendering the Security & Compliance Radar view
Given the standalone visualizer is open in a web browser
When the user navigates to the "Security & Compliance" tab or URL hash "#tab=security"
Then the view renders five summary metric cards:
  | Metric                     | Indicator                   |
  | Secret Scan Status         | Pass / Fail                 |
  | Lockfile Integrity         | Synchronized / Modified     |
  | Signed Commit Coverage     | Percentage (e.g., 100%)     |
  | Human Sign-off Rate        | Percentage (e.g., 95%)      |
  | Known Vulnerability Count  | Count of Low/Med/High CVEs  |
And tasks pending human sign-off are listed in an interactive triage table.
```

```gherkin
Scenario: Filtering tasks by compliance readiness
Given the user is on the Security & Compliance tab
When the user toggles the "Show Only Unsigned / Unreviewed" filter
Then the board filters to display only tasks lacking cryptographic signatures or human sign-off approvals
And clicking any row opens the task drawer displaying the exact missing compliance artifacts.
```

## Rationale & Compelling Value
Gives C-level executives, auditors, and DevSecOps leads an immediate visual dashboard of AI safety and regulatory compliance without requiring git terminal proficiency.
