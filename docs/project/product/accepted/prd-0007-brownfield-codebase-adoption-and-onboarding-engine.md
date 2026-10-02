---
id: '0007'
title: Brownfield Codebase Adoption, Technical Debt Baselining & Documentation Bridging Engine
status: Accepted
created: 2026-10-02
target_persona: Devon (The Brownfield Migration Engineer)
component: adopt
---

# PRD-0007 — Brownfield Codebase Adoption, Technical Debt Baselining & Documentation Bridging Engine

## Who this is for

- **Devon (The Brownfield Migration Engineer)**: Staff engineer or platform lead onboarding mature, production repositories (like `redstring`) into SpecOps without breaking established CI pipelines, introducing lockfile churn, or crashing against greenfield assumptions.
- **Sasha (The Trust & Security Officer)**: Needs dependency, license, and compliance audits to execute accurately against the target repository's virtual environment without altering the project's dependency manifest.
- **Alex (The Agentic Systems Architect)**: Wants existing codebases to establish SpecOps PMaC specifications, bidirectional traceability, and living 2D graph visualizers alongside pre-existing documentation sites.

## What the person cannot do today

- **Lockfile Contamination in CI**: Existing deployment workflow scaffolding assumes SpecOps is a declared runtime dependency in `pyproject.toml` or `uv.lock`. When deployed in clean GitHub Actions runner environments on third-party repositories, CI fails because `spec-ops` is not installed.
- **Conflicting Documentation Deployments**: Target repositories often already run documentation systems (such as MkDocs or Sphinx) with existing `.github/workflows/docs.yml` deploying to GitHub Pages under the `pages` concurrency group. Running `spec-ops adopt` creates colliding deployment jobs that fail or overwrite each other.
- **Visualizer Navigation Disconnect**: Existing documentation setups lack a bridge to the SpecOps interactive 2D graph visualizer, preventing teams from exploring specification graphs and burndown metrics alongside their user guides.
- **Immediate Health Failures on Legacy Code**: Greenfield invariants (such as the strict `<500` lines per file limit) immediately fail existing production files upon adoption unless incremental debt baselines and automated decomposition blueprints are established.

## What good looks like

1. **Self-Contained Standalone Tool Execution (`--github-pages`)**:
   - `spec-ops adopt --github-pages` scaffolds `.github/workflows/deploy-pages.yml` configured to invoke SpecOps via standalone tool execution (`uv tool run --from git+https://github.com/tyevans/spec-ops.git spec-ops docs build --base-url /${{ github.event.repository.name }}/`).
   - Executes cleanly on standard GitHub Actions runners without requiring `spec-ops` to be declared in the target repository's `pyproject.toml` or `uv.lock`.
2. **Intelligent Documentation & Workflow Conflict Deconfliction**:
   - `spec-ops adopt` detects pre-existing documentation generators (`mkdocs.yml`, Sphinx `conf.py`) and existing Pages workflows (`.github/workflows/docs.yml`, concurrency group `pages`).
   - Flags deployment collisions and provides actionable bridging recommendations, including flags to deconflict workflows (`--deconflict-workflow`) or guide migration to SpecOps Diataxis docs.
3. **Interactive 2D Visualizer Publishing & Cross-Navigation**:
   - `spec-ops docs build` generates both the Diataxis documentation portal at `/` and the interactive 2D graph visualizer at `/visualizer/index.html`.
   - Every compiled documentation page includes a header navigation link to `/visualizer/`.
4. **Grandfathered Technical Debt Ratchet**:
   - `spec-ops adopt --grandfather-debt` records existing oversized files into `.spec-ops/debt_baseline.json`.
   - Emits structured AST seam decomposition refactor tasks into `docs/project/backlog/proposed/`.
   - `spec-ops health` allows grandfathered files to pass provided their line count does not increase, while newly created files strictly adhere to the limit.
5. **Target Virtualenv Site-Packages Inspection**:
   - Security and compliance commands discover and audit dependencies directly inside the target repository's `.venv/` site-packages without in-repo configuration changes.

## What this does not do

- It does not rewrite or overwrite existing repository documentation without explicit user instruction.
- It does not force existing projects to abandon their chosen package managers or lockfile formats.
- It does not waive file length or architecture rules for newly authored code files.

## Checkable Outcomes

1. Executing `spec-ops adopt --github-pages` on a repository without `spec-ops` in `pyproject.toml` scaffolds `.github/workflows/deploy-pages.yml` containing the `uv tool run` command.
2. Executing `spec-ops adopt` in a directory containing `mkdocs.yml` or an existing workflow using concurrency group `pages` prints an actionable conflict warning and remediation instructions.
3. Executing `spec-ops adopt --github-pages --deconflict-workflow` renames conflicting legacy workflow concurrency groups or deconflicts the Pages job configuration.
4. Executing `spec-ops docs build --out <dir>` outputs the Diataxis documentation index and generates `<dir>/visualizer/index.html` with graph telemetry.
5. Every HTML file generated by `spec-ops docs build` contains `<a ... href=".../visualizer/">` in the top header navigation.
6. Executing `spec-ops adopt --grandfather-debt` creates `.spec-ops/debt_baseline.json` containing recorded file paths and line counts, and running `spec-ops health` returns exit code 0.

## Linked User Stories

- `US-0124`
- `US-0125`
- `US-0126`
- `US-0127`

## Implementing Backlog Tasks

- `TASK-0248`
- `TASK-0249`
- `TASK-0250`
