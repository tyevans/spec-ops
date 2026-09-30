"""Executable BDD scenarios for US-0058 and US-0114: Living Security Posture and Compliance Radar."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.bundle import compile_bundle
from tests.test_visualizer import _run_node_test

scenarios("features/us_0058_living_security_radar.feature")


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
def bdd_security_radar_ctx(tmp_path: Path) -> dict[str, Any]:
    project_dir = tmp_path / "sec_radar_proj"
    init_project(project_dir, name="SecRadarProject")

    # Set up some sample tasks with diverse compliance states
    backlog = project_dir / "docs" / "project" / "backlog"
    complete_dir = backlog / "complete"
    refined_dir = backlog / "refined"
    complete_dir.mkdir(parents=True, exist_ok=True)
    refined_dir.mkdir(parents=True, exist_ok=True)

    # Compliant completed task
    (complete_dir / "0030-auth-gate.md").write_text(
        """---
id: '0030'
title: Cryptographic Verification Gate
status: Complete
target_bc: security
signed_off_by: 'Sasha <sasha@specops.dev>'
signed_off_at: '2026-09-29T18:00:00Z'
commit_signature_status: 'Signed'
has_signed_commits: true
---
# TASK-0030: Cryptographic Verification Gate
""",
        encoding="utf-8",
    )

    # Non-compliant task lacking sign-off and commit signature
    (refined_dir / "0031-unreviewed-task.md").write_text(
        """---
id: '0031'
title: Unreviewed Microservice Feature
status: Refined
target_bc: core
commit_signature_status: 'Unsigned'
has_signed_commits: false
---
# TASK-0031: Unreviewed Microservice Feature
""",
        encoding="utf-8",
    )

    # Initialize git repo so git metadata harvester and scanner work cleanly
    subprocess.run(["git", "init", "-b", "main"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Security Officer"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.email", "security@specops.dev"], cwd=project_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "feat: initial commit for security radar project"], cwd=project_dir, check=True)

    config = load_config(root_dir=project_dir)
    return {
        "project_dir": project_dir,
        "config": config,
        "html_content": None,
    }


@given("the standalone visualizer is open in a web browser")
def given_visualizer_open(bdd_security_radar_ctx: dict[str, Any]) -> None:
    bdd_security_radar_ctx["html_content"] = compile_bundle(bdd_security_radar_ctx["config"])


@when('the user navigates to the "Security & Compliance" tab or URL hash "#tab=security"')
def when_navigates_to_security_tab(bdd_security_radar_ctx: dict[str, Any]) -> None:
    pass


@then("the view renders five summary metric cards:")
def then_renders_five_summary_metric_cards(bdd_security_radar_ctx: dict[str, Any]) -> None:
    html = bdd_security_radar_ctx["html_content"]
    test_js = """
    window.location.hash = '#tab=security';
    triggerPopState();
    assert.strictEqual(window.location.hash, '#tab=security');

    const htmlView = window.renderSecurityRadarView();
    assert(htmlView.includes('Secret Scan Status'));
    assert(htmlView.includes('Lockfile Integrity'));
    assert(htmlView.includes('Signed Commit Coverage'));
    assert(htmlView.includes('Human Sign-off Rate'));
    assert(htmlView.includes('Known Vulnerability Count'));

    // Check card element wrappers
    assert(htmlView.includes('id="card-secret-scan"'));
    assert(htmlView.includes('id="card-lockfile-integrity"'));
    assert(htmlView.includes('id="card-signed-commit-coverage"'));
    assert(htmlView.includes('id="card-human-signoff-rate"'));
    assert(htmlView.includes('id="card-known-vulnerability-count"'));
    """
    _run_vis_js(html, test_js)


@then("tasks pending human sign-off are listed in an interactive triage table.")
def then_tasks_pending_human_signoff_listed(bdd_security_radar_ctx: dict[str, Any]) -> None:
    html = bdd_security_radar_ctx["html_content"]
    test_js = """
    window.location.hash = '#tab=security';
    triggerPopState();
    const htmlView = window.renderSecurityRadarView();
    assert(htmlView.includes('id="compliance-triage-table"'));
    assert(htmlView.includes('TASK-0031'));
    assert(htmlView.includes('Pending'));
    """
    _run_vis_js(html, test_js)


@given("the user is on the Security & Compliance tab")
def given_user_on_security_tab(bdd_security_radar_ctx: dict[str, Any]) -> None:
    bdd_security_radar_ctx["html_content"] = compile_bundle(bdd_security_radar_ctx["config"])


@when('the user toggles the "Show Only Unsigned / Unreviewed" filter')
def when_user_toggles_unsigned_filter(bdd_security_radar_ctx: dict[str, Any]) -> None:
    pass


@then("the board filters to display only tasks lacking cryptographic signatures or human sign-off approvals")
@then('toggling "Show Only Unsigned / Unreviewed" filters tasks to display only non-compliant items blocking release cut-off.')
def then_board_filters_to_non_compliant(bdd_security_radar_ctx: dict[str, Any]) -> None:
    html = bdd_security_radar_ctx["html_content"]
    test_js = """
    window.location.hash = '#tab=security';
    triggerPopState();

    // Toggle filter ON
    window.toggleUnsignedFilter(true);
    assert.strictEqual(window.securityRadarFilterState.showOnlyUnsigned, true);

    const filteredHtml = window.renderSecurityRadarView();
    // Non-compliant task must be visible
    assert(filteredHtml.includes('TASK-0031'));
    assert(filteredHtml.includes('Non-Compliant'));

    // Fully compliant task must be filtered out
    assert(!filteredHtml.includes('TASK-0030'));
    """
    _run_vis_js(html, test_js)


@then("clicking any row opens the task drawer displaying the exact missing compliance artifacts.")
def then_clicking_row_opens_drawer_with_artifacts(bdd_security_radar_ctx: dict[str, Any]) -> None:
    html = bdd_security_radar_ctx["html_content"]
    test_js = """
    window.location.hash = '#tab=security';
    triggerPopState();

    // Open drawer for the non-compliant task
    window.openDrawer('TASK-0031');

    const drawerBody = window.document.getElementById('drawer-body').innerHTML;
    assert(drawerBody.includes('Compliance &amp; Security Posture'));
    assert(drawerBody.includes('Missing Compliance Artifacts:'));
    assert(drawerBody.includes('Human Review Sign-off'));
    assert(drawerBody.includes('Cryptographic Commit Signature'));
    assert(drawerBody.includes('Permalink URL:'));
    assert(drawerBody.includes('#tab=security&entity=TASK-0031'));
    """
    _run_vis_js(html, test_js)
