---
id: '0254'
title: ADR Amendment Relational Graph Edges, Living Radar Visualization, and Worker Context Hydration
status: Complete
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
- ADR-0007
governing_prds:
- PRD-0005
governing_stories:
- US-0131
target_bc: visualizer
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-04T20:30:00+00:00'
commit_signature_status: SIGNED
persona: Alex
has_signed_commits: true
dependencies:
- TASK-0253
mutation_scope:
- src/spec_ops/visualizer
---

# TASK-0254: ADR Amendment Relational Graph Edges, Living Radar Visualization, and Worker Context Hydration

## Summary
Complete the incremental ADR evolution loop by integrating amendments into the relational graph compiler, living Architecture Radar visualization, and autonomous worker/pathfinder context hydration pipelines:
1. Compile directed `(ADR)-[:amends]->(ADR)` and `(ADR)-[:supersedes]->(ADR)` edges in `spec-ops graph compile` and assert 100% graph connectivity in `spec-ops trace --verify`.
2. Update the Architecture Radar view and living visualizer detail drawers to render active amended ADRs with distinct active badges (green or cyan with an "Amended" chip) instead of strikethrough red badges.
3. Add an "Amendments" lineage section in ADR detail drawers linking directly to amending decisions, and render "Amends: <target>" when inspecting an amending decision.
4. Hydrate active amendment context into `spec-ops pathfinder inspect TASK-XXXX` and worker prompt contracts (`.task-prompt.md`) when governing ADRs have recorded amendments.

## Problem Statement & Context
When an autonomous worker picks up a backlog task governed by an amended ADR (e.g. ADR-0102 with amendments ADR-0116 and ADR-0127), it must receive not only the foundational ADR but also recent signature and capability refinements codified in the amending decisions. Furthermore, human reviewers inspecting the decision DAG in the visualizer need clear visual cues distinguishing total replacement (supersedes) from non-destructive evolution (amends).

## Detailed Objectives
1. **Relational Graph Compiler**:
   - Update `src/spec_ops/core/graph.py` to generate `amends` and `supersedes` traceability edges between ADRs.
   - Update `src/spec_ops/core/topology.py` to preserve these relations in directed graph topology.
   - Ensure `spec-ops trace --verify` accounts for ADR-to-ADR evolution edges with 100% graph connectivity.
2. **Architecture Radar & Visualizer**:
   - Update `src/spec_ops/visualizer/generator.py` to include `amends` and `amended_by` in `adrs_payload`.
   - Update `src/spec_ops/visualizer/templates/radar.js` and `src/spec_ops/visualizer/drawer_script.py` to render active status badges with an "Amended" chip, an "Amendments" lineage drawer section, and "Amends: <ADR>" links.
3. **Worker & Pathfinder Context Hydration**:
   - Update `src/spec_ops/core/pathfinder.py` to hydrate active amending ADRs in `inspect_entity`.
   - Update `src/spec_ops/worker/claimer.py` (`hydrate_task_prompt`) and `src/spec_ops/worker/review.py` to include both primary governing ADRs and active amending decisions in task prompt contracts.
4. **Testing**:
   - BDD scenarios in `tests/features/us_0131_adr_amendment_graph_and_radar.feature` and `tests/test_bdd_us0131_adr_amendment_graph_and_radar.py`.
   - End-to-end integration tests verifying graph compilation and worker hydration.

## Definition of Done
1. `spec-ops graph compile` produces directed `amends` and `supersedes` edges.
2. `spec-ops trace --verify` passes with 100% graph connectivity.
3. Architecture Radar and detail drawer render amended ADRs with active badges and lineage exploration drawers.
4. `spec-ops pathfinder inspect` and worker `.task-prompt.md` hydrate both primary and amending decisions.
5. All automated tests pass with 100% pass rate; 0 file length limit violations (<500 lines) and 0 warnings (<400 lines).
