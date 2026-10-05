---
id: '0255'
title: Default SpecOps SDLC Orchestrator Skill Scaffolding on Project Onboarding
status: Complete
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
governing_prds:
- PRD-0006
governing_stories:
- US-0132
target_bc: scaffold
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-05T04:43:43.498272+00:00'
commit_signature_status: SIGNED
persona: Alex & Morgan
mutation_scope:
- src/spec_ops/scaffold
has_signed_commits: true
---

# TASK-0255: Default SpecOps SDLC Orchestrator Skill Scaffolding on Project Onboarding

## Summary
Ensure that when a repository onboards to SpecOps (via `spec-ops init` or `spec-ops adopt`), `.agents/skills/spec-ops/SKILL.md` and supporting reference runbooks (`cli_primer.md`, `balancing_loop.md`, `orchestration_protocol.md`) are scaffolded into the project by default, without requiring explicit `--agents` flags.

## Problem Statement & Context
Currently, `init_project` only scaffolds agent adapters/skills when `agents` is explicitly passed (e.g. `--agent antigravity`). However, SpecOps is designed to be an agentic PMaC engine where autonomous agents and pairing developers operate collaboratively. Having `.agents/skills/spec-ops` present from moment zero ensures that agents entering a newly initialized or adopted project immediately discover the system constitution, CLI primer, and autonomous balancing loop protocols.

## Detailed Objectives
1. **Scaffolding Core (`src/spec_ops/scaffold/init.py`)**:
   - In `init_project`, scaffold `.agents/skills/spec-ops/` and supporting references (`cli_primer.md`, `balancing_loop.md`, `orchestration_protocol.md`) unconditionally as part of baseline project onboarding.
2. **Init Wizard & Plan (`src/spec_ops/scaffold/wizard.py`)**:
   - Include `.agents/skills/spec-ops/SKILL.md` and reference runbooks in `plan_initialization` manifest.
3. **Skill Packager Idempotency (`src/spec_ops/scaffold/skill_packager.py`)**:
   - Ensure `scaffold_skill_command` handles existing, unmodified `.agents/skills/spec-ops/` files cleanly rather than treating them as blocking collisions when running `spec-ops scaffold skill --target all` or `--target antigravity`.
4. **Verification & Tests**:
   - Executable BDD scenarios in `tests/features/us_0132_default_skill_scaffolding.feature` and `tests/test_bdd_us0132_default_skill_scaffolding.py`.
   - Update unit test assertions in `tests/test_scaffold.py` and `tests/test_init_wizard_unit.py`.
   - Ensure 0 file length limit violations (<500 lines) and 100% test pass rate.

## Definition of Done
1. `init_project` scaffolds `.agents/skills/spec-ops/SKILL.md` and all 3 reference runbooks by default.
2. `spec-ops init --name TestApp` generates the skill without any `--agent` flag.
3. `spec-ops adopt` generates the skill into brownfield repositories.
4. BDD scenarios for US-0132 pass cleanly.
5. `spec-ops health` reports 0 file limit violations and 0 warnings.
