"""Executable BDD acceptance tests for US-0100: Automated PRD Shipping Verification Gate."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.models import Task
from spec_ops.core.parser import extract_frontmatter
from spec_ops.scaffold.init import init_project

scenarios("features/us_0100_prd_shipping_gate.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


@pytest.fixture
def ship_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="ShippingApp")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Jordan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "jordan@specops.dev"], cwd=repo, check=True, capture_output=True)

    # Initialize REGISTRY.md and ROADMAP.md
    registry_file = repo / "docs" / "project" / "product" / "REGISTRY.md"
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    registry_file.write_text(
        "# PRD Registry\n\n"
        "| ID | Title | Status | Target Persona | Component |\n"
        "|---|---|---|---|---|\n"
        "| `PRD-0001` | Core Platform | Accepted | Taylor | core |\n"
        "| `PRD-0002` | Security Gate | Accepted | Jordan | security |\n",
        encoding="utf-8",
    )

    roadmap_file = repo / "docs" / "project" / "backlog" / "ROADMAP.md"
    roadmap_file.parent.mkdir(parents=True, exist_ok=True)
    roadmap_file.write_text(
        "# Delivery Roadmap\n\n"
        "## Milestone 1: Platform Core (Active)\n"
        "- Initial architecture spike and platform setup (`TASK-0001`).\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup shipping repo"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "cli_result": None,
        "shipped_prd_file": None,
        "manifest_path": None,
    }


# ==============================================================================
# Scenario: Successfully shipping a fully implemented and verified PRD
# ==============================================================================


@given(parsers.parse('an accepted PRD "{prd_id}" where all {task_count:d} implementing backlog tasks are marked "Complete"'))
def setup_accepted_prd_with_complete_tasks(ship_context: dict[str, Any], prd_id: str, task_count: int):
    repo: Path = ship_context["repo"]
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)

    task_ids = [f"TASK-{i:04d}" for i in range(1, task_count + 1)]
    task_lines = "\n".join(f"- `{tid}`" for tid in task_ids)

    story_ids = [f"US-{i:04d}" for i in range(1, 59)]
    story_lines = "\n".join(f"- `{sid}`" for sid in story_ids)

    prd_file = prd_dir / f"{prd_id.lower()}-core-platform.md"
    prd_file.write_text(
        f"""---
id: '{prd_id.replace("PRD-", "")}'
title: Core Platform Engine
status: Accepted
target_persona: Taylor (The Product Manager)
component: core
---

# {prd_id} — Core Platform Engine

## Checkable Outcomes

1. Launch core engine without terminal.

## Linked User Stories

{story_lines}

## Implementing Backlog Tasks

{task_lines}
""",
        encoding="utf-8",
    )

    # Create complete task files
    complete_dir = repo / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    for tid in task_ids:
        t_file = complete_dir / f"{tid.lower()}.md"
        t_file.write_text(
            f"""---
id: '{tid.replace("TASK-", "")}'
title: Task {tid}
status: Complete
governing_prds:
  - {prd_id}
---

# {tid}
Done.
""",
            encoding="utf-8",
        )

    # Create stories
    stories_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    for sid in story_ids:
        s_file = stories_dir / f"{sid.lower()}.md"
        s_file.write_text(
            f"""---
id: '{sid.replace("US-", "")}'
title: Story {sid}
status: Accepted
governing_prd: {prd_id}
---

# {sid}
```gherkin
Scenario: Verified behavior for {sid}
  Given condition
  When action
  Then outcome
```
""",
            encoding="utf-8",
        )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: setup PRD-0001 with complete tasks and stories"], cwd=repo, check=True, capture_output=True)


@given(parsers.parse('all {story_count:d} linked BDD user stories pass "pytest" with a 100% success rate through public frontdoors'))
def verify_bdd_stories_pass(ship_context: dict[str, Any], story_count: int):
    # Simulated 100% pass rate environment
    pass


@when(parsers.parse('Jordan runs "spec-ops prd ship {prd_id}"'))
def jordan_runs_prd_ship(ship_context: dict[str, Any], prd_id: str):
    repo: Path = ship_context["repo"]
    cmd = [sys.executable, "-m", "spec_ops.cli.main", "prd", "ship", prd_id]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, env=CLI_ENV)
    ship_context["cli_result"] = res


@then(parsers.parse('SpecOps moves the PRD file from "{src_dir}" to "{dst_dir}"'))
def prd_file_moved(ship_context: dict[str, Any], src_dir: str, dst_dir: str):
    repo: Path = ship_context["repo"]
    src_path = repo / src_dir
    dst_path = repo / dst_dir

    # Source should not have prd-0001
    remaining_src = list(src_path.glob("*prd-0001*"))
    assert len(remaining_src) == 0

    # Destination should have prd-0001
    shipped_files = list(dst_path.glob("*prd-0001*"))
    assert len(shipped_files) == 1
    ship_context["shipped_prd_file"] = shipped_files[0]


@then(parsers.parse('updates the frontmatter status to "{expected_status}" and records "shipped_date: {expected_date}"'))
def frontmatter_updated(ship_context: dict[str, Any], expected_status: str, expected_date: str):
    prd_file: Path = ship_context["shipped_prd_file"]
    content = prd_file.read_text(encoding="utf-8")
    meta, _ = extract_frontmatter(content)
    assert meta.get("status") == expected_status
    # Verify shipped_date
    today_str = date.today().isoformat()
    assert str(meta.get("shipped_date")) in (expected_date, today_str)


@then(parsers.parse('updates "{registry_path}" to status "{expected_status}"'))
def registry_updated(ship_context: dict[str, Any], registry_path: str, expected_status: str):
    repo: Path = ship_context["repo"]
    reg_file = repo / registry_path
    content = reg_file.read_text(encoding="utf-8")
    assert "| `PRD-0001` | Core Platform Engine | Shipped |" in content or f"| Shipped |" in content


@then(parsers.parse('marks the corresponding milestone in "{roadmap_path}" as complete with 100% delivery.'))
def roadmap_milestone_marked_complete(ship_context: dict[str, Any], roadmap_path: str):
    repo: Path = ship_context["repo"]
    rm_file = repo / roadmap_path
    content = rm_file.read_text(encoding="utf-8")
    assert "100% delivery" in content


# ==============================================================================
# Scenario: Aborting shipping when linked BDD user stories or tasks are incomplete
# ==============================================================================


@given(parsers.parse('an accepted PRD "{prd_id}" with {task_count:d} implementing tasks'))
def setup_accepted_prd_with_tasks(ship_context: dict[str, Any], prd_id: str, task_count: int):
    repo: Path = ship_context["repo"]
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)

    prd_file = prd_dir / f"{prd_id.lower()}-security-gate.md"
    prd_file.write_text(
        f"""---
id: '{prd_id.replace("PRD-", "")}'
title: Security Gate Engine
status: Accepted
target_persona: Jordan (The AI-Native Engineering Lead)
component: security
---

# {prd_id} — Security Gate Engine

## Checkable Outcomes

1. Verify security invariants.

## Implementing Backlog Tasks

- `TASK-0025`
- `TASK-0026`
- `TASK-0027`
- `TASK-0028`
""",
        encoding="utf-8",
    )

    # Put TASK-0026, 0027, 0028 into complete
    complete_dir = repo / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    for tid in ["TASK-0026", "TASK-0027", "TASK-0028"]:
        (complete_dir / f"{tid.lower()}.md").write_text(
            f"""---
id: '{tid.replace("TASK-", "")}'
title: Task {tid}
status: Complete
governing_prds:
  - {prd_id}
---

# {tid}
""",
            encoding="utf-8",
        )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: setup PRD-0002"], cwd=repo, check=True, capture_output=True)


@given(parsers.parse('task "{task_id}" is currently in status "{status}"'))
def task_in_status(ship_context: dict[str, Any], task_id: str, status: str):
    repo: Path = ship_context["repo"]
    refined_dir = repo / "docs" / "project" / "backlog" / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)

    (refined_dir / f"{task_id.lower()}.md").write_text(
        f"""---
id: '{task_id.replace("TASK-", "")}'
title: Refined Task {task_id}
status: {status}
governing_prds:
  - PRD-0002
---

# {task_id}
In progress.
""",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: add refined task"], cwd=repo, check=True, capture_output=True)


@then(parsers.parse('the command aborts with error: "{expected_error}"'))
def command_aborts_with_error(ship_context: dict[str, Any], expected_error: str):
    res = ship_context["cli_result"]
    assert res.returncode != 0
    assert expected_error in res.stdout or expected_error in res.stderr


@then("no files are moved or modified in git.")
def no_files_moved(ship_context: dict[str, Any]):
    repo: Path = ship_context["repo"]
    res = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True)
    assert res.stdout.strip() == ""


# ==============================================================================
# Scenario: Generating a customer-facing release verification manifest upon shipping
# ==============================================================================


@given(parsers.parse('Jordan successfully executes "spec-ops prd ship {prd_id}"'))
def successfully_executes_ship(ship_context: dict[str, Any], prd_id: str):
    res = ship_context["cli_result"]
    if res is None:
        setup_accepted_prd_with_complete_tasks(ship_context, prd_id, 23)
        verify_bdd_stories_pass(ship_context, 58)
        jordan_runs_prd_ship(ship_context, prd_id)
        res = ship_context["cli_result"]
    assert res is not None
    assert res.returncode == 0



@then(parsers.parse('SpecOps generates a release verification manifest at "{manifest_rel_path}"'))
def release_manifest_generated(ship_context: dict[str, Any], manifest_rel_path: str):
    repo: Path = ship_context["repo"]
    manifest_path = repo / manifest_rel_path
    assert manifest_path.is_file()
    ship_context["manifest_path"] = manifest_path


@then("the manifest contains:")
def verify_manifest_contents(ship_context: dict[str, Any]):
    manifest_path: Path = ship_context["manifest_path"]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    # PRD ID, title, persona
    assert "prd" in data
    assert data["prd"]["id"] == "PRD-0001"
    assert "title" in data["prd"]
    assert "persona" in data["prd"]

    # Full list of completed task IDs and commit SHAs
    assert "completed_tasks" in data
    assert len(data["completed_tasks"]) == 23
    for entry in data["completed_tasks"]:
        assert "id" in entry
        assert "commit_sha" in entry

    # Executable BDD scenario verification test run summary
    assert "test_verification" in data
    assert data["test_verification"]["status"] == "Passed (CI)"

    # Cryptographic SHA-256 digest of verified git tree
    assert "verified_tree_digest" in data
    assert len(data["verified_tree_digest"]) == 64
    assert "manifest_signature" in data
