"""Executable BDD scenarios for US-0026: Living Visualizer Lead Console with Real-Time Fleet Telemetry."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.bundle import compile_bundle
from tests.test_visualizer import run_node_test

scenarios("features/us_0026_living_visualizer_lead_console_and_fleet_telemetry.feature")


def _run_vis_js(html: str, user_js: str) -> None:
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert len(scripts) >= 2
    full_js = f"""
    {scripts[0]}
    {scripts[1]}
    {user_js}
    """
    run_node_test(html, full_js)


@pytest.fixture
def bdd_telemetry_ctx(tmp_path: Path) -> dict[str, Any]:
    project_dir = tmp_path / "telemetry_proj"
    init_project(project_dir, name="LeadTelemetryProject")
    config = load_config(root_dir=project_dir)
    return {
        "project_dir": project_dir,
        "config": config,
        "html_content": None,
    }


@given("multiple autonomous workers running across isolated git worktrees")
def given_multiple_workers_in_worktrees(bdd_telemetry_ctx: dict[str, Any]):
    root = bdd_telemetry_ctx["project_dir"]
    wt1 = root / ".worktrees" / "task-0013"
    wt1.mkdir(parents=True, exist_ok=True)
    (wt1 / ".task-prompt.md").write_text("Working on TASK-0013 (Attempt 1)\npytest running", encoding="utf-8")

    wt2 = root / ".worktrees" / "task-0014"
    wt2.mkdir(parents=True, exist_ok=True)
    (wt2 / ".task-prompt.md").write_text("Working on TASK-0014 (Attempt 2)\nfile limit violation", encoding="utf-8")


@when(parsers.parse('the lead navigates to the "{tab_name}" tab in the visualizer'))
def when_lead_navigates_to_tab(bdd_telemetry_ctx: dict[str, Any], tab_name: str):
    bdd_telemetry_ctx["html_content"] = compile_bundle(bdd_telemetry_ctx["config"])


@then("an active fleet status grid displays:")
def then_fleet_status_grid_displays(bdd_telemetry_ctx: dict[str, Any]):
    content = bdd_telemetry_ctx["html_content"]
    test_js = """
    window.switchTab('lead');
    const rendered = window.renderLeadConsoleView();
    assert(rendered.includes('TASK-0013'));
    assert(rendered.includes('TASK-0014'));
    assert(rendered.includes('Executing'));
    assert(rendered.includes('Self-Healing'));
    assert(rendered.includes('Fixing file limit'));
    assert(rendered.includes('.worktrees/task-0013'));
    assert(rendered.includes('.worktrees/task-0014'));
    """
    _run_vis_js(content, test_js)


@then("the telemetry updates dynamically without page reloads.")
def then_telemetry_updates_dynamically(bdd_telemetry_ctx: dict[str, Any]):
    content = bdd_telemetry_ctx["html_content"]
    test_js = """
    window.switchTab('lead');
    assert.strictEqual(typeof window.renderLeadConsoleView, 'function');
    """
    _run_vis_js(content, test_js)


@given("an autonomous worker has exhausted its maximum attempts (3/3) and stalled")
def given_worker_stalled(bdd_telemetry_ctx: dict[str, Any]):
    root = bdd_telemetry_ctx["project_dir"]
    wt = root / ".worktrees" / "task-0014"
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".task-prompt.md").write_text(
        "Working on TASK-0014 (Attempt 3)\n## Preflight Failure Feedback\nFile length violation in core.py",
        encoding="utf-8",
    )


@when("the lead views the Lead Console")
def when_lead_views_console(bdd_telemetry_ctx: dict[str, Any]):
    bdd_telemetry_ctx["html_content"] = compile_bundle(bdd_telemetry_ctx["config"])


@then(parsers.parse('an urgent rescue banner appears highlighting "{banner_text}"'))
def then_urgent_rescue_banner(bdd_telemetry_ctx: dict[str, Any], banner_text: str):
    content = bdd_telemetry_ctx["html_content"]
    test_js = f"""
    window.switchTab('lead');
    const rendered = window.renderLeadConsoleView();
    assert(rendered.includes('{banner_text}'));
    """
    _run_vis_js(content, test_js)


@then(parsers.parse('clicking "{btn_label}" displays the agent\'s failure log and "{prompt_file}" feedback.'))
def then_click_inspect_displays_log(bdd_telemetry_ctx: dict[str, Any], btn_label: str, prompt_file: str):
    content = bdd_telemetry_ctx["html_content"]
    test_js = """
    window.switchTab('lead');
    const rendered = window.renderLeadConsoleView();
    assert(rendered.includes('File length violation in core.py'));
    """
    _run_vis_js(content, test_js)


@given("a stalled task displayed in the rescue panel of the Lead Console")
def given_stalled_task_in_rescue(bdd_telemetry_ctx: dict[str, Any]):
    root = bdd_telemetry_ctx["project_dir"]
    wt = root / ".worktrees" / "task-0014"
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".task-prompt.md").write_text("(Attempt 3) Stalled awaiting human takeover", encoding="utf-8")
    bdd_telemetry_ctx["html_content"] = compile_bundle(bdd_telemetry_ctx["config"])


@when(parsers.parse('the lead clicks "{btn_label}"'))
def when_lead_clicks_takeover(bdd_telemetry_ctx: dict[str, Any], btn_label: str):
    pass


@then(parsers.parse('the console copies the exact command "{cmd}" to the clipboard'))
def then_copies_command_to_clipboard(bdd_telemetry_ctx: dict[str, Any], cmd: str):
    content = bdd_telemetry_ctx["html_content"]
    test_js = f"""
    window.switchTab('lead');
    window.takeoverTask('TASK-0014').then(() => {{
      assert(clipboardContent.includes('{cmd}'));
    }});
    """
    _run_vis_js(content, test_js)


@then("provides a deep link directly to the task specification and failure diff.")
def then_provides_deep_link(bdd_telemetry_ctx: dict[str, Any]):
    content = bdd_telemetry_ctx["html_content"]
    test_js = """
    window.switchTab('lead');
    const rendered = window.renderLeadConsoleView();
    assert(rendered.includes('#entity=TASK-0014'));
    """
    _run_vis_js(content, test_js)
