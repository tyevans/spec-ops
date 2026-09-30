"""BDD tests for US-0039: Ergonomic Human Task and Bug Authoring with Definition of Ready Scaffolding."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.parser import parse_task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0039_task_authoring.feature")


@pytest.fixture
def bdd_us39_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(target_dir=repo, name="AuthoringTest")

    return {
        "repo": repo,
        "last_res": None,
        "output": "",
        "created_task_path": None,
    }


# --- Scenario 1: Scaffolding a new proposed task via CLI flags ---


@given(parsers.parse('a clean repository with accepted PRD "{prd_id}" and user story "{story_id}"'))
def clean_repo_with_prd_and_story(bdd_us39_context: dict[str, Any], prd_id: str, story_id: str):
    repo = bdd_us39_context["repo"]
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "0001-visualizer-redesign.md").write_text(
        f"""---
id: '{prd_id.replace("PRD-", "")}'
title: Visualizer Redesign
status: Accepted
target_persona: Riley (The Human IC Developer)
---

# {prd_id} — Visualizer Redesign
""",
        encoding="utf-8",
    )

    story_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / "us-0002-visualizer-drawer.md").write_text(
        f"""---
id: '{story_id.replace("US-", "")}'
title: Visualizer Drawer
status: Accepted
governing_prd: {prd_id}
---

# {story_id} — Visualizer Drawer
""",
        encoding="utf-8",
    )


@when(parsers.parse('the engineer executes "{command_str}"'))
def engineer_executes_command(bdd_us39_context: dict[str, Any], command_str: str):
    repo = bdd_us39_context["repo"]
    cmd_parts = shlex.split(command_str)
    if cmd_parts[0] == "spec-ops":
        cmd_args = [sys.executable, "-m", "spec_ops.cli.main", *cmd_parts[1:]]
    else:
        cmd_args = cmd_parts

    res = subprocess.run(cmd_args, cwd=repo, capture_output=True, text=True)
    bdd_us39_context["last_res"] = res
    bdd_us39_context["output"] = res.stdout + ("\n" + res.stderr if res.stderr else "")


@then(parsers.parse('a new task file "{expected_glob}" is generated'))
def verify_task_file_generated(bdd_us39_context: dict[str, Any], expected_glob: str):
    repo = bdd_us39_context["repo"]
    pattern = expected_glob.split("/")[-1].replace("XXXX-", "*")
    folder = repo / "docs" / "project" / "backlog" / "proposed"
    matches = list(folder.glob(pattern))
    assert len(matches) > 0, f"No matching task file found for pattern {pattern} in {folder}"
    bdd_us39_context["created_task_path"] = matches[0]


@then("the file contains valid YAML frontmatter with canonical ID, title, target_bc, governing_prds, and governing_stories")
def verify_task_frontmatter(bdd_us39_context: dict[str, Any]):
    task_file: Path = bdd_us39_context["created_task_path"]
    assert task_file.is_file()
    task = parse_task(task_file)

    assert task.id != ""
    assert task.canonical_id.startswith("TASK-")
    assert task.title == "Extract Visualizer Drawer Script"
    assert task.target_bc == "visualizer"
    assert "PRD-0001" in task.governing_prds
    assert "US-0002" in task.governing_stories
    assert task.status == "Proposed"


@then(parsers.parse('"{priority_path}" is updated with the newly proposed task.'))
def verify_priority_updated(bdd_us39_context: dict[str, Any], priority_path: str):
    repo = bdd_us39_context["repo"]
    priority_file = repo / priority_path
    assert priority_file.is_file()
    content = priority_file.read_text(encoding="utf-8")
    task_file: Path = bdd_us39_context["created_task_path"]
    task = parse_task(task_file)
    assert task.canonical_id in content
    assert f"proposed/{task_file.name}" in content


# --- Scenario 2: Definition of Ready (DoR) validation when promoting to refined ---


@given(parsers.parse('a task file in "{folder_path}" missing governing ADRs and BDD user stories'))
def task_missing_adrs_and_stories(bdd_us39_context: dict[str, Any], folder_path: str):
    repo = bdd_us39_context["repo"]
    proposed_dir = repo / folder_path
    proposed_dir.mkdir(parents=True, exist_ok=True)

    # Ensure accepted PRD exists
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "0001-prd.md").write_text(
        "---\nid: '0001'\ntitle: Foundation\nstatus: Accepted\n---\n# PRD-0001\n",
        encoding="utf-8",
    )

    task_file = proposed_dir / "0025-legacy-migration.md"
    task_file.write_text(
        """---
id: '0025'
title: Legacy Migration
status: Proposed
governing_prds:
- PRD-0001
target_bc: worker
---

# TASK-0025: Legacy Migration
""",
        encoding="utf-8",
    )

    priority_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    priority_content = priority_file.read_text(encoding="utf-8")
    entry = "- **TASK-0025 (Proposed)**: [`0025-legacy-migration`](proposed/0025-legacy-migration.md)"
    if entry not in priority_content:
        priority_file.write_text(priority_content.strip() + "\n" + entry + "\n", encoding="utf-8")


@when(parsers.parse('the engineer attempts to promote the task to "{stage}" via "{command_str}"'))
def engineer_promotes_task(bdd_us39_context: dict[str, Any], stage: str, command_str: str):
    engineer_executes_command(bdd_us39_context, command_str)


@then("the command rejects the transition with clear DoR violation errors:")
def verify_dor_rejection_errors(bdd_us39_context: dict[str, Any]):
    res = bdd_us39_context["last_res"]
    output = bdd_us39_context["output"]
    assert res.returncode != 0
    assert "Missing governing ADRs: task must link at least 1 accepted ADR" in output
    assert "Missing governing story: task must trace back to an accepted BDD user story" in output


@then(parsers.parse('the task remains in "{folder_name}" until the criteria are satisfied.'))
def verify_task_remains_in_folder(bdd_us39_context: dict[str, Any], folder_name: str):
    repo = bdd_us39_context["repo"]
    proposed_file = repo / "docs" / "project" / "backlog" / folder_name / "0025-legacy-migration.md"
    refined_file = repo / "docs" / "project" / "backlog" / "refined" / "0025-legacy-migration.md"
    assert proposed_file.is_file()
    assert not refined_file.exists()
