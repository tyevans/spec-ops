---
id: '0125'
title: Autonomous Continuous Balancing Loop and Tri-Directional Discovery in SpecOps
  Skill
status: Complete
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0005
governing_prds:
- PRD-0006
governing_stories:
- US-0117
target_bc: core
---

# TASK-0125: Autonomous Continuous Balancing Loop and Tri-Directional Discovery in SpecOps Skill

## Summary
Enhance `.agents/skills/spec-ops/SKILL.md` and associated orchestration references to institute an autonomous continuous balancing loop and tri-directional discovery protocol. Enable the orchestrator to automatically decompose PRDs, inspect user stories, identify ADRs with low/zero implementing tasks, synthesize balanced task batches, synchronize Diataxis documentation, and loop autonomously across SDLC phases.

## Problem Statement & Context
The current `/spec-ops` skill acts as an advisory prompt that presents backlog status and halts, requiring interactive user prodding at each step. It lacks continuous looping momentum and proactive tri-directional discovery (auditing PRDs for undecomposed capabilities, inspecting user stories for next journeys, checking ADRs for architectural coverage, and ensuring Diataxis docs stay synchronized). To fulfill its vision as an autonomous "company in a box", `/spec-ops` must continuously cycle through discovery, refinement, implementation, and documentation in a self-balancing loop.

## Key Capabilities & Procedures
1. **Tri-Directional Discovery Audit**:
   - **PRD Decomposition**: Scan accepted PRDs for checkable outcomes and capabilities lacking user stories or tasks.
   - **User Story Inspection**: Scan accepted BDD user stories for unstarted or partially implemented acceptance scenarios.
   - **ADR Coverage Audit**: Scan accepted ADRs (`docs/project/adrs/accepted/`) to identify architectural decisions with low/zero linked implementing tasks.
   - **Diataxis Documentation Balance**: Audit `docs/` to ensure new features, CLI subcommands, and workflows have corresponding how-to recipes and reference specs.
2. **Autonomous Continuous Looping Protocol**:
   - Establish explicit orchestrator loop semantics:
     `[Tri-Directional Discovery] -> [JIT Refinement & Task Slicing] -> [In-Worktree Implementation] -> [Preflight Verification & Integration] -> [Diataxis Doc Sync] -> [Next Cycle]`
   - Autonomous looping continues balancing work across all bounded contexts and documentation layers without stalling or awaiting manual step-by-step steering.

## Definition of Done (Blackbox Frontdoor TDD)
1. `.agents/skills/spec-ops/SKILL.md` updated with the Continuous Balancing Loop and Tri-Directional Discovery protocol.
2. `.agents/skills/spec-ops/references/balancing_loop.md` authored detailing the loop lifecycle, audit criteria, and autonomous dispatch guidelines.
3. Codebase health (`uv run spec-ops health`) passes with 0 violations and 0 warnings.
