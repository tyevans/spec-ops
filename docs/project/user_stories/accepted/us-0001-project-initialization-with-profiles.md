---
id: '0001'
title: Project Initialization with Architectural Profiles
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-CORE-01
governing_prd: PRD-0001
---

# US-0001 — Project Initialization with Architectural Profiles

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** agentic software architect,  
**I want** to initialize a new codebase with `spec-ops init --profile core,bdd,ddd`,  
**So that** my repository immediately adopts version-controlled project management, baseline ADR guardrails, and quality invariants.

## Acceptance Criteria

### Scenario 1: Bootstrapping a New Repository
```gherkin
Given a blank project directory
When the engineer executes "spec-ops init --name TestApp --profile core,bdd,ddd"
Then the directory structure "docs/project/" is created with adrs, product, user_stories, and backlog
And 7 baseline ADRs are installed into "docs/project/adrs/accepted/"
And "specops.toml" is generated with matching project settings.
```
