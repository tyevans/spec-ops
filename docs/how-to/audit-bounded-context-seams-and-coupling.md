# How-To: Audit Bounded Context Seams and Coupling

This guide demonstrates using the autonomous bounded context seam auditor to verify Domain-Driven Design (DDD) layering, detect illegal cross-context internal dependencies, and generate architectural coupling heatmaps.

---

## Auditing Bounded Context Seams

To audit all bounded contexts and cross-context imports:

```bash
spec-ops architecture seams
```

Output:

```text
=== Bounded Context Seam & Coupling Audit ===
Discovered Contexts: adrs, backlog, cli, config, core, docs, graph, prd, profiles, release, rescue, scaffold, security, spike, tui, visualizer, worker

Bounded Context      | Ca (In)  | Ce (Out) | Instability (I)
--------------------------------------------------------
adrs                 | 4        | 1        | 0.200
backlog              | 9        | 10       | 0.526
cli                  | 2        | 16       | 0.889
config               | 14       | 0        | 0.000
core                 | 13       | 3        | 0.188
...

✅ All cross-context dependencies comply with Domain-Driven Design seams.
```

---

## Enforcing Strict Architecture Quality Gates

In CI/CD preflight pipelines, enforce that no illegal cross-context internal dependencies leak across boundaries:

```bash
spec-ops architecture seams --strict
```

If unauthorized internal imports are detected (such as core domain code importing private visualizer or rescue internals):

```text
=== Bounded Context Seam & Coupling Audit ===
...
⚠️ Detected 1 illegal cross-context dependency leak(s):
❌ [core -> visualizer] src/spec_ops/core/sample.py:12
   Illegal import 'spec_ops.visualizer._internal': Illegal direct import of private visualizer internals
```

The command terminates with exit code `1`, halting the preflight gate.

---

## Exporting Cross-Context Coupling Heatmaps

To generate visual coupling heatmaps for architectural review briefs or dashboards:

### Markdown Matrix

```bash
spec-ops architecture seams --export-heatmap dist/architecture/coupling-matrix.md
```

### JSON Format

```bash
spec-ops architecture seams --json --export-heatmap dist/architecture/coupling.json
```

### HTML Visual Heatmap

```bash
spec-ops architecture seams --export-heatmap dist/architecture/coupling.html
```

---

## Understanding Coupling Metrics

The seam auditor computes Robert C. Martin's Package Coupling Metrics:

- **Afferent Coupling ($Ca$)**: Number of other bounded contexts that depend on this context. High $Ca$ indicates foundational, authoritative modules (e.g. `config`, `core`).
- **Efferent Coupling ($Ce$)**: Number of external bounded contexts this context depends upon. High $Ce$ indicates orchestrating or transport modules (e.g. `cli`, `worker`).
- **Instability Index ($I = Ce / (Ca + Ce)$)**:
  - $I = 0.0$: Maximally stable; heavily depended upon, depends on nothing.
  - $I = 1.0$: Maximally instable; depends on many contexts, nobody depends on it.
