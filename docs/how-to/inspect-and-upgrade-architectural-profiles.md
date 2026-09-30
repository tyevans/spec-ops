# How-To: Inspect and Upgrade Architectural Profiles

This guide explains how to preview upstream profile changes, detect tightened invariant constraints, and migrate baseline Architectural Decision Records (ADRs) using semantic diffing and automated 3-way reconciliation.

---

## 1. Previewing Profile Upgrades with Semantic Diffs

When upstream architectural profiles evolve (e.g. tightening file size limits or adding security invariants), preview changes before modifying repository configurations:

```bash
spec-ops profile diff core
```

To compare against an explicit upstream version:

```bash
spec-ops profile diff specops/base@v2.0
```

### Understanding Semantic Diff Output

The semantic diff highlights breaking changes, added/deprecated ADRs, and modified invariant clauses:

```text
=== SpecOps Profile Semantic Diff: core@1.0.0 -> core@2.0.0 ===

⚠️  BREAKING CHANGES (2):
  • Decreased file length limit from 500 to 350 lines
  • Newly mandated mutation testing (quality.require_mutation_testing = true)

📋 Baseline ADRs:
  + Added ADR-0008: Generative Property-Based Testing and Mutation Testing

🛡️  Invariant Rules:
  + Added: Generative Property-Based Testing (Hypothesis) mandated for domain state machines
  + Added: Target minimum 80% mutation kill score under mutmut

⚙️  Configuration & Limits:
  ~ file_length_limit: 500 -> 350
  ~ quality.require_mutation_testing: false -> true
```

### Machine-Readable Inspection (CI Pipelines)

For automated compliance checks or CI gating, generate machine-readable JSON:

```bash
spec-ops profile diff core --json
```

---

## 2. Upgrading Architectural Profiles

To apply upstream enhancements and migrate baseline ADRs:

```bash
spec-ops profile upgrade core
```

Executing upgrade automatically:
1. Updates the pinned profile version in `specops.toml` (e.g. `core@2.0.0`).
2. Installs new baseline ADRs sequentially into `docs/project/adrs/accepted/`.
3. Atomically appends new entries to `docs/project/adrs/REGISTRY.md`.
4. Re-synchronizes `AGENTS.md` to reflect updated invariant rules and file length thresholds.

---

## 3. Resolving 3-Way ADR Conflicts Safely

If your team has customized a baseline ADR (e.g. `ADR-0002`) and upstream introduces modifications to the same ADR, SpecOps pauses and displays the 3-way conflict:

```text
⚠️  Migration Conflict: Conflict detected for ADR-0002 (Modular Source File Length Limit)
   File: docs/project/adrs/accepted/adr-0002-modular-file-length-limits-anti-rot.md
   Local project has modified this ADR, and upstream has also modified it (3-way conflict).

   Choose a resolution option:
     [1] keep-local      Keep the local override and preserve local changes
     [2] accept-upstream Accepting upstream changes and overwrite local modifications
     [3] custom-diff     Creating a custom ADR diff / merge markers
     [4] abort           Safe migration abort without corrupting files
```

### Automated Resolution in Scripts

For automated migrations or CI automation:
- To overwrite local conflicts with upstream baseline:
  ```bash
  spec-ops profile upgrade core --force
  ```
- To preserve existing local overrides explicitly:
  ```bash
  spec-ops profile upgrade core --action keep-local
  ```
- To cleanly abort without modifying any files:
  ```bash
  spec-ops profile upgrade core --action abort
  ```
