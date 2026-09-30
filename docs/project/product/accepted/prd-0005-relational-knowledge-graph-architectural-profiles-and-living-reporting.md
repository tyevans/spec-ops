---
id: '0005'
title: Relational Knowledge Graph, Architectural Profiles & Living Reporting
status: Accepted
created: 2026-09-29
target_persona: Alex (The Systems Architect) & Jordan (The Engineering Lead)
component: core
---

# PRD-0005 — Relational Knowledge Graph, Architectural Profiles & Living Reporting

## Who this is for

- **Alex (The Agentic Systems Architect)**: Needs high-performance incremental graph caching, cycle detection, AST frontmatter resilience, and modular profile inheritance.
- **Jordan (The AI-Native Engineering Lead)**: Needs live worker fleet telemetry, bottleneck radar, multi-perspective matrix visualization, and automated standup digests.
- **Riley (The Human IC Developer)**: Needs sub-50ms terminal graph reachability pathfinding, blast radius traversal, and deep-linked URL permalinks.

## What the person cannot do today

- **Compilation Bottlenecks**: Re-scanning and re-parsing hundreds of markdown files on every CLI call degrades developer experience and slows CI pipelines.
- **Deadlocking Dependency Cycles**: Circular dependencies in task and PRD graphs lead to deadlocked curation queues and worker freezes.
- **Profile & Constitution Drift**: Architectural profiles and AGENTS.md constitutions drift between enterprise repositories without automated version upgrade paths.
- **Fragmented Delivery Visibility**: Engineering leads lack unified visibility into multi-agent fleet operations, blocker cascades, and milestone burnup.

## What good looks like

1. **Content-Addressed Incremental Graph Caching**:
   - SHA-256 content-addressed caching compiling large PMaC graphs in under 50ms with resilient AST parsing and diagnostic source mapping.
2. **Deterministic DAG Topology & Cycle Detection**:
   - Tarjan SCC cycle detection and topological sorting ensuring deadlock-free execution queues and blast radius analysis.
3. **Modular Profile Inheritance & Living Constitution Sync**:
   - Composable profiles with semantic diffs, migration tooling, and automated AGENTS.md updates preserving local custom extensions.
4. **Reactive Backlog Replenishment & Cross-Process Locking**:
   - In-memory graph event bus triggering reactive backlog replenishment upon task completion, protected by cross-process file locks.
5. **Zero-Dependency Portable Visualizer & Fleet Telemetry**:
   - Standalone HTML bundle with 2D force-directed canvas, Gantt timeline, unified multi-perspective project matrix, and live worker fleet telemetry.

## What this does not do

- It does not require a persistent background database server (PostgreSQL/Redis); state is compiled directly from git.
- It does not replace general-purpose enterprise BI dashboards; it specializes purely in PMaC repository health and delivery telemetry.

## Checkable Outcomes

1. Running `spec-ops graph compile --incremental` builds the relational graph from disk cache in <50ms for 1,000 entities.
2. Running `spec-ops graph cycles` detects circular dependencies in task graphs with exact cycle node paths and remediation hints.
3. Running `spec-ops profile upgrade enterprise-security` diffs local ADRs against upstream profile versions and proposes non-destructive migrations.
4. Running `spec-ops visualizer --build dist/visualizer.html` compiles all views, matrices, and telemetry into a self-contained offline bundle.
5. Navigating visualizer deep links (`#tab=matrix`, `#entity=TASK-0013`) activates target views and detail drawers with URL state synchronization.

## Linked User Stories

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
- `US-0059`
- `US-0060`
- `US-0061`
- `US-0062`
- `US-0063`
- `US-0064`
- `US-0065`
- `US-0066`
- `US-0067`
- `US-0068`
- `US-0069`
- `US-0070`
- `US-0071`
- `US-0072`
- `US-0073`
- `US-0074`
- `US-0075`
- `US-0076`
- `US-0077`
- `US-0078`
- `US-0079`
- `US-0101`
- `US-0102`
- `US-0103`
- `US-0104`
- `US-0105`
- `US-0106`
- `US-0107`

## Implementing Backlog Tasks

- `TASK-0001`
- `TASK-0004`
- `TASK-0006`
- `TASK-0013`
- `TASK-0057`
- `TASK-0058`
- `TASK-0059`
- `TASK-0060`
- `TASK-0061`
- `TASK-0062`
- `TASK-0063`
- `TASK-0064`
- `TASK-0065`
- `TASK-0066`
- `TASK-0067`
- `TASK-0068`
- `TASK-0069`
- `TASK-0070`
