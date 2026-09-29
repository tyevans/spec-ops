# How-To: Decompose PRDs and Curate the Backlog

This guide explains how to break high-level PRD documents into thin vertical slices and maintain a healthy backlog buffer.

---

## Decomposing a PRD

When a PRD is approved in `docs/project/product/accepted/`, decompose it into vertical slices:

```bash
spec-ops prd decompose PRD-0001 --spikes
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

The curator promotes eligible tasks to `docs/project/backlog/refined/` and atomically synchronizes `PRIORITY.md`.
