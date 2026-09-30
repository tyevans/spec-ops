---
id: '0003'
title: Product Discovery, Web PRD Studio & Living UAT Verification
status: Accepted
created: 2026-09-29
target_persona: Taylor (The Product Manager & Technical Writer)
component: prd
---

# PRD-0003 — Product Discovery, Web PRD Studio & Living UAT Verification

## Who this is for

- **Taylor (The Product Manager & Technical Writer)**: Needs an intuitive web-based interface and low-code Gherkin assistant to author falsifiable requirements and track shipping progress.
- **Alex (The Agentic Systems Architect)**: Needs PRD checkable outcomes to decompose cleanly into vertical slices, user stories, and bounded architectural spikes.
- **Jordan (The AI-Native Engineering Lead)**: Needs automated PRD shipping verification and customer-ready UAT receipt generation before releases are cut.

## What the person cannot do today

- **Terminal Intimidation**: Product managers and technical writers are alienated by raw git worktrees, YAML frontmatter syntax, and terminal CLI commands.
- **Unfalsifiable PRD Outcomes**: PRD outcomes are frequently written as vague qualitative aspirations rather than checkable, falsifiable behavioral tests.
- **Scope Creep & Duplication**: Product scope evolves incrementally, but existing decomposition tools re-generate duplicate tasks or destroy active backlog work.
- **Speculative Feature Rot**: Unproven technical assumptions rot in backlogs without empirical spike validation and timeboxed proof-of-concept sandboxes.
- **Disconnected UAT**: Non-technical stakeholders cannot execute user acceptance tests (UAT) independently to confirm that features satisfy real customer workflows.

## What good looks like

1. **Interactive Web PRD Studio**:
   - Local, lightweight web application providing visual form authoring, Gherkin scenario generation, and live validation directly synced to git.
2. **Deterministic Lifecycle Gates**:
   - Enforced stage progressions (`idea` -> `shaped` -> `accepted` -> `shipped`) gated by checkable outcome coverage and falsifiability linters.
3. **Incremental PRD Delta Decomposition**:
   - Non-destructive delta decomposition (`spec-ops prd decompose --diff`) that discovers added or modified outcomes without disturbing active backlog tasks.
4. **Governed Spike Lifecycle & Automated ADR Synthesis**:
   - Disposable spike worktree sandboxes under `spikes/` with empirical hypothesis validation that automatically synthesizes accepted ADRs upon completion.
5. **Living Customer UAT Matrix & Acceptance Receipts**:
   - Customer-ready UAT verification interface generating non-technical sign-off receipts and automated release notes.

## What this does not do

- It does not replace customer discovery interviews or qualitative user research sessions.
- It does not sync with proprietary closed-source roadmapping tools without explicit export adapters.
- It does not allow unvalidated, unfalsifiable outcomes to bypass quality gates into `accepted/`.

## Checkable Outcomes

1. Running `spec-ops prd studio --open` launches a lightweight local web interface for authoring and validating PRDs without terminal interaction.
2. Running `spec-ops prd lint` flags unfalsifiable outcomes and missing persona links with line-level suggestions and remediation hints.
3. Running `spec-ops prd audit PRD-0003` computes test coverage across checkable outcomes and linked BDD scenarios.
4. Running `spec-ops prd ship PRD-0003` verifies 100% completion of implementing tasks and generates automated customer release notes.
5. Running `spec-ops prd uat PRD-0003 --export` generates a tamper-evident HTML/PDF acceptance matrix signed off by stakeholders.

## Linked User Stories

- `US-0043`
- `US-0044`
- `US-0045`
- `US-0046`
- `US-0047`
- `US-0048`
- `US-0049`
- `US-0050`
- `US-0094`
- `US-0095`
- `US-0096`
- `US-0097`
- `US-0098`
- `US-0099`
- `US-0100`

## Implementing Backlog Tasks

- `TASK-0034`
- `TASK-0035`
- `TASK-0036`
- `TASK-0037`
- `TASK-0038`
- `TASK-0039`
- `TASK-0040`
- `TASK-0041`
- `TASK-0042`
- `TASK-0043`
- `TASK-0091`

