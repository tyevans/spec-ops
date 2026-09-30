"""Executable BDD acceptance tests for US-0106: Living Architectural Review Radar."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.adrs.supersede import supersede_adr
from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.bundle import compile_bundle
from tests.test_visualizer import _run_node_test

scenarios("features/us_0106_living_architectural_radar.feature")


def _run_vis_js(html: str, user_js: str) -> None:
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert len(scripts) >= 2
    full_js = f"""
    {scripts[0]}
    {scripts[1]}
    {user_js}
    """
    _run_node_test(html, full_js)


@pytest.fixture
def bdd_radar_ctx(tmp_path: Path) -> dict[str, Any]:
    project_dir = tmp_path / "radar_project"
    init_project(project_dir, name="RadarTestProject")
    config = load_config(root_dir=project_dir)

    return {
        "project_dir": project_dir,
        "config": config,
        "html_content": None,
    }


# ============================================================================
# Scenario 1: Bounded Context Boundary and Dependency Flow Inspection
# ============================================================================

@given('a project with explicit bounded contexts: "core", "visualizer", "reporting", "worker", "health"')
def given_project_with_explicit_bcs(bdd_radar_ctx: dict[str, Any]):
    repo = bdd_radar_ctx["project_dir"]
    toml_path = repo / "specops.toml"
    current = toml_path.read_text(encoding="utf-8")
    bc_config = """
[architecture.bounded_contexts.core]
path = "src/core"
[architecture.bounded_contexts.visualizer]
path = "src/visualizer"
[architecture.bounded_contexts.reporting]
path = "src/reporting"
[architecture.bounded_contexts.worker]
path = "src/worker"
[architecture.bounded_contexts.health]
path = "src/health"

[architecture.boundary_rules]
"core.*" = ["visualizer.*", "reporting.*"]
"""
    toml_path.write_text(current.rstrip() + "\n" + bc_config, encoding="utf-8")

    # Create dummy files simulating bounded contexts and dependencies
    src = repo / "src"
    for bc in ["core", "visualizer", "reporting", "worker", "health"]:
        (src / bc).mkdir(parents=True, exist_ok=True)
        (src / bc / "__init__.py").write_text("", encoding="utf-8")

    # An illegal backward import: core imports visualizer (violates boundary rule & layering)
    (src / "core" / "seam.py").write_text("import visualizer.template\n", encoding="utf-8")
    (src / "visualizer" / "view.py").write_text("import core.models\n", encoding="utf-8")

    config = load_config(root_dir=repo)
    bdd_radar_ctx["config"] = config
    bdd_radar_ctx["html_content"] = compile_bundle(config)


@when('Alex selects the "ADR Architecture" tab and switches layout to "Radar" or "Flow DAG"')
def when_alex_selects_adrs_and_switches_layout(bdd_radar_ctx: dict[str, Any]):
    # Verified in subsequent then step via JS harness
    pass


@then("the visualization groups entities into distinct bounded context clusters with color-coded boundaries")
def then_groups_into_bc_clusters(bdd_radar_ctx: dict[str, Any]):
    html = bdd_radar_ctx["html_content"]
    test_js = """
    window.switchTab('adrs');
    assert.strictEqual(window.activeTab, 'adrs');

    // Switch layout to Radar (radial)
    window.switchLayout('radial');
    assert.strictEqual(window.currentLayout, 'radial');

    // Verify bounded context hulls are active in Radar/Flow DAG layouts
    assert.strictEqual(typeof window.drawBcHulls, 'function');
    assert.strictEqual(typeof window.getBcColor, 'function');

    // Render Architecture Radar View and verify coupling matrix
    const radarView = window.renderArchitectureRadarView();
    assert(radarView.includes('Bounded Context Boundary &amp; Coupling Matrix'));
    assert(radarView.includes('coupling-matrix-table'));
    assert(radarView.includes('core'));
    assert(radarView.includes('visualizer'));
    """
    _run_vis_js(html, test_js)


@then("directed edges illustrate dependency flows between contexts")
def then_directed_edges_illustrate_flows(bdd_radar_ctx: dict[str, Any]):
    html = bdd_radar_ctx["html_content"]
    test_js = """
    // Verify directed edges and coupling matrix vectors
    const radarView = window.renderArchitectureRadarView();
    assert(radarView.includes('From \\\\ To Context') || radarView.includes('From \\ To Context'));
    assert(radarView.includes('Permissible') || radarView.includes('Allowed') || radarView.includes('Prohibited'));
    """
    _run_vis_js(html, test_js)


@then("any illegal backward dependency violating ADR-0007 is highlighted with a pulsing red warning line.")
def then_illegal_dependency_highlighted(bdd_radar_ctx: dict[str, Any]):
    html = bdd_radar_ctx["html_content"]
    test_js = """
    const radarView = window.renderArchitectureRadarView();
    assert(radarView.includes('Prohibited') || radarView.includes('matrix-badge-prohibited'));
    assert(radarView.includes('pulsing-red'));
    assert(radarView.includes('Prohibited Import Violations'));
    """
    _run_vis_js(html, test_js)


# ============================================================================
# Scenario 2: ADR Supersession Lineage and Active Status Radar
# ============================================================================

@given('an architectural record "ADR-0005" that has been superseded by "ADR-0014"')
def given_adr_0005_superseded_by_0014(bdd_radar_ctx: dict[str, Any]):
    repo = bdd_radar_ctx["project_dir"]
    adrs_dir = repo / "docs" / "project" / "adrs"
    adrs_dir.mkdir(parents=True, exist_ok=True)

    adr5 = adrs_dir / "adr-0005-worktree-concurrency.md"
    adr5.write_text(
        """---
id: 'ADR-0005'
title: Worktree Concurrency v1
status: Superseded
superseded_by: ADR-0014
---
# ADR-0005: Worktree Concurrency v1

## Status
Superseded by ADR-0014

## Context
Initial single-pass concurrency.

## Decision
Use simple worktrees.

## Consequences
Superseded by ADR-0014.
""",
        encoding="utf-8",
    )

    adr14 = adrs_dir / "adr-0014-worktree-concurrency-v2.md"
    adr14.write_text(
        """---
id: 'ADR-0014'
title: Worktree Concurrency v2
status: Accepted
supersedes: ADR-0005
---
# ADR-0014: Worktree Concurrency v2

## Status
Accepted

## Context
Multi-agent concurrency upgrade.

## Decision
Use lockless branch worktrees.

## Consequences
Invariants updated.
""",
        encoding="utf-8",
    )

    config = load_config(root_dir=repo)
    bdd_radar_ctx["config"] = config
    bdd_radar_ctx["html_content"] = compile_bundle(config)


@when('Alex inspects "ADR-0005" in the visualizer ADR Matrix')
def when_alex_inspects_adr_0005(bdd_radar_ctx: dict[str, Any]):
    pass


@then('"ADR-0005" is visually rendered with a strikethrough badge "Superseded"')
def then_adr0005_rendered_with_strikethrough(bdd_radar_ctx: dict[str, Any]):
    html = bdd_radar_ctx["html_content"]
    test_js = """
    window.switchTab('adrs');
    const adrsHtml = window.renderAdrsView ? window.renderAdrsView() : '';
    assert(adrsHtml.includes('ADR-0005'));
    assert(adrsHtml.includes('Superseded'));
    assert(adrsHtml.includes('strikethrough-badge') || adrsHtml.includes('line-through'));

    const radarHtml = window.renderArchitectureRadarView();
    assert(radarHtml.includes('ADR-0005'));
    assert(radarHtml.includes('strikethrough'));
    """
    _run_vis_js(html, test_js)


@then('the detail drawer displays a prominent notification: "Superseded by ADR-0014: Worktree Concurrency v2"')
def then_detail_drawer_displays_superseded_notification(bdd_radar_ctx: dict[str, Any]):
    html = bdd_radar_ctx["html_content"]
    test_js = """
    window.openDrawer('ADR-0005');
    const drawerHtml = window.document.getElementById('drawer-body').innerHTML;
    assert(drawerHtml.includes('superseded-notification'));
    assert(drawerHtml.includes('Superseded by'));
    assert(drawerHtml.includes('ADR-0014'));
    assert(drawerHtml.includes('Worktree Concurrency v2'));
    """
    _run_vis_js(html, test_js)


@then('clicking the supersession link navigates directly to "ADR-0014" with updated consequences and active invariants.')
def then_clicking_link_navigates_to_adr0014(bdd_radar_ctx: dict[str, Any]):
    html = bdd_radar_ctx["html_content"]
    test_js = """
    window.openDrawer('ADR-0014');
    const drawerHtml = window.document.getElementById('drawer-body').innerHTML;
    assert(drawerHtml.includes('ADR-0014'));
    assert(drawerHtml.includes('Worktree Concurrency v2'));
    assert(drawerHtml.includes('Accepted'));
    assert(drawerHtml.includes('Invariants updated'));
    """
    _run_vis_js(html, test_js)


# ============================================================================
# Scenario 3: Automated Orphan Work Item and Specification Drift Audit
# ============================================================================

@given("a project containing:")
def given_project_containing_orphan_specs(bdd_radar_ctx: dict[str, Any]):
    repo = bdd_radar_ctx["project_dir"]
    backlog_dir = repo / "docs" / "project" / "backlog" / "refined"
    stories_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    prds_dir = repo / "docs" / "project" / "product" / "accepted"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    stories_dir.mkdir(parents=True, exist_ok=True)
    prds_dir.mkdir(parents=True, exist_ok=True)

    # 1 backlog task with no governing PRD or User Story
    (backlog_dir / "0099-orphan-task.md").write_text(
        """---
id: '0099'
title: Orphaned Feature Task
status: Refined
target_bc: core
---
# TASK-0099: Orphaned Feature Task
""",
        encoding="utf-8",
    )

    # 1 user story with no linked PRD
    (stories_dir / "us-0099-orphan-story.md").write_text(
        """---
id: '0099'
title: Orphaned User Story
status: Accepted
persona: Alex
---
# US-0099: Orphaned User Story
""",
        encoding="utf-8",
    )

    # 1 PRD with zero implementing tasks
    (prds_dir / "prd-0099-orphan-prd.md").write_text(
        """---
id: 'PRD-0099'
title: Orphaned Standalone PRD
status: Accepted
---
# PRD-0099: Orphaned Standalone PRD
""",
        encoding="utf-8",
    )

    config = load_config(root_dir=repo)
    bdd_radar_ctx["config"] = config
    bdd_radar_ctx["html_content"] = compile_bundle(config)


@when('Alex clicks "Audit Specification Drift" in the visualizer header')
def when_alex_clicks_audit_specification_drift(bdd_radar_ctx: dict[str, Any]):
    pass


@then("an audit modal opens categorizing all orphaned specifications")
def then_audit_modal_opens_categorizing_orphans(bdd_radar_ctx: dict[str, Any]):
    html = bdd_radar_ctx["html_content"]
    test_js = """
    window.openDriftAuditModal();
    const modal = window.document.getElementById('drift-audit-modal');
    assert.strictEqual(modal.style.display, 'flex');

    const modalBody = window.document.getElementById('drift-audit-modal-body').innerHTML;
    assert(modalBody.includes('TASK-0099'));
    assert(modalBody.includes('US-0099'));
    assert(modalBody.includes('PRD-0099'));
    """
    _run_vis_js(html, test_js)


@then("each orphan entity provides a 1-click action to scaffold missing governing specs or archive obsolete entries")
def then_each_orphan_entity_provides_actions(bdd_radar_ctx: dict[str, Any]):
    html = bdd_radar_ctx["html_content"]
    test_js = """
    window.openDriftAuditModal();
    const modalBody = window.document.getElementById('drift-audit-modal-body').innerHTML;
    assert(modalBody.includes('Scaffold Governing Spec') || modalBody.includes('Scaffold Missing Spec'));
    assert(modalBody.includes('Archive Obsolete Entry'));

    // Test 1-click scaffold action
    window.scaffoldMissingSpec('TASK-0099');
    const taskRow = window.document.getElementById('drift-task-TASK-0099').innerHTML;
    assert(taskRow.includes('Scaffolded missing governing spec'));

    // Test 1-click archive action
    window.archiveObsoleteEntry('US-0099');
    const storyRow = window.document.getElementById('drift-story-US-0099').innerHTML;
    assert(storyRow.includes('Archived obsolete entry'));
    """
    _run_vis_js(html, test_js)


@then('Alex can export the audit report as "dist/spec-drift-audit.json".')
def then_alex_exports_audit_report_json(bdd_radar_ctx: dict[str, Any]):
    html = bdd_radar_ctx["html_content"]
    test_js = """
    const report = window.exportDriftAuditReport();
    assert(report.total_orphans >= 3);
    assert(report.orphaned_tasks.some(t => t.id === 'TASK-0099'));
    assert(report.orphaned_stories.some(s => s.id === 'US-0099'));
    assert(report.orphaned_prds.some(p => p.id === 'PRD-0099'));
    assert.strictEqual(window.lastExportedDriftAudit, report);
    """
    _run_vis_js(html, test_js)
