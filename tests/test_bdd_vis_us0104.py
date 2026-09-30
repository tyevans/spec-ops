"""Executable BDD scenarios for US-0104: Live Autonomous Worker Fleet Telemetry and Worktree Operations Console."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.bundle import compile_bundle
from tests.test_visualizer import run_node_test

scenarios("features/us_0104_live_autonomous_worker_fleet_telemetry_console.feature")


def _run_vis_js(html: str, user_js: str) -> None:
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert len(scripts) >= 2
    full_js = f"""
    const content = {json.dumps(html)};
    {scripts[0]}
    {scripts[1]}
    {user_js}
    """
    run_node_test(html, full_js)


@pytest.fixture
def bdd_us104_ctx(tmp_path: Path) -> dict[str, Any]:
    project_dir = tmp_path / "fleet_telemetry_project"
    init_project(project_dir, name="FleetTelemetryProject")
    config = load_config(root_dir=project_dir)
    return {
        "project_dir": project_dir,
        "config": config,
        "html_content": None,
    }


# ============================================================================
# Scenario 1: Live Active Worktree Fleet Telemetry Display
# ============================================================================


@given("3 autonomous coding agents are executing tasks in concurrent git worktrees:")
def given_three_autonomous_agents(bdd_us104_ctx: dict[str, Any]):
    root = bdd_us104_ctx["project_dir"]
    wt_parent = root / ".worktrees"
    wt_parent.mkdir(parents=True, exist_ok=True)

    # 1. TASK-0012
    wt1 = wt_parent / "task-0012"
    wt1.mkdir(parents=True, exist_ok=True)
    (wt1 / ".specops").mkdir(parents=True, exist_ok=True)
    (wt1 / ".specops" / "worker.json").write_text(
        json.dumps({
            "task_id": "TASK-0012",
            "title": "Implement profile parser",
            "branch": "feat/task-0012",
            "status": "Running",
            "retries": "0/3",
            "active_preflight_check": "uv run pytest",
            "elapsed_seconds": 90,
            "memory_mb": 128.0,
        }),
        encoding="utf-8",
    )

    # 2. TASK-0015
    wt2 = wt_parent / "task-0015"
    wt2.mkdir(parents=True, exist_ok=True)
    (wt2 / ".specops").mkdir(parents=True, exist_ok=True)
    (wt2 / ".specops" / "worker.json").write_text(
        json.dumps({
            "task_id": "TASK-0015",
            "title": "AST file decomposition helper",
            "branch": "feat/task-0015",
            "status": "Self-Healing",
            "retries": "2/3",
            "active_preflight_check": "spec-ops health",
            "elapsed_seconds": 150,
            "memory_mb": 256.0,
        }),
        encoding="utf-8",
    )

    # 3. TASK-0018
    wt3 = wt_parent / "task-0018"
    wt3.mkdir(parents=True, exist_ok=True)
    (wt3 / ".specops").mkdir(parents=True, exist_ok=True)
    (wt3 / ".specops" / "worker.json").write_text(
        json.dumps({
            "task_id": "TASK-0018",
            "title": "Governed spike lifecycle runner",
            "branch": "feat/task-0018",
            "status": "Running",
            "retries": "1/3",
            "active_preflight_check": "git commit preflight",
            "elapsed_seconds": 210,
            "memory_mb": 192.0,
        }),
        encoding="utf-8",
    )


@when(parsers.parse('Jordan opens the "{tab_name}" tab in the visualizer'))
def when_jordan_opens_lead_console(bdd_us104_ctx: dict[str, Any], tab_name: str):
    bdd_us104_ctx["html_content"] = compile_bundle(bdd_us104_ctx["config"])


@then("a real-time fleet grid renders each active worktree with branch name, status badge, and elapsed runtime")
def then_fleet_grid_renders(bdd_us104_ctx: dict[str, Any]):
    content = bdd_us104_ctx["html_content"]
    test_js = """
    window.switchTab('lead');
    const rendered = window.renderLeadConsoleView();
    assert(rendered.includes('TASK-0012'));
    assert(rendered.includes('feat/task-0012'));
    assert(rendered.includes('Running'));
    assert(rendered.includes('TASK-0015'));
    assert(rendered.includes('feat/task-0015'));
    assert(rendered.includes('Self-Healing'));
    assert(rendered.includes('TASK-0018'));
    assert(rendered.includes('feat/task-0018'));
    """
    _run_vis_js(content, test_js)


@then(parsers.parse('the retry counter displays progress indicators (e.g. "{indicator}")'))
def then_retry_counter_displays(bdd_us104_ctx: dict[str, Any], indicator: str):
    content = bdd_us104_ctx["html_content"]
    test_js = f"""
    window.switchTab('lead');
    const rendered = window.renderLeadConsoleView();
    assert(rendered.includes('{indicator}'));
    """
    _run_vis_js(content, test_js)


@then("the telemetry refreshes automatically without requiring manual browser reloads.")
def then_telemetry_refreshes_automatically(bdd_us104_ctx: dict[str, Any]):
    content = bdd_us104_ctx["html_content"]
    test_js = """
    window.switchTab('lead');
    assert.strictEqual(typeof window.renderLeadConsoleView, 'function');
    assert(content.includes('_fleetTelemetryInterval'));
    """
    _run_vis_js(content, test_js)


# ============================================================================
# Scenario 2: Urgent Visual Alerting on Stalled Worker Exhaustion
# ============================================================================


@given('an autonomous worker in ".worktrees/task-0015" fails its 3rd self-healing attempt and stalls')
def given_worker_stalls_attempt_3(bdd_us104_ctx: dict[str, Any]):
    root = bdd_us104_ctx["project_dir"]
    wt = root / ".worktrees" / "task-0015"
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".specops").mkdir(parents=True, exist_ok=True)
    (wt / ".specops" / "worker.json").write_text(
        json.dumps({
            "task_id": "TASK-0015",
            "title": "AST file decomposition helper",
            "branch": "feat/task-0015",
            "status": "Stalled",
            "attempt": "3/3",
            "retries": "3/3",
            "stalled": True,
            "failure_log": "File length violation: helper.py contains 540 lines (exceeds 500 line limit)",
        }),
        encoding="utf-8",
    )
    (wt / ".task-prompt.md").write_text(
        "Working on TASK-0015 (Attempt 3)\nLast generated agent prompt for AST file decomposition helper",
        encoding="utf-8",
    )


@when("the visualizer receives updated fleet state")
def when_visualizer_receives_updated_fleet(bdd_us104_ctx: dict[str, Any]):
    bdd_us104_ctx["html_content"] = compile_bundle(bdd_us104_ctx["config"])


@then("a high-visibility rescue banner appears at the top of the Lead Console")
def then_rescue_banner_appears(bdd_us104_ctx: dict[str, Any]):
    content = bdd_us104_ctx["html_content"]
    test_js = """
    window.switchTab('lead');
    const rendered = window.renderLeadConsoleView();
    assert(rendered.includes('rescue-banner'));
    assert(rendered.includes('TASK-0015 Stalled: Awaiting Human Takeover'));
    """
    _run_vis_js(content, test_js)


@then('the row for "TASK-0015" transitions to status "Stalled: Human Takeover Required" with an amber alert border')
def then_row_transitions_to_stalled(bdd_us104_ctx: dict[str, Any]):
    content = bdd_us104_ctx["html_content"]
    test_js = """
    window.switchTab('lead');
    const rendered = window.renderLeadConsoleView();
    assert(rendered.includes('Stalled: Human Takeover Required'));
    assert(rendered.includes('row-stalled') || rendered.includes('border: 2px solid #f59e0b'));
    """
    _run_vis_js(content, test_js)


@then("the dashboard displays the exact diagnostic failure excerpt and the last generated agent prompt.")
def then_dashboard_displays_diagnostics(bdd_us104_ctx: dict[str, Any]):
    content = bdd_us104_ctx["html_content"]
    test_js = """
    window.switchTab('lead');
    const rendered = window.renderLeadConsoleView();
    assert(rendered.includes('File length violation: helper.py contains 540 lines'));
    assert(rendered.includes('Last generated agent prompt for AST file decomposition helper'));
    """
    _run_vis_js(content, test_js)


# ============================================================================
# Scenario 3: One-Click Rescue Launch and Diagnostic Handshake
# ============================================================================


@given("a stalled worker task displayed in the visualizer Lead Console")
def given_stalled_task_displayed(bdd_us104_ctx: dict[str, Any]):
    root = bdd_us104_ctx["project_dir"]
    wt = root / ".worktrees" / "task-0015"
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".specops").mkdir(parents=True, exist_ok=True)
    (wt / ".specops" / "worker.json").write_text(
        json.dumps({
            "task_id": "TASK-0015",
            "title": "AST file decomposition helper",
            "branch": "feat/task-0015",
            "status": "Stalled",
            "attempt": "3/3",
            "retries": "3/3",
            "stalled": True,
            "failure_log": "Invariant check failed: 540 lines in helper.py",
        }),
        encoding="utf-8",
    )
    (wt / ".task-prompt.md").write_text("Working on TASK-0015 (Attempt 3)", encoding="utf-8")
    bdd_us104_ctx["html_content"] = compile_bundle(bdd_us104_ctx["config"])


@when(parsers.parse('Jordan clicks the "{btn_label}" button on the task card'))
def when_jordan_clicks_rescue_button(bdd_us104_ctx: dict[str, Any], btn_label: str):
    pass


@then(parsers.parse('the console copies the exact terminal command "{cmd}" to the system clipboard'))
def then_console_copies_rescue_cmd(bdd_us104_ctx: dict[str, Any], cmd: str):
    content = bdd_us104_ctx["html_content"]
    test_js = f"""
    window.switchTab('lead');
    window.takeoverTask('TASK-0015').then(() => {{
      assert.strictEqual(clipboardContent, '{cmd}');
    }});
    """
    _run_vis_js(content, test_js)


@then("opens an inspection drawer showing the file diff, last preflight terminal output, and instructions for developer handover.")
def then_opens_inspection_drawer(bdd_us104_ctx: dict[str, Any]):
    content = bdd_us104_ctx["html_content"]
    test_js = """
    window.switchTab('lead');
    assert.strictEqual(typeof window.renderWorktreeTelemetryCard, 'function');
    const drawerHtml = window.renderWorktreeTelemetryCard({ id: 'TASK-0015' });
    assert(drawerHtml.includes('Worktree Fleet Diagnostics'));
    assert(drawerHtml.includes('Developer Handover'));
    assert(drawerHtml.includes('File Diff'));
    assert(drawerHtml.includes('Last Preflight Terminal Output / Failure Feedback'));
    assert(drawerHtml.includes('Instructions for Developer Handover'));
    assert(drawerHtml.includes('spec-ops rescue TASK-0015'));
    """
    _run_vis_js(content, test_js)
