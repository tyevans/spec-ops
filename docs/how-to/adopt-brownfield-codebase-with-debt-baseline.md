# How-To: Adopt Brownfield Codebases and Manage Grandfathered Debt

This guide explains how to adopt SpecOps into an existing brownfield codebase without immediate file limit disruptions, and how to incrementally extract architectural seams.

---

## Adopting an Existing Codebase

To bootstrap SpecOps into an existing repository with baseline architectural profiles:

```bash
spec-ops adopt --name "ExistingSystem" --profile core,bdd,ddd
```

By default, `spec-ops adopt` enables `--grandfather-debt`, which snapshots all existing files that exceed the 500-line file limit (ADR-0002) into `.spec-ops/debt-baseline.json`. This ensures existing large files do not cause preflight or CI failures, while preventing those files from growing any larger.

To adopt without debt baselining:

```bash
spec-ops adopt --no-grandfather-debt
```

---

## How Grandfathered Debt Works

When `--grandfather-debt` is active:
1. Files already over 500 lines are recorded in `.spec-ops/debt-baseline.json` with their exact line counts at adoption time.
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
