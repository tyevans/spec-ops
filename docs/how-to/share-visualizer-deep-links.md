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

# Backlog view with completed tasks hidden and filtered by search query
visualizer.html#tab=kanban&hideDone=true&q=rescue
```

Supported filter parameters include:
- `q`: Text search query (matches titles, canonical IDs, and tags).
- `status`: Lifecycle status filter (`all`, `complete`, `refined`, `proposed`).
- `bc`: Target bounded context filter.
- `hideDone`: Boolean toggle (`true`/`false`) to exclude completed tasks.
- `groupBy`: Timeline grouping mode (`release` or `bc`).

---

## Copying Permalinks

To copy a canonical permalink from the visualizer:

1. Open any entity in the detail drawer (or click a node in the graph).
2. Click the **🔗 Copy Deep Link** button in the drawer header.
3. Paste the URL into pull request descriptions, architecture review notes, or agent prompt instructions.

---

## Browser History Navigation

The visualizer responds to native browser navigation:
- Clicking the browser **Back** button closes an active detail drawer or returns to the previous tab.
- Clicking **Forward** steps forward through your inspection history without triggering network reloads.
