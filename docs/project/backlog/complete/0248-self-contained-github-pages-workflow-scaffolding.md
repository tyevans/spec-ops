---
id: 0248
title: Self-Contained GitHub Pages Workflow Scaffolding with Standalone Tool Execution
status: Complete
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0006
governing_prds:
- PRD-0007
governing_stories:
- US-0124
target_bc: docs
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T19:52:04.558167+00:00'
commit_signature_status: SIGNED
persona: Devon
has_signed_commits: true
---

# TASK-0248: Self-Contained GitHub Pages Workflow Scaffolding with Standalone Tool Execution

## Summary
Implement `--github-pages` flag in `spec-ops adopt` to scaffold a self-contained GitHub Actions deployment workflow (`.github/workflows/deploy-pages.yml`) invoking SpecOps via standalone tool execution (`uv tool run --from git+https://github.com/tyevans/spec-ops.git spec-ops docs build --base-url /${{ github.event.repository.name }}/`), and ensure `spec-ops docs build` embeds a top navigation link to `/visualizer/` on every compiled documentation page.

## Problem Statement & Context
Brownfield repositories like `redstring` onboarding onto SpecOps do not have `spec-ops` declared as a runtime dependency in `pyproject.toml` or `uv.lock`. Current Pages scaffolding generates `uv run spec-ops docs build` and requires `uv sync`, which fails in clean GitHub Actions runners with missing package errors. Additionally, generated documentation pages lack a visible top header link connecting users directly to the interactive 2D graph visualizer.

## Proposed Solution & Remediation Plan
1. Add `--github-pages` argument to `spec-ops adopt` CLI parser in `src/spec_ops/cli/parser.py` and handle it in `src/spec_ops/cli/adopt_handler.py`.
2. Update `src/spec_ops/scaffold/pages_workflow.py` to support `standalone: bool = False`. When standalone is enabled, generate workflow steps using `uv tool run --from git+https://github.com/tyevans/spec-ops.git spec-ops docs build` without requiring in-repo `uv sync` or dependencies.
3. Update `src/spec_ops/docs/templates.py` and `src/spec_ops/docs/builder.py` so that every compiled documentation page provides an explicit header navigation link to `/visualizer/`.
4. Ensure `spec-ops docs build` compiles the visualizer to `site/visualizer/index.html` alongside the Diataxis documentation.
5. Author blackbox frontdoor tests verifying adoption with `--github-pages` and header navigation linking in compiled docs.

## Definition of Done (Blackbox Frontdoor TDD)
1. Running `spec-ops adopt --github-pages` scaffolds `.github/workflows/deploy-pages.yml` with standalone `uv tool run` execution.
2. Running `spec-ops docs build` generates Diataxis pages containing `<a ... href=".../visualizer/">` in top navigation and standalone visualizer at `site/visualizer/index.html`.
3. 100% blackbox frontdoor test pass rate with 0 private backdoor mocks (ADR-0003).
4. Code strictly adheres to ADR-0002 (<500 lines limit).
