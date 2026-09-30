# How-To: Share Deep Links and Permalinks in the SpecOps Visualizer

This guide explains how to construct, share, and navigate visualizer deep links targeting specific dashboard views, faceted filter sets, and individual entity drawers.

---

## Overview

The SpecOps visualizer uses browser URL hash fragments to store and synchronize view and entity state. Because state is encoded in hash parameters (rather than server query strings), permalinks function identically across:

- Local preview servers (`spec-ops visualizer --serve` at `http://localhost:8787/`)
- Static GitHub Pages deployments (`/spec-ops/visualizer/`)
- Offline standalone bundles opened directly from disk (`file:///.../visualizer.html`)

---

## Deep Linking to Dashboard Views

To link directly to a specific visualizer tab, append `#tab=<identifier>` to the visualizer URL:

| Dashboard View | Deep Link Format | Example URL |
|---|---|---|
| **Relationship Graph** | `#tab=graph` | `visualizer.html#tab=graph` |
| **Gantt & Timeline** | `#tab=gantt` | `visualizer.html#tab=gantt` |
| **Kanban Pipeline** | `#tab=kanban` | `visualizer.html#tab=kanban` |
| **PRDs & Features** | `#tab=prds` | `visualizer.html#tab=prds` |
| **ADR Architecture** | `#tab=adrs` | `visualizer.html#tab=adrs` |
| **Personas & Stories** | `#tab=personas` | `visualizer.html#tab=personas` |
| **Project Matrix** | `#tab=matrix` | `visualizer.html#tab=matrix` |
| **Lead Operations Console** | `#tab=lead` | `visualizer.html#tab=lead` |

When a user or agent opens the link, the visualizer immediately mounts the specified tab view without full page reloads.

---

## Deep Linking to Specific Entities

To open a particular task, ADR, PRD, story, or persona directly in the visualizer detail drawer, supply the `entity` parameter:

```text
# Deep link to a specific backlog task card
visualizer.html#tab=kanban&entity=TASK-0013

# Deep link to an Architectural Decision Record
visualizer.html#tab=adrs&entity=ADR-0002

# Deep link directly to a PRD specification
visualizer.html#tab=prds&entity=PRD-0001
```

If `#tab` is omitted, the visualizer activates the default context for the entity type and opens the detail drawer.

---

## Preserving Faceted Filters and Search Queries

Filter parameters can be combined in the URL hash to share exact triage views with teammates:

```text
# Kanban view filtered to Refined tasks in the 'core' bounded context
visualizer.html#tab=kanban&status=refined&bc=core

# Relationship graph clustered by Bounded Context with boundary hulls and labels
visualizer.html#tab=graph&groupBy=bc

# Relationship graph filtered to Active Delivery (tasks, stories, PRDs with complete hidden)
visualizer.html#tab=graph&types=task,story,prd&hideDone=true

# Relationship graph blast radius isolated to 1-hop neighborhood of a focused task
visualizer.html#tab=graph&entity=TASK-0009&hops=1
```

Supported filter parameters include:
- `q`: Text search query (matches titles, canonical IDs, roles, and tags).
- `status`: Lifecycle status filter (`all`, `complete`, `refined`, `proposed`).
- `bc`: Target bounded context filter (isolates nodes in that architectural domain).
- `hideDone`: Boolean toggle (`true`/`false`) to exclude completed tasks.
- `groupBy`: Grouping mode (`bc` for Bounded Context clusters with boundary hulls on the graph or BC groups in Gantt; `release` for delivery milestones).
- `types`: Comma-separated list of visible entity types (`task`, `story`, `prd`, `adr`, `persona`, `bc`).
- `hops`: Blast radius degree-of-separation (`all`, `1`, or `2` hops from focused/searched nodes).
- `preset`: Perspective preset (`default`, `bc`, `delivery`, `architecture`, `flow`).

---

## Copying Permalinks and Context Actions

To copy a canonical permalink from the visualizer:

1. **Detail Drawer Header**: Click the **🔗 Copy Deep Link** button in the entity detail drawer header. Visual confirmation (`✓ Copied URL!`) confirms the canonical deep link has been copied to your clipboard.
2. **Kanban Task Cards**: Click the **🔗 Copy Link** context action button directly on any Kanban card to copy its canonical URL.
3. **ADR Governance Lists**: Click the **🔗 Copy Link** button on any ADR card in the ADR Architecture tab.

---

## 2D Canvas Focal Centering and Glowing Halo

When deep linking to an entity on the relationship graph (`#tab=graph&entity=<ID>` or `#entity=<ID>`):
- The 2D Canvas camera viewport automatically pans and centers directly on the target entity node.
- A glowing dual-ring halo pulses around the target node to immediately distinguish it from neighboring nodes in the graph.
- Opening or closing detail drawers synchronizes the URL hash (`entity=...`), smoothly centering the camera when inspected and clearing the focal halo when dismissed.

---

## Browser History Navigation

The visualizer responds to native browser navigation:
- Clicking the browser **Back** button closes an active detail drawer or returns to the previous tab.
- Clicking **Forward** steps forward through your inspection history without triggering network reloads.

---

## Air-Gapped Standalone Bundle Export

To share the visualizer in zero-network or air-gapped environments, export a standalone, self-contained HTML bundle:

```bash
spec-ops visualizer export --output dist/index.html
```

Or build the artifact during static documentation site compilation:

```bash
spec-ops docs build --include-visualizer
```

The resulting single-file HTML artifact bundles all CSS, SVG icons, and JavaScript logic with zero external CDN dependencies, fully supporting local `file://` protocol execution.
