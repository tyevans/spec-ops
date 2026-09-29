---
id: '0001'
title: SpecOps Autonomous Project Management Engine
status: Accepted
created: 2026-09-29
target_persona: Alex
component: core
---

# PRD-0001 — SpecOps Autonomous Project Management Engine

## Who this is for

- **Alex (The Systems Architect)**: Needs project management as code living directly in git to eliminate specification drift.
- **Jordan (The Engineering Lead)**: Needs real-time 2D traceability graphs and automated JIT backlog refinement.
- **Morgan (The Autonomous Agent)**: Needs unambiguous task contracts citing governing ADRs and isolated worktrees for conflict-free execution.

## What the person cannot do today

- **Specification Drift**: External SaaS tools (Jira, Linear) drift from running code, blinding coding agents to true architectural constraints.
- **Agent Merge Conflicts**: Concurrent multi-agent workers editing shared backlog files cause guaranteed git merge conflicts on PR integration.
- **Mock Rot**: Tests relying on private backdoors and direct database mutation mask production bugs.
- **Monolithic File Decay**: Large monolithic files (>500 lines) degrade LLM reasoning and break automated refactorings.

## What good looks like

1. **Specification as Code (PMaC)**:
   - Personas, PRDs, User Stories, Backlog Tasks, and ADRs live as Markdown with YAML frontmatter under `docs/project/`.
2. **Architectural Profiles & Baseline ADRs**:
   - Composable baseline ADR bundles (`core`, `bdd`, `ddd`) establish foundational quality laws on project initialization.
3. **Three-Tier Autonomous Delivery Loop**:
   - PRD decomposition into thin vertical slices and spikes.
   - JIT backlog curation maintaining a lean buffer of ~10 tasks in `refined/`.
   - Autonomous multi-worker engine running in isolated git worktrees with strict backlog isolation.
4. **Living 2D Graph Visualizer**:
   - Zero-dependency canvas visualizing directional relationships and health metrics with standalone HTML export.

## What this does not do

- It does not replace git; git is the single source of truth.
- It does not require external database services; all state is version-controlled Markdown and TOML.

## Checkable Outcomes

1. Running `spec-ops init` scaffolds the full project structure with 7 baseline ADRs and configuration.
2. Running `spec-ops health` validates that zero source files exceed 500 lines and backlog indices match disk state.
3. Running `spec-ops prd decompose PRD-0001` generates vertical slices and user stories.
4. Running `spec-ops curate` refines unblocked proposed tasks JIT to reach the buffer target.
5. Running `spec-ops visualizer --build dist/visualizer.html` generates a self-contained interactive 2D graph bundle.
6. Navigating visualizer deep links (`#tab=...`, `#entity=...`) activates target views and detail drawers with URL state synchronization.

## Linked User Stories

- `US-0001`
- `US-0002`
- `US-0003`
- `US-0004`
- `US-0005`
- `US-0006`
- `US-0007`
- `US-0008`
- `US-0009`
- `US-0010`
- `US-0011`
- `US-0012`
- `US-0013`
- `US-0014`
- `US-0015`
- `US-0016`
- `US-0017`
- `US-0018`
- `US-0019`
- `US-0020`
- `US-0021`
- `US-0022`
- `US-0023`
- `US-0024`
- `US-0025`
- `US-0026`
- `US-0027`
- `US-0028`
- `US-0029`
- `US-0030`
- `US-0031`
- `US-0032`
- `US-0033`
- `US-0034`
- `US-0035`
- `US-0036`
- `US-0037`
- `US-0038`
- `US-0039`
- `US-0040`
- `US-0041`
- `US-0042`
- `US-0043`
- `US-0044`
- `US-0045`
- `US-0046`
- `US-0047`
- `US-0048`
- `US-0049`
- `US-0050`
- `US-0051`
- `US-0052`
- `US-0053`
- `US-0054`
- `US-0055`
- `US-0056`
- `US-0057`
- `US-0058`

## Implementing Backlog Tasks

- `TASK-0001`
- `TASK-0002`
- `TASK-0003`
- `TASK-0004`
- `TASK-0005`
- `TASK-0006`
- `TASK-0007`
- `TASK-0008`
- `TASK-0009`
- `TASK-0010`
- `TASK-0011`
- `TASK-0012`
- `TASK-0013`
- `TASK-0014`
- `TASK-0015`
- `TASK-0016`
- `TASK-0017`
- `TASK-0018`
- `TASK-0019`
- `TASK-0020`
- `TASK-0021`
- `TASK-0022`
- `TASK-0023`
