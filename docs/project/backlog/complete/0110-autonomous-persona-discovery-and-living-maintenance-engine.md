---
id: '0110'
title: Autonomous Persona Discovery and Living Maintenance Engine
status: Complete
dependencies:
- TASK-0109
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0008
governing_prds:
- PRD-0006
governing_stories:
- US-0117
target_bc: core
---

# TASK-0110: Autonomous Persona Discovery and Living Maintenance Engine

## Summary
Implement an autonomous persona discovery and maintenance workflow (`spec-ops persona audit` and `spec-ops persona sync`) that analyzes codebase evolution, git commit histories, and stakeholder interaction patterns to detect emerging user archetypes, identify obsolete pain points, and propose version-locked updates to `docs/project/user_stories/PERSONAS.md`.

## Problem Statement & Context
Personas in `PERSONAS.md` represent the human and AI archetypes that interact with SpecOps. However, as the platform expands (introducing security sandboxing, visualizers, and multi-worker rescue), new stakeholders emerge (e.g. compliance officers, executive leaders, external tool consumers). Without an automated mechanism to audit persona coverage against evolving repository capabilities, personas drift from reality, leading to blind spots during PRD and story generation.

## User Stories & Scenarios Satisfied
- **US-0117: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Coordination**
  - *Scenario: Autonomous Persona Discovery and Coverage Audit*
    - Given a repository with evolving bounded contexts and newly introduced architectural roles
    - When the orchestrator executes "spec-ops persona audit"
    - Then the engine inspects all accepted PRDs, stories, and git commits
    - And highlights uncovered archetypes with recommended profile drafts for `PERSONAS.md`.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: New persona discovery module in `src/spec_ops/core/persona_engine.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests asserting that persona markdown parsing and serialization preserve YAML frontmatter and markdown sections idempotently.
- **Mutmut Mutation Scope**: Core persona matching and gap analysis achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. CLI commands `spec-ops persona audit` and `spec-ops persona sync` available via public CLI entry point.
2. Automatically identifies unrepresented archetypes referenced across PRD target personas.
3. Provides interactive diff preview before writing updates to `docs/project/user_stories/PERSONAS.md`.
4. 100% test pass rate verifying observable contracts without private mock backdoors.

## Acceptance Criteria

### Scenario 1: Autonomous Persona Discovery and Coverage Audit*
```gherkin
Given the system is initialized and ready
When the user executes the workflow for "Autonomous Persona Discovery and Living Maintenance Engine"
Then Autonomous Persona Discovery and Coverage Audit*
And observable outputs satisfy public contracts without backdoor tampering.
```
