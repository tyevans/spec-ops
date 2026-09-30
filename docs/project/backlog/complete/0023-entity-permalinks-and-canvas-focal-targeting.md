---
id: '0023'
title: Entity Permalinks, Canvas Focal Targeting, and Shareable URL Actions
status: Complete
dependencies:
- TASK-0022
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
governing_prds:
- PRD-0001
governing_stories:
- US-0010
target_bc: visualizer
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0023: Entity Permalinks, Canvas Focal Targeting, and Shareable URL Actions

## Summary
Add direct entity permalinks (`#entity=TASK-0013` or `#tab=...&entity=...`), automated detail drawer opening on deep link load, 2D Canvas camera focal centering and halo highlighting on target nodes, and a "Copy Deep Link" UI action to the SpecOps visualizer.

## Problem Statement
When human architects, engineering leads, or AI agents want to reference a specific work item (such as a backlog task, ADR, or PRD) during code review or architecture discussion, they must instruct collaborators to open the visualizer and manually search for the item. There is no automated deep link resolution to open the entity detail drawer directly or focus the camera on a specific node in the 2D relational graph.

## Detailed Objectives
1. **Entity Permalink Resolution**:
   - Support `entity=<ID>` parameter in URL hash (e.g. `#entity=TASK-0013`, `#entity=ADR-0002`, `#entity=PRD-0001`).
   - Automatically resolve the entity from `window.PROJECT_DATA` on page initialization and invoke `openDrawer(id)`.
   - Update the URL hash when opening or closing drawers (`openDrawer` adds `entity=...`, `closeDrawer` removes it).
2. **2D Canvas Focal Centering**:
   - When `#tab=graph&entity=<ID>` is loaded or navigated to, pan and center the Canvas 2D camera viewport onto the target node coordinates.
   - Render a glowing focal ring/halo around the deep-linked node to distinguish it immediately from neighboring nodes.
3. **Shareable Permalinks UI Action**:
   - Add a "🔗 Copy Deep Link" button to the entity detail drawer header alongside the existing "📋 Copy Path" button.
   - Add "Copy Link" context action to Kanban task cards and ADR lists.
   - Provide visual feedback ("✓ Copied URL!") when copied to clipboard.
4. **Frontdoor Test Verification**:
   - Verify permalink generation, clipboard payload, and drawer auto-opening behavior through blackbox frontdoor tests.
   - Maintain zero file length violations (<500 lines).

## Definition of Done (Blackbox Frontdoor TDD)
1. Navigating to `#entity=<ID>` automatically opens the corresponding entity detail drawer with full specification.
2. On the Relationship Graph view, deep-linked entities are centered and highlighted in the canvas viewport.
3. Detail drawer includes a functional "Copy Deep Link" button copying the canonical URL with hash parameters.
4. Opening and closing drawers synchronizes the `entity` parameter in the URL hash.
5. All test suites (`uv run pytest`) and codebase health checks (`uv run spec-ops health`) pass cleanly.
