# How-To: Decompose PRDs and Curate the Backlog

This guide explains how to break high-level PRD documents into thin vertical slices and maintain a healthy backlog buffer.

---

## Decomposing a PRD

When a PRD is approved in `docs/project/product/accepted/`, decompose it into vertical slices:

```bash
spec-ops prd decompose PRD-0001
```

This:
1. Inspects checkable outcomes and user stories in the PRD.
2. Emits granular vertical slice tasks into `docs/project/backlog/proposed/`.
3. Emits an architectural spike task if unverified technical invariants are detected.
4. Links the newly created tasks in the PRD frontmatter.

---

## Replenishing the Refined Buffer Just-in-Time

To promote unblocked proposed tasks and maintain an optimal ready buffer:

```bash
spec-ops curate
```

### Cognitive Inference-Driven Refinement

To critically audit candidate tasks against living repository reality, reconcile architectural drift across superseded ADRs and refactored modules, slice oversized tasks (>500 lines) into thin vertical slices, and synthesize Definition of Ready (DoR) acceptance criteria:

```bash
# Preview proposed reconciliations and decompositions without modifying disk state
spec-ops curate --infer --dry-run

# Execute cognitive curation and replenishment
spec-ops curate --infer
```

