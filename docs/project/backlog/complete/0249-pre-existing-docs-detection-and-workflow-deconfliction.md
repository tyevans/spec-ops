---
id: 0249
title: Pre-Existing Documentation System Detection, Workflow Deconfliction & Bridging
  Guidance
status: Complete
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0006
governing_prds:
- PRD-0007
governing_stories:
- US-0125
target_bc: adopt
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T19:52:10.402639+00:00'
commit_signature_status: SIGNED
persona: Devon
has_signed_commits: true
---

# TASK-0249: Pre-Existing Documentation System Detection, Workflow Deconfliction & Bridging Guidance

## Summary
Add pre-flight inspection in `spec-ops adopt` to detect pre-existing documentation tools (such as MkDocs or Sphinx) and duplicate GitHub Pages deployment workflows, outputting actionable guidance to prevent workflow collisions or bridging the living 2D visualizer into legacy documentation sites.

## Problem Statement & Context
When adopting SpecOps in brownfield codebases like `redstring`, the repository frequently already has an existing documentation setup (e.g. `mkdocs.yml` and `.github/workflows/docs.yml` deploying to Pages under `concurrency: group: pages`). When `spec-ops adopt --github-pages` runs, it creates duplicate Pages workflows that collide with or overwrite the legacy site. SpecOps currently lacks detection and deconfliction mechanisms for pre-existing documentation tools.

## Proposed Solution & Remediation Plan
1. Implement documentation and workflow detection logic in `src/spec_ops/adopt/detector.py` to identify `mkdocs.yml`, Sphinx `conf.py`, and existing `.github/workflows/*.yml` with `concurrency: group: pages` or `deploy-pages`.
2. In `src/spec_ops/cli/adopt_handler.py`, call the detector and print clear, actionable warnings outlining detected conflicts and remediation options.
3. Support `--deconflict-workflow` flag in `spec-ops adopt` to safely adjust or namespace conflicting workflow configurations.
4. Support `--bridge-docs` flag in `spec-ops adopt` to emit configuration hints or snippet recommendations for embedding `/visualizer/` links into existing MkDocs navigation.
5. Author blackbox frontdoor tests exercising pre-existing documentation detection and conflict handling.

## Definition of Done (Blackbox Frontdoor TDD)
1. Running `spec-ops adopt` in a directory with `mkdocs.yml` prints detection notice and bridging instructions.
2. Running `spec-ops adopt --github-pages` in a directory with existing Pages workflow flags the duplicate concurrency group.
3. Running with `--deconflict-workflow` successfully handles workflow collision.
4. 100% blackbox frontdoor test pass rate with 0 private backdoor mocks (ADR-0003).
5. Code strictly adheres to ADR-0002 (<500 lines limit).
