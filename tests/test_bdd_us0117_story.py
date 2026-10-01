"""BDD step definitions for US-0117: Multi-Faceted BDD User Story Generation and Traceability."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0117_story_generation.feature")


def _run_cli(root: Path, cmd_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *cmd_args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def bdd_story_env(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="StoryBDD")
    return {
        "root": tmp_path,
        "last_res": None,
    }


@given("an accepted PRD with defined checkable outcomes")
def accepted_prd_with_outcomes(bdd_story_env: dict[str, Any]):
    root = bdd_story_env["root"]
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0006.md").write_text(
        "---\n"
        "id: '0006'\n"
        "title: Autonomous SDLC Orchestrator\n"
        "status: Accepted\n"
        "target_persona: Jordan (The AI-Native Engineering Lead)\n"
        "component: core\n"
        "---\n"
        "# PRD-0006 — Autonomous SDLC Orchestrator\n\n"
        "## Checkable Outcomes\n"
        "1. Automated user story authoring.\n",
        encoding="utf-8",
    )


@when(parsers.parse('the orchestrator executes "{cli_cmd}"'))
def orchestrator_executes_command(bdd_story_env: dict[str, Any], cli_cmd: str):
    root = bdd_story_env["root"]
    args = cli_cmd.split()[1:]  # strip spec-ops
    res = _run_cli(root, args)
    bdd_story_env["last_res"] = res


@then('a new user story is scaffolded in "docs/project/user_stories/accepted/"')
def verify_story_scaffolded(bdd_story_env: dict[str, Any]):
    root = bdd_story_env["root"]
    res = bdd_story_env["last_res"]
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"

    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    story_files = list(stories_dir.glob("*.md"))
    assert len(story_files) >= 1, "Expected at least one scaffolded user story file"
    latest_story = sorted(story_files)[-1]
    bdd_story_env["scaffolded_story_file"] = latest_story


@then("executable Gherkin scenarios are generated without private mock backdoors")
def verify_gherkin_scenarios(bdd_story_env: dict[str, Any]):
    story_file: Path = bdd_story_env["scaffolded_story_file"]
    content = story_file.read_text(encoding="utf-8")

    assert "Scenario:" in content
    assert "Given the system is initialized and ready" in content
    assert "When " in content
    assert "Then " in content
    assert "observable outputs satisfy public contracts without backdoor tampering." in content
    assert "mock" not in content.lower()


@then(parsers.parse('"{registry_rel_path}" is updated atomically.'))
def verify_registry_updated(bdd_story_env: dict[str, Any], registry_rel_path: str):
    root = bdd_story_env["root"]
    reg_path = root / registry_rel_path
    assert reg_path.is_file(), f"Registry file missing: {reg_path}"
    content = reg_path.read_text(encoding="utf-8")
    assert "| `US-" in content
    assert "Jordan" in content
    assert "`PRD-0006`" in content


@given("a project repository with PRDs, user stories, personas, and backlog tasks")
def repo_with_lineage(bdd_story_env: dict[str, Any]):
    root = bdd_story_env["root"]
    # Initialize already created docs/project
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0006.md").write_text(
        "---\n"
        "id: '0006'\n"
        "title: Autonomous SDLC Orchestrator\n"
        "status: Accepted\n"
        "target_persona: Jordan (The AI-Native Engineering Lead)\n"
        "component: core\n"
        "---\n"
        "# PRD-0006 — Autonomous SDLC Orchestrator\n",
        encoding="utf-8",
    )

    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0001-initial-story.md").write_text(
        "---\n"
        "id: '0001'\n"
        "title: Initial User Story\n"
        "status: Accepted\n"
        "persona: Jordan (The AI-Native Engineering Lead)\n"
        "target_bc: core\n"
        "feature: FEAT-CORE-01\n"
        "governing_prd: PRD-0006\n"
        "scenarios:\n"
        "  - Workflow execution\n"
        "---\n"
        "# US-0001 — Initial User Story\n",
        encoding="utf-8",
    )

    backlog_dir = root / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    (backlog_dir / "0001-implement-initial-feature.md").write_text(
        "---\n"
        "id: '0001'\n"
        "title: Implement Initial Feature\n"
        "status: Refined\n"
        "target_bc: core\n"
        "governing_prds:\n"
        "  - PRD-0006\n"
        "governing_stories:\n"
        "  - US-0001\n"
        "governing_adrs: []\n"
        "dependencies: []\n"
        "---\n"
        "# TASK-0001: Implement Initial Feature\n",
        encoding="utf-8",
    )


@then("unbroken bidirectional lineage is reported across Personas, PRDs, Stories, Tasks, and Commits")
def verify_trace_lineage(bdd_story_env: dict[str, Any]):
    root = bdd_story_env["root"]
    res = bdd_story_env["last_res"]
    assert res.returncode == 0, f"Trace failed: {res.stderr}\n{res.stdout}"
    assert "SpecOps User Story Traceability Audit" in res.stdout
    assert "Traceability Invariant Met" in res.stdout

    # Also test json format through public CLI frontdoor
    res_json = _run_cli(root, ["story", "trace", "--json"])
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["is_clean"] is True
    assert data["total_stories"] >= 1
    assert data["covered_stories"] >= 1


@then("broken references or orphaned items are flagged.")
def verify_broken_references_flagged(bdd_story_env: dict[str, Any]):
    root = bdd_story_env["root"]
    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    # Introduce an orphaned story referencing non-existent PRD and unknown persona
    (stories_dir / "us-0999-orphan.md").write_text(
        "---\n"
        "id: '0999'\n"
        "title: Orphaned Story\n"
        "status: Accepted\n"
        "persona: UnknownPersona\n"
        "target_bc: core\n"
        "feature: FEAT-ORPH-01\n"
        "governing_prd: PRD-9999\n"
        "---\n"
        "# US-0999 — Orphaned Story\n",
        encoding="utf-8",
    )

    res = _run_cli(root, ["story", "trace"])
    assert res.returncode == 1
    assert "Orphaned Stories" in res.stdout or "Broken References" in res.stdout

    res_json = _run_cli(root, ["story", "trace", "--json"])
    assert res_json.returncode == 1
    data = json.loads(res_json.stdout)
    assert data["is_clean"] is False
    assert len(data["orphaned_stories"]) >= 1
