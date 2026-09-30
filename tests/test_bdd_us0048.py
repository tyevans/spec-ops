"""BDD step definitions for US-0048: Persona-to-Commit Traceability Matrix and Coverage Auditor."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.generator import generate_standalone_html

scenarios("features/us_0048_persona_traceability.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="TraceabilityBDD")
    return {
        "root": tmp_path,
        "res": None,
        "html": "",
        "persona_selection": "",
        "last_copied": "",
    }


def _run_cli(root: Path, cmd_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *cmd_args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


from tests.test_visualizer import run_node_test


def _run_node_harness(html: str, test_script: str) -> None:
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    full_js = f"{scripts[0]}\n{scripts[1]}\n{test_script}"
    run_node_test(html, full_js)


@given('documented personas in "PERSONAS.md" and linked stories across the backlog')
def documented_personas_and_linked_stories(bdd_context: dict[str, Any]):
    root = bdd_context["root"]
    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    backlog_dir = root / "docs" / "project" / "backlog" / "complete"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)

    # Ensure Taylor is in PERSONAS.md
    p_file = root / "docs" / "project" / "user_stories" / "PERSONAS.md"
    current_p = p_file.read_text(encoding="utf-8") if p_file.exists() else ""
    if "Taylor" not in current_p:
        p_file.write_text(
            current_p + "\n\n## 5. Taylor — The Product Manager\n- **Role**: Product manager.\n",
            encoding="utf-8",
        )

    # PRD-0001
    (prd_dir / "prd-0001-visualizer.md").write_text(
        """---
id: '0001'
title: Living 2D Graph Visualizer
status: Accepted
target_persona: Taylor (The Product Manager)
component: visualizer
---

# PRD-0001 — Living 2D Graph Visualizer

## Checkable Outcomes
1. Visualizer displays interactive node graph
""",
        encoding="utf-8",
    )

    # US-0006 & US-0009
    (stories_dir / "us-0006-living-graph.md").write_text(
        """---
id: '0006'
title: Living 2D Graph Visualizer
status: Accepted
persona: Taylor (The Product Manager)
feature: FEAT-VIS-01
governing_prd: PRD-0001
---
# US-0006
""",
        encoding="utf-8",
    )

    (stories_dir / "us-0009-matrix-dashboard.md").write_text(
        """---
id: '0009'
title: Multi-View Project Matrix Dashboard
status: Accepted
persona: Taylor (The Product Manager)
feature: FEAT-VIS-04
governing_prd: PRD-0001
---
# US-0009
""",
        encoding="utf-8",
    )

    # TASK-0008 & TASK-0013
    (backlog_dir / "0008-graph-canvas.md").write_text(
        """---
id: '0008'
title: Graph Canvas Renderer
status: Complete
governing_prds:
  - PRD-0001
governing_stories:
  - US-0006
---
# TASK-0008
""",
        encoding="utf-8",
    )

    (backlog_dir / "0013-matrix-view.md").write_text(
        """---
id: '0013'
title: Matrix View Renderer
status: Complete
governing_prds:
  - PRD-0001
governing_stories:
  - US-0009
---
# TASK-0013
""",
        encoding="utf-8",
    )


@when(parsers.parse('Taylor selects "{selection}" in the visualizer Traceability Matrix'))
def taylor_selects_persona(bdd_context: dict[str, Any], selection: str):
    root = bdd_context["root"]
    config = load_config(root_dir=root)
    html = generate_standalone_html(config)
    bdd_context["html"] = html
    bdd_context["persona_selection"] = selection


@then("the interface renders a multi-column lineage view:")
def interface_renders_multi_column_lineage(bdd_context: dict[str, Any]):
    html = bdd_context["html"]
    selection = bdd_context["persona_selection"]

    test_js = f"""
    location.hash = "#tab=matrix";
    location.href = "http://localhost:8080/#tab=matrix";

    const t8 = (window.PROJECT_DATA.tasks || []).find(t => t.id === 'TASK-0008');
    if (t8) t8.commits = [{{ hash: 'abc1234', author: 'Ty', date: '2026-09-29', subject: 'TASK-0008 canvas' }}];
    const t13 = (window.PROJECT_DATA.tasks || []).find(t => t.id === 'TASK-0013');
    if (t13) t13.commits = [{{ hash: 'def5678', author: 'Ty', date: '2026-09-29', subject: 'TASK-0013 matrix' }}];

    window.switchTab('matrix');
    window.setMatrixFilter('persona', '{selection}');
    const content = elements['dashboard-content'].innerHTML;

    // Verify multi-column lineage table header
    assert(content.includes('<th>Persona</th>'));
    assert(content.includes('<th>PRD</th>'));
    assert(content.includes('<th>User Story</th>'));
    assert(content.includes('<th>Backlog Task</th>'));
    assert(content.includes('<th>Git Commit</th>'));
    assert(content.includes('<th>Status</th>'));

    // Verify rows contain expected entities
    assert(content.includes('Taylor'));
    assert(content.includes('PRD-0001'));
    assert(content.includes('US-0006'));
    assert(content.includes('TASK-0008'));
    assert(content.includes('abc1234'));

    assert(content.includes('US-0009'));
    assert(content.includes('TASK-0013'));
    assert(content.includes('def5678'));
    """
    _run_node_harness(html, test_js)


@then("clicking any node in the lineage chain highlights its connections across the entire project graph.")
def clicking_node_highlights_connections(bdd_context: dict[str, Any]):
    html = bdd_context["html"]
    test_js = """
    window.openDrawer('TASK-0008');
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert.strictEqual(elements['drawer-title'].textContent.includes('TASK-0008'), true);
    """
    _run_node_harness(html, test_js)


@given('the project has active tasks in "proposed/" and "refined/"')
def project_has_active_tasks(bdd_context: dict[str, Any]):
    root = bdd_context["root"]
    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    refined_dir = root / "docs" / "project" / "backlog" / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)

    # Ensure Taylor is in PERSONAS.md
    p_file = root / "docs" / "project" / "user_stories" / "PERSONAS.md"
    current_p = p_file.read_text(encoding="utf-8") if p_file.exists() else ""
    if "Taylor" not in current_p:
        p_file.write_text(
            current_p + "\n\n## 5. Taylor — The Product Manager\n- **Role**: Product manager.\n",
            encoding="utf-8",
        )

    # Active story for Alex
    (stories_dir / "us-0001-alex.md").write_text(
        """---
id: '0001'
title: Architect Core Invariants
status: Accepted
persona: Alex (The Agentic Systems Architect)
---
# US-0001
""",
        encoding="utf-8",
    )

    # Task for Alex
    (refined_dir / "0001-alex-task.md").write_text(
        """---
id: '0001'
title: Task for Alex
status: Refined
governing_stories:
  - US-0001
---
# TASK-0001
""",
        encoding="utf-8",
    )

    # Orphan task (no governing story)
    (proposed_dir / "0099-orphan.md").write_text(
        """---
id: '0099'
title: Rogue task without story
status: Proposed
---
# TASK-0099
""",
        encoding="utf-8",
    )


@when(parsers.parse('{persona} executes "{cmd}" or views the Persona Studio'))
def executes_stats_persona_coverage(bdd_context: dict[str, Any], persona: str, cmd: str):
    root = bdd_context["root"]
    parts = cmd.split()
    assert parts[0] == "spec-ops"
    res = _run_cli(root, parts[1:])
    bdd_context["res"] = res


@then("a coverage distribution report is displayed showing task allocation per persona")
def coverage_distribution_report_displayed(bdd_context: dict[str, Any]):
    res = bdd_context["res"]
    assert res.returncode == 0
    assert "Persona Coverage" in res.stdout
    assert "Alex" in res.stdout
    assert "Taylor" in res.stdout


@then(parsers.parse("warns when a persona has 0 active stories in the current milestone"))
def warns_zero_active_stories(bdd_context: dict[str, Any]):
    res = bdd_context["res"]
    assert "Warning: Persona" in res.stdout
    assert "0 active stories in the current milestone" in res.stdout


@then(parsers.parse('flags any backlog task lacking a governing user story or persona lineage as an "Orphan Task".'))
def flags_orphan_task(bdd_context: dict[str, Any]):
    res = bdd_context["res"]
    assert "Orphan Task: TASK-0099" in res.stdout or "Orphan Task: 0099" in res.stdout


@given(parsers.parse('Taylor receives an inquiry from leadership asking about progress on "{title}"'))
def taylor_receives_inquiry(bdd_context: dict[str, Any], title: str):
    root = bdd_context["root"]
    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)

    (prd_dir / "prd-0001-visualizer.md").write_text(
        f"""---
id: '0001'
title: {title}
status: Accepted
component: visualizer
---
# PRD-0001 — {title}
""",
        encoding="utf-8",
    )
    (stories_dir / "us-0006-living-graph.md").write_text(
        """---
id: '0006'
title: Living 2D Graph Visualizer
status: Accepted
feature: FEAT-VIS-01
governing_prd: PRD-0001
---
# US-0006
""",
        encoding="utf-8",
    )
    config = load_config(root_dir=root)
    bdd_context["html"] = generate_standalone_html(config)


@when(parsers.parse('Taylor filters the Traceability Matrix by "{filter_query}"'))
def taylor_filters_matrix(bdd_context: dict[str, Any], filter_query: str):
    bdd_context["filter_query"] = filter_query


@when('clicks "Copy Shareable Link"')
def clicks_copy_shareable_link(bdd_context: dict[str, Any]):
    html = bdd_context["html"]
    filter_query = bdd_context["filter_query"]

    test_js = f"""
    location.hash = "#tab=matrix";
    location.href = "http://localhost:8080/#tab=matrix";
    window.switchTab('matrix');
    window.setMatrixFilter('query', '{filter_query}');
    const permalink = window.copyMatrixShareableLink();
    assert(permalink.includes('#tab=prds&entity=PRD-0001&filter={filter_query}'));
    """
    _run_node_harness(html, test_js)
    bdd_context["last_copied"] = f"#tab=prds&entity=PRD-0001&filter={filter_query}"


@then(parsers.parse('the clipboard receives a deep link permalink with URL state "{expected_url_state}"'))
def clipboard_receives_permalink(bdd_context: dict[str, Any], expected_url_state: str):
    last = bdd_context["last_copied"]
    assert expected_url_state in last


@then("recipient opening the URL sees the exact filtered lineage and delivery progress without logging in.")
def recipient_opening_url_sees_lineage(bdd_context: dict[str, Any]):
    html = bdd_context["html"]
    last = bdd_context["last_copied"]

    test_js = f"""
    location.hash = '{last}';
    location.href = 'http://localhost:8080/{last}';
    const parsed = window.parseHash('{last}');
    assert.strictEqual(parsed.tab, 'prds');
    assert.strictEqual(parsed.entity, 'PRD-0001');
    assert(parsed.q === 'FEAT-VIS-01' || elements['search-input']?.value === 'FEAT-VIS-01');
    """
    _run_node_harness(html, test_js)
