"""Executable BDD scenarios for US-0131 / TASK-0254: Relational Graph Traceability and Architecture Radar.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007; PRD-0005; US-0131.
Target Bounded Context: visualizer. File length strictly under 400 lines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.cli.graph_handler import handle_graph_command
from spec_ops.cli.parser import build_parser
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.cache import RelationalGraphCacheEngine
from spec_ops.core.graph_audit import audit_graph_all
from spec_ops.core.models import ProjectData, Task
from spec_ops.core.pathfinder import inspect_entity
from spec_ops.core.topology import DirectedGraph
from spec_ops.visualizer.drawer_script import DRAWER_JS
from spec_ops.visualizer.generator import generate_standalone_html, serialize_project_data
from spec_ops.worker.claimer import hydrate_task_prompt

scenarios("features/us_0131_adr_amendment_graph_and_radar.feature")


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    return {}


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _create_minimal_valid_project(root_dir: Path) -> None:
    """Creates minimal valid PMaC project structure for graph compilation and verification."""
    d = root_dir / "docs" / "project"
    _write_file(d / "user_stories" / "PERSONAS.md", "# Personas\n## Alex (The Agentic Systems Architect)\n")
    _write_file(
        d / "user_stories" / "accepted" / "us-0001.md",
        "---\nid: '0001'\ntitle: Workflow\npersona: Alex (The Agentic Systems Architect)\ngoverning_prd: PRD-0001\nscenarios: [S1]\n---\n# US-0001\n",
    )
    _write_file(
        d / "product" / "accepted" / "prd-0001.md",
        "---\nid: '0001'\ntitle: Engine\ntarget_persona: Alex (The Agentic Systems Architect)\nlinked_stories: [US-0001]\n---\n# PRD-0001\n",
    )
    _write_file(
        d / "backlog" / "refined" / "0001-task.md",
        "---\nid: '0001'\ntitle: Task 1\nstatus: Refined\npersona: Alex\ngoverning_prds: [PRD-0001]\ngoverning_stories: [US-0001]\ngoverning_adrs: [ADR-0102]\nmutation_scope: [src/spec_ops]\n---\n# TASK-0001\n",
    )


# --- Scenario 1: Compiling bidirectional ADR-to-ADR amends and supersedes edges ---


@given('a set of ADRs where ADR-0116 has frontmatter "amends: [ADR-0102]" and ADR-0120 has "supersedes: [ADR-0118]"')
def step_given_adrs_with_amends_and_supersedes(bdd_ctx: dict[str, Any], tmp_path: Path) -> None:
    _create_minimal_valid_project(tmp_path)
    a_dir = tmp_path / "docs" / "project" / "adrs" / "accepted"
    _write_file(a_dir / "adr-0102.md", "---\nid: ADR-0102\ntitle: Store Ports\nstatus: Accepted\namended_by: [ADR-0116]\n---\n# ADR-0102\n")
    _write_file(a_dir / "adr-0116.md", "---\nid: ADR-0116\ntitle: Capabilities\nstatus: Accepted\namends: [ADR-0102]\n---\n# ADR-0116\n")
    _write_file(a_dir / "adr-0118.md", "---\nid: ADR-0118\ntitle: Old Dec\nstatus: Superseded\nsuperseded_by: ADR-0120\n---\n# ADR-0118\n")
    _write_file(a_dir / "adr-0120.md", "---\nid: ADR-0120\ntitle: New Dec\nstatus: Accepted\nsupersedes: ADR-0118\n---\n# ADR-0120\n")
    bdd_ctx["root_dir"] = tmp_path
    bdd_ctx["config"] = SpecOpsConfig(root_dir=tmp_path)


@when('the relational graph compiler runs via "spec-ops graph compile"')
def step_when_graph_compile_runs(bdd_ctx: dict[str, Any]) -> None:
    engine = RelationalGraphCacheEngine(bdd_ctx["root_dir"])
    data, _ = engine.compile_graph(force_cold=True)
    bdd_ctx["project_data"] = data
    bdd_ctx["graph"] = DirectedGraph.from_project_data(data)


@then('the graph includes directed edge "(ADR-0116)-[:amends]->(ADR-0102)"')
def step_then_edge_amends_exists(bdd_ctx: dict[str, Any]) -> None:
    data = bdd_ctx["project_data"]
    edge_tuples = {(e.source_id, e.target_id, e.relation) for e in data.edges}
    assert ("ADR-0116", "ADR-0102", "amends") in edge_tuples
    assert bdd_ctx["graph"].edge_relations.get(("ADR-0116", "ADR-0102")) == "amends"


@then('the graph includes directed edge "(ADR-0120)-[:supersedes]->(ADR-0118)"')
def step_then_edge_supersedes_exists(bdd_ctx: dict[str, Any]) -> None:
    data = bdd_ctx["project_data"]
    edge_tuples = {(e.source_id, e.target_id, e.relation) for e in data.edges}
    assert ("ADR-0120", "ADR-0118", "supersedes") in edge_tuples
    assert bdd_ctx["graph"].edge_relations.get(("ADR-0120", "ADR-0118")) == "supersedes"


@then('"spec-ops trace --verify" passes with 100% graph connectivity')
def step_then_trace_verify_passes(bdd_ctx: dict[str, Any]) -> None:
    code, msgs = audit_graph_all(bdd_ctx["project_data"])
    assert code == 0, f"Audit errors: {msgs}"


# --- Scenario 2: Rendering amended ADRs with distinct active badges and evolution drawers ---


@given('an ADR "ADR-0101" that is amended by "ADR-0135" and "ADR-0136"')
def step_given_adr_amended_by_two(bdd_ctx: dict[str, Any], tmp_path: Path) -> None:
    _create_minimal_valid_project(tmp_path)
    a_dir = tmp_path / "docs" / "project" / "adrs" / "accepted"
    _write_file(a_dir / "adr-0101.md", "---\nid: ADR-0101\ntitle: Event Log\nstatus: Accepted\namended_by: [ADR-0135, ADR-0136]\n---\n# ADR-0101\n")
    _write_file(a_dir / "adr-0135.md", "---\nid: ADR-0135\ntitle: Provenance\nstatus: Accepted\namends: [ADR-0101]\n---\n# ADR-0135\n")
    _write_file(a_dir / "adr-0136.md", "---\nid: ADR-0136\ntitle: Merge Resolution\nstatus: Accepted\namends: [ADR-0101]\n---\n# ADR-0136\n")
    bdd_ctx["root_dir"] = tmp_path
    bdd_ctx["config"] = SpecOpsConfig(root_dir=tmp_path)


@when("viewing the Architecture Radar or ADR tab in the living visualizer")
def step_when_viewing_visualizer(bdd_ctx: dict[str, Any]) -> None:
    bdd_ctx["html"] = generate_standalone_html(bdd_ctx["config"])
    bdd_ctx["payload"] = serialize_project_data(bdd_ctx["config"])
    bdd_ctx["drawer_js"] = DRAWER_JS


@then("ADR-0101 is rendered with an active status badge rather than a strikethrough red badge")
def step_then_active_status_badge(bdd_ctx: dict[str, Any]) -> None:
    payload = bdd_ctx["payload"]
    adrs = {a["id"]: a for a in payload["adrs"]}
    assert "ADR-0101" in adrs
    adr101 = adrs["ADR-0101"]
    assert adr101["status"] == "Accepted"
    assert "ADR-0135" in adr101["amended_by"]
    assert "ADR-0136" in adr101["amended_by"]
    assert "Amended" in bdd_ctx["html"]


@then('opening the ADR detail drawer displays an "Amendments" lineage section linking directly to ADR-0135 and ADR-0136')
def step_then_drawer_displays_amendments(bdd_ctx: dict[str, Any]) -> None:
    drawer_js = bdd_ctx["drawer_js"]
    assert "Amendments" in drawer_js
    assert "a.amended_by" in drawer_js


@then('viewing ADR-0135 in the drawer displays "Amends: ADR-0101"')
def step_then_drawer_displays_amends(bdd_ctx: dict[str, Any]) -> None:
    drawer_js = bdd_ctx["drawer_js"]
    assert "Amends" in drawer_js
    assert "a.amends" in drawer_js


# --- Scenario 3: Hydrating amending ADR context into pathfinder and autonomous worker contracts ---


@given('task "TASK-0012" cites "governing_adrs: [ADR-0102]"')
def step_given_task_cites_adr102(bdd_ctx: dict[str, Any], tmp_path: Path) -> None:
    _create_minimal_valid_project(tmp_path)
    a_dir = tmp_path / "docs" / "project" / "adrs" / "accepted"
    _write_file(a_dir / "adr-0102.md", "---\nid: ADR-0102\ntitle: Store Ports\nstatus: Accepted\namended_by: [ADR-0116, ADR-0127]\n---\n# ADR-0102\n")
    _write_file(
        tmp_path / "docs" / "project" / "backlog" / "refined" / "0012-engine.md",
        "---\nid: '0012'\ntitle: Implement Store Engine\nstatus: Refined\ntarget_bc: core\npersona: Alex (The Agentic Systems Architect)\ngoverning_adrs: [ADR-0102]\ngoverning_prds: [PRD-0001]\ngoverning_stories: [US-0001]\nmutation_scope: [src/spec_ops]\n---\n# TASK-0012\nExecute engine implementation.\n",
    )
    bdd_ctx["root_dir"] = tmp_path
    bdd_ctx["config"] = SpecOpsConfig(root_dir=tmp_path)
    bdd_ctx["task"] = Task(
        id="0012",
        title="Implement Store Engine",
        status="Refined",
        target_bc="core",
        governing_adrs=["ADR-0102"],
        governing_prds=["PRD-0001"],
        governing_stories=["US-0001"],
        body="Execute engine implementation.",
    )


@given("ADR-0102 has recorded amendments [ADR-0116, ADR-0127]")
def step_given_recorded_amendments(bdd_ctx: dict[str, Any]) -> None:
    a_dir = bdd_ctx["root_dir"] / "docs" / "project" / "adrs" / "accepted"
    _write_file(a_dir / "adr-0116.md", "---\nid: ADR-0116\ntitle: Capabilities\nstatus: Accepted\namends: [ADR-0102]\n---\n# ADR-0116\n")
    _write_file(a_dir / "adr-0127.md", "---\nid: ADR-0127\ntitle: Refinement\nstatus: Accepted\namends: [ADR-0102]\n---\n# ADR-0127\n")


@when('an autonomous worker session or "spec-ops pathfinder inspect TASK-0012" runs')
def step_when_worker_or_pathfinder_runs(bdd_ctx: dict[str, Any], capsys: pytest.CaptureFixture) -> None:
    bdd_ctx["hydrated_prompt"] = hydrate_task_prompt(bdd_ctx["task"], bdd_ctx["config"])
    engine = RelationalGraphCacheEngine(bdd_ctx["root_dir"])
    data, _ = engine.compile_graph(force_cold=True)
    graph = DirectedGraph.from_project_data(data)
    bdd_ctx["card_output"] = inspect_entity(graph, "TASK-0012", data=data)

    parser = build_parser()
    args = parser.parse_args(["pathfinder", "inspect", "TASK-0012"])
    bdd_ctx["cli_rc"] = handle_graph_command(args, bdd_ctx["config"])
    captured = capsys.readouterr()
    bdd_ctx["cli_output"] = captured.out


@then("the hydrated task context includes both the primary governing decision ADR-0102 and the active amending decisions ADR-0116 and ADR-0127")
def step_then_hydrated_context_includes_both(bdd_ctx: dict[str, Any]) -> None:
    prompt = bdd_ctx["hydrated_prompt"]
    card = bdd_ctx["card_output"]
    cli_out = bdd_ctx["cli_output"]

    assert "ADR-0102" in prompt and "ADR-0116" in prompt and "ADR-0127" in prompt
    assert "active amendments" in prompt.lower()
    assert "ADR-0102" in card and "ADR-0116" in card and "ADR-0127" in card
    assert "active amendments" in card.lower()
    assert bdd_ctx["cli_rc"] == 0
    assert "ADR-0102" in cli_out and "ADR-0116" in cli_out and "ADR-0127" in cli_out
