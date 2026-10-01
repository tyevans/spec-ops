# SpecOps Multi-Agent SDLC Orchestration Protocol

This document defines the multi-agent coordination protocol used by the SpecOps inline orchestrator. It establishes how autonomous subagents are dispatched, how they consult living specifications, and how failures are treated as first-class actionable work items.

---

## 1. Core Principles

1. **Inline Coordination (No Blind Process Forking)**:
   - The primary orchestrator runs directly within the active agent session.
   - Subagents are invoked via native agent tools (`invoke_subagent`, `send_message`) rather than detached background shell forks. This preserves context, allows dynamic intervention, and keeps the lead orchestrator informed.

2. **Living Specification as Ground Truth**:
   - All subagents must consult version-locked PMaC specifications in `docs/project/` before making architectural or code modifications:
     - Personas: `docs/project/user_stories/PERSONAS.md`
     - PRDs: `docs/project/product/accepted/`
     - User Stories: `docs/project/user_stories/accepted/`
     - ADRs: `docs/project/adrs/accepted/`
     - Backlog: `docs/project/backlog/`

3. **Strict Invariant Governance**:
   - Every subagent must honor hard invariants:
     - File length <500 lines (proactive warning at >=400 lines) per ADR-0002.
     - Blackbox frontdoor verification (ADR-0003, ADR-0006) without private backdoor mocks.
     - Strict backlog isolation on feature branches (ADR-0005).
     - Lockfile immutability and allowlisted commands.

4. **Actionable Orchestration Failure Protocol**:
   - When running on this project, any orchestration failure (subagent stall, tool error, spec ambiguity, preflight failure) is an **actionable task**:
     - Document the failure immediately as a high-priority bug in `docs/project/backlog/proposed/`.
     - Dispatch remediation to resolve the root cause before moving forward.

5. **Autonomous Continuous Balancing Loop**:
   - Maintain continuous development velocity across PRD value, BDD user journeys, ADR architectural invariants, and Diataxis documentation without waiting for manual step-by-step steering. Governed by [Continuous Balancing Loop](./balancing_loop.md).

---

## 2. Specialized Subagent Archetypes

When orchestrating across the SDLC, the lead agent dispatches specialized subagents:

| Role Name | Scope | Primary Inputs | Primary Outputs |
|---|---|---|---|
| `persona-agent` | Persona discovery & maintenance | User feedback, market shifts, codebase evolution | Updates to `docs/project/user_stories/PERSONAS.md` |
| `prd-agent` | Product discovery & PRD authoring | Unmet user needs, persona pain points | PRD draft in `docs/project/product/accepted/` |
| `story-agent` | Multi-faceted BDD user stories | Accepted PRD, personas, bounded contexts | Gherkin stories in `docs/project/user_stories/accepted/` |
| `slicing-agent` | INVEST task decomposition & spikes | User stories, architecture seams | Proposed tasks in `docs/project/backlog/proposed/` |
| `refinement-agent` | JIT backlog curation & DoR validation | Proposed queue, living ADRs, AST seams | Refined tasks in `docs/project/backlog/refined/` |
| `implementation-agent` | In-worktree TDD implementation | Refined task, governing ADRs/stories | Code changes, tests, commit trailers in worktree |
| `review-agent` | Architectural verification & preflight | Task diff, test suite, security policies | Verification report, preflight sign-off |

---

## 3. Step-by-Step Lifecycle Workflow

### Phase 1: Persona Maintenance
1. Dispatch `persona-agent` to evaluate existing personas in `docs/project/user_stories/PERSONAS.md`.
2. Ask: Are new archetypes emerging (e.g. security officers, non-technical PMs, external API consumers)? Are existing pain points addressed or evolving?
3. Update `PERSONAS.md` atomically with clear roles, pain points, and goals.

### Phase 2: Product Discovery & Living PRDs
1. Dispatch `prd-agent` to draft or shape a PRD under `docs/project/product/accepted/`.
2. Include: "Who this is for", "What the person cannot do today", "What good looks like", and "Checkable Outcomes".
3. Verify PRD validity: `uv run spec-ops prd lint docs/project/product/accepted/PRD-XXXX.md`.
4. Register in `docs/project/product/REGISTRY.md`.

### Phase 3: BDD User Story Generation
1. Dispatch `story-agent` to author multi-faceted user stories:
   - By Persona: Grounded in target archetypes.
   - By Bounded Context: Aligned with domain architecture (ADR-0007).
   - By Feature: Clear vertical slices.
2. Author executable Gherkin scenarios (`Given ... When ... Then`) verifiable via public frontdoors.
3. Save in `docs/project/user_stories/accepted/us-XXXX-....md` and register in `REGISTRY.md`.

### Phase 4: INVEST Task Decomposition
1. Dispatch `slicing-agent` to decompose stories into thin vertical slices (<500 lines per file):
   - Independent, Negotiable, Valuable, Estimable, Small, Testable.
   - If technical uncertainty exists, scaffold an architectural spike (`SPIKE-XXXX`).
2. Scaffold tasks using `uv run spec-ops task create` into `docs/project/backlog/proposed/`.

### Phase 5: JIT Refinement & Definition of Ready
1. Maintain a ready buffer of ~10 tasks in `docs/project/backlog/refined/`.
2. Run cognitive curation: `uv run spec-ops curate --infer`.
3. Validate Definition of Ready (DoR):
   - Dependencies mapped.
   - Governing PRDs, stories, and ADRs cited.
   - Executable Gherkin scenarios defined.
   - Property invariants and mutation targets identified.

### Phase 6: Subagent Implementation & Peer Consultation
1. Create isolated task worktree: `uv run spec-ops worktree create TASK-XXXX`.
2. Dispatch `implementation-agent` inside worktree.
3. Subagent must:
   - Consult cited ADRs and stories.
   - Write tests first (TDD) through public frontdoors.
   - Maintain file length <500 lines.
   - Keep commits structured with RFC 822 trailers (`SpecOps-Task: TASK-XXXX`).

### Phase 7: Verification, Preflight & Integration
1. Run preflight verification:
   ```bash
   uv run spec-ops health
   uv run pytest
   uv lock --check
   ```
2. Open pull request or perform merge under `MERGE_LOCK`.
3. Synchronize `PRIORITY.md` and transition task to `complete/` on `main`.

---

## 4. Failure Recovery & Continuous Dogfooding

If any subagent encounters a blocker, stall, or test failure:
1. **Never Silently Discard**: Inspect diagnostics using `uv run spec-ops rescue inspect TASK-XXXX`.
2. **Salvage or Reset**: Salvage working files with `spec-ops rescue salvage` or reset with anti-loop memory via `spec-ops rescue reset --anti-loop`.
3. **Log Orchestration Bug**: If the toolchain, script, or prompt caused the failure, record an actionable task in `docs/project/backlog/proposed/` to fix it for future runs.
