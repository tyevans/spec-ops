# How-To: Audit Architectural Radar and Bounded Context Boundaries

This guide covers viewing and auditing bounded context couplings, detecting illegal cross-context module imports, inspecting ADR supersession trees, and remediating specification drift using the Living Architectural Review Radar.

---

## Accessing the Architectural Review Radar

The Architectural Review Radar is built directly into the SpecOps visualizer dashboard. To start the local visualizer server:

```bash
spec-ops visualizer
```

Navigate to the **📡 Architectural Review Radar** tab or use the direct deep link:

```text
http://127.0.0.1:8787/#tab=radar
```

To export a self-contained, air-gapped single-file HTML bundle including the Architectural Review Radar:

```bash
spec-ops visualizer export --output dist/project-visualizer.html
```

---

## 1. Bounded Context Boundary & Coupling Matrix

The coupling matrix visualizes all cross-context module imports between bounded contexts based on architectural layers and independence contracts governed by `import-linter` and ADR-0007:

- **Permissible (N)**: Permitted downward dependency flow actively in use by code.
- **Permissible**: Allowed downward layer vectors currently uncoupled ($N = 0$).
- **Isolated**: Independent peer bounded contexts in the same layer (enforced via `import-linter` pipe `|` separation).
- **Prohibited**: Forbidden backward layer vectors (lower layer attempting to import a higher layer) or contract-forbidden vectors ($N = 0$).
- **Prohibited (N)**: Active architectural violations highlighted with pulsing red warning badges (`matrix-badge-prohibited pulsing-red`) indicating illegal backward dependencies or unauthorized peer imports.
- **Layout Switching**: Toggle between the **Coupling Matrix**, **Radial Radar Layout** (`window.switchLayout('radial')`), or **Flow DAG Layout** (`window.switchLayout('flow')`) to inspect bounded context hulls and directional dependency flows.

---

## 2. ADR Supersession Lineage Tree

The supersession radar visualizes the lifecycle state of Architectural Decision Records:

- **Active Decisions**: Displayed with green status badges (`Accepted`).
- **Superseded Decisions**: Flagged with red strikethrough badges (`Superseded`), showing the superseding ADR and a direct link to inspect the replacement decision and updated invariants.
- **Obsolete Citations Audit**: Warns when backlog tasks cite superseded ADRs without human architect re-refinement.

---

## 3. Specification Drift Audit & 1-Click Remediation

Click **🔍 Audit Specification Drift** in the header or radar view to launch the interactive audit modal:

- **Orphan Tasks**: Identifies tasks lacking governing PRDs or user stories. Use **Scaffold Governing Spec** to generate missing specifications.
- **Orphan Stories**: Identifies user stories not linked to any governing PRD.
- **Orphan PRDs**: Identifies PRDs with zero implementing backlog tasks.
- **Exporting JSON Reports**: Click **📄 Export Audit Report** to download or write `dist/spec-drift-audit.json`.

---

## CLI Automated Boundary Verification

To run automated CI boundary verification without launching the visualizer:

```bash
spec-ops health --architecture
```

This verifies that zero illegal cross-context imports exist and that bounded context boundaries adhere to ADR-0007. Any violation results in a non-zero exit code to prevent architectural erosion in CI pipelines.
