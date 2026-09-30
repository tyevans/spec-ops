# How-To: Scaffold Bounded-Context Diataxis Documentation and Spec Links

This guide explains how to scaffold modular Diataxis documentation quadrants for new bounded contexts with bidirectional links to living specifications and the 2D visualizer canvas.

---

## 1. Scaffolding Documentation for a Bounded Context

To generate compliant Diataxis quadrants (`tutorials/`, `how-to/`, `reference/`, and `explanation/`) for a bounded context:

```bash
spec-ops scaffold docs --bc billing --title "Billing Subsystem"
```

Or invoke via the `diataxis` alias:

```bash
spec-ops scaffold diataxis --bc billing --title "Billing Subsystem"
```

The scaffolding command creates starter index files and architecture specs:
- `docs/tutorials/billing/index.md`
- `docs/how-to/billing/index.md`
- `docs/reference/billing/index.md`
- `docs/explanation/billing/index.md`
- `docs/explanation/billing/architecture.md`
- Updates `docs/index.md` with a registered section and visualizer link.

---

## 2. Preventing Duplicate Scaffolding and Overwriting

To prevent accidental file corruption or overwriting of customized documentation, SpecOps guards existing trees:

```bash
spec-ops scaffold docs --bc billing
```

If documentation already exists, the command exits with code 1 and warns that Diataxis documentation already exists.

To intentionally re-scaffold or update templates:

```bash
spec-ops scaffold docs --bc billing --force
```

Or using the `--overwrite` flag:

```bash
spec-ops scaffold docs --bc billing --overwrite
```

---

## 3. Visualizer Deep Linking

All scaffolded documents automatically include deep links targeting the bounded context in the 2D graph visualizer:

- Query focus: `visualizer/?focus=billing`
- Canvas camera focus hash: `#tab=canvas&focus=billing`
