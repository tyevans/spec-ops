# How-To: Adopt Brownfield Codebases and Manage Grandfathered Debt

This guide explains how to adopt SpecOps into an existing brownfield codebase without immediate file limit disruptions, and how to incrementally extract architectural seams.

---

## Adopting an Existing Codebase

To bootstrap SpecOps into an existing repository with baseline architectural profiles:

```bash
spec-ops adopt --name "ExistingSystem" --profile core,bdd,ddd
```

By default, `spec-ops adopt` enables `--grandfather-debt`, which snapshots all existing files that exceed the 500-line file limit (ADR-0002) into `.specops/grandfathered_debt.json` and records them under `[invariants.file_limits]` in `specops.toml`. This ensures existing large files do not cause preflight or CI failures, while preventing those files from growing any larger.

To adopt without debt baselining:

```bash
spec-ops adopt --no-grandfather-debt
```

---

## How Grandfathered Debt Works

When `--grandfather-debt` is active:
1. Files already over 500 lines are recorded in `.specops/grandfathered_debt.json` with their exact line counts at adoption time.
2. In subsequent health checks (`spec-ops health`), grandfathered files are reported as tracked debt:
   ```text
   ℹ️ 3 grandfathered files remain tracked debt items.
   ```
3. **Ratchet Principle**: If a grandfathered file expands beyond its recorded baseline, `spec-ops health` triggers an expanded debt violation:
   ```text
   File Length Violation: src/legacy_monolith.py (620 lines > 580 line limit)
      src/legacy_monolith.py: 620 lines (expanded beyond recorded baseline 580 lines)
   ```
4. New files are always subject to the unexempt 500-line hard invariant limit.

---

## Verifying Bounded Context Architecture

SpecOps inspects module dependencies and directory boundaries to enforce clean bounded context architecture:

```bash
spec-ops health --architecture
```

This verifies:
- **Bounded Context Isolation**: Code in domain contexts does not take unauthorized direct dependencies across isolated layers.
- **Deterministic Dependency DAG**: Dependency relationships between packages and modules form an acyclic directed graph with zero cyclic dependency traps.

---

## Analyzing AST Seams and Generating Refactor Tasks

To analyze candidate extraction points in a large or monolithic file using Abstract Syntax Tree (AST) seam parsing:

```bash
spec-ops decompose src/spec_ops/core/parser.py
```

This parses top-level classes and functions, computes line boundaries and fan-out, and recommends cohesive module extraction seams.

To automatically inspect all files approaching or exceeding limits and suggest decomposition splits:

```bash
spec-ops health --suggest-splits
```

To automatically scaffold discrete refactoring tasks in `docs/project/backlog/proposed/` based on AST seam extraction:

```bash
spec-ops health --suggest-splits --emit-task
```

---

## Pre-Existing Documentation Bridging and Workflow Deconfliction

Brownfield repositories often have established documentation systems (such as MkDocs or Sphinx) and active GitHub Actions deployment workflows.

When running `spec-ops adopt`, SpecOps automatically inspects the repository for pre-existing doc frameworks and GitHub Pages deployment workflows:

```bash
spec-ops adopt --github-pages --deconflict-workflow --bridge-docs
```

- **Conflict Detection & Deconfliction (`--deconflict-workflow`)**: If existing workflows target the `pages` concurrency group or `github-pages` environment, SpecOps prompts or automatically deconflicts them (e.g. archiving or renaming the legacy deploy trigger) so that competing workflows do not overwrite each other.
- **Documentation Bridging (`--bridge-docs`)**: Generates navigation bridge stubs or links allowing legacy docs to seamlessly link directly to `{base_url}visualizer/` for interactive PMaC graph exploration.

---

## Self-Contained GitHub Pages Scaffolding

To publish Diataxis documentation and the living 2D visualizer without declaring SpecOps as a runtime dependency in the target repository's lockfile (`uv.lock` or `pyproject.toml`), pass `--github-pages`:

```bash
spec-ops adopt --github-pages
```

This generates `.github/workflows/spec-ops-pages.yml` configured to execute via isolated tool runner:

```yaml
- name: Build Diataxis Documentation & Visualizer
  run: uv tool run --from git+https://github.com/tyevans/spec-ops.git spec-ops docs build --include-visualizer
```

This ensures zero dependency contamination in clean CI environments while deploying the full static site and interactive graph visualizer.

---

## Automated Security Sentinel & Pre-Commit Hook Installation

SpecOps adoption automatically sets up repository supply-chain safeguards:

1. **Pre-Commit Hook**: `spec-ops adopt` scaffolds `.git/hooks/pre-commit` to prevent unauthorized lockfile drift (`spec-ops security sentinel`) and block accidental credential leakage before commits land.
2. **Lockfile Immutability**: Enforces that autonomous agents and human developers do not mutate lockfiles without authorized architectural intent.

---

## Brownfield Commit Provenance Baselining & Rev-Range Auditing

Existing repositories have long commit histories that precede SpecOps and lack RFC-822 specification trailers (`SpecOps-Task: TASK-XXXX`).

During adoption:
1. `spec-ops adopt` records the current HEAD commit in `specops.toml`:
   ```toml
   [audit.provenance]
   baseline_commit = "adae3d7..."
   ```
2. Subsequent provenance audits (`spec-ops audit provenance`) automatically start from `baseline_commit`, preventing grandfathered commits from failing compliance checks.
3. To audit a specific revision range manually:
   ```bash
   spec-ops audit provenance --since origin/main
   ```

