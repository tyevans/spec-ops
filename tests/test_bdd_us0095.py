"""BDD step definitions for US-0095: Continuous PRD Outcome Coverage Audit."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0095_prd_outcome_audit.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="AuditBDD")
    return {
        "root": tmp_path,
        "res": None,
        "outcomes": [],
    }


def _run_cli(root: Path, cmd_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *cmd_args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@given(parsers.parse('an accepted PRD "{prd_id}" with {count:d} checkable outcomes'))
def accepted_prd_with_n_outcomes(bdd_context: dict[str, Any], prd_id: str, count: int):
    root = bdd_context["root"]
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)

    outcomes = [f"Checkable behavioral requirement number {i}" for i in range(1, count + 1)]
    bdd_context["outcomes"] = outcomes
    bdd_context["prd_id"] = prd_id

    outcomes_md = "\n".join(f"{i}. {ot}" for i, ot in enumerate(outcomes, start=1))
    clean_num = prd_id.replace("PRD-", "")
    content = f"""---
id: '{clean_num}'
title: Core Verification PRD
status: Accepted
created: 2026-09-29
target_persona: Taylor
component: prd
---

# {prd_id} — Core Verification PRD

## Who this is for
- **Taylor**: Product manager.

## What the person cannot do today
- Cannot automatically verify PRD outcomes.

## What good looks like
1. Continuous outcome coverage auditing.

## What this does not do
- Does not replace manual exploratory testing.

## Checkable Outcomes

{outcomes_md}
"""
    (prd_dir / f"prd-{clean_num}-core-verification.md").write_text(content, encoding="utf-8")


@given(parsers.parse('every checkable outcome is mapped to at least one user story in "{dir_path}"'))
def every_outcome_mapped_to_story(bdd_context: dict[str, Any], dir_path: str):
    root = bdd_context["root"]
    stories_dir = root / dir_path
    stories_dir.mkdir(parents=True, exist_ok=True)
    prd_id = bdd_context["prd_id"]
    outcomes = bdd_context["outcomes"]

    for i, ot in enumerate(outcomes, start=1):
        s_content = f"""---
id: '{i:04d}'
title: "{ot}"
status: Accepted
created: 2026-09-29
persona: Taylor
governing_prd: {prd_id}
outcome_id: {i}
---

# US-{i:04d} — {ot}

## User Story
**As a** product manager,
**I want** {ot},
**So that** business value is proven.

## Acceptance Criteria
```gherkin
Scenario: Verify outcome {i}
Given the environment is configured
When the action is triggered
Then observable outcome "{ot}" is validated.
```
"""
        (stories_dir / f"us-{i:04d}-story.md").write_text(s_content, encoding="utf-8")


@given(parsers.parse('every user story has implementing tasks in "{dir_path}"'))
def every_story_has_tasks(bdd_context: dict[str, Any], dir_path: str):
    root = bdd_context["root"]
    tasks_dir = root / dir_path / "proposed"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    prd_id = bdd_context["prd_id"]
    outcomes = bdd_context["outcomes"]

    for i, ot in enumerate(outcomes, start=1):
        t_content = f"""---
id: '{i:04d}'
title: "Implement {ot}"
status: Proposed
created: 2026-09-29
governing_prds:
  - {prd_id}
governing_stories:
  - US-{i:04d}
outcome_id: {i}
---

# TASK-{i:04d}: Implement {ot}
"""
        (tasks_dir / f"{i:04d}-task.md").write_text(t_content, encoding="utf-8")


@given(parsers.parse('an accepted PRD "{prd_id}" where outcome "{outcome_name}" has no linked user story'))
def prd_with_orphaned_outcome(bdd_context: dict[str, Any], prd_id: str, outcome_name: str):
    root = bdd_context["root"]
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    clean_num = prd_id.replace("PRD-", "")
    content = f"""---
id: '{clean_num}'
title: Multi-tenant Workspace PRD
status: Accepted
created: 2026-09-29
target_persona: Taylor
---

# {prd_id} — Multi-tenant Workspace PRD

## Checkable Outcomes

1. {outcome_name}
"""
    (prd_dir / f"prd-{clean_num}-workspace.md").write_text(content, encoding="utf-8")


@given(parsers.parse('a backlog task "{task_id}" with "governing_prds: [\'{prd_id}\']" but with no valid outcome reference or governing story'))
def unanchored_task_created(bdd_context: dict[str, Any], task_id: str, prd_id: str):
    root = bdd_context["root"]
    tasks_dir = root / "docs" / "project" / "backlog" / "proposed"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    clean_num = task_id.replace("TASK-", "")
    content = f"""---
id: '{clean_num}'
title: Rogue Unanchored Deliverable
status: Proposed
governing_prds:
  - {prd_id}
---

# {task_id}: Rogue Unanchored Deliverable
"""
    (tasks_dir / f"{clean_num}-unanchored.md").write_text(content, encoding="utf-8")


@when(parsers.parse('{persona} executes "{cmd}"'))
def execute_cli_command(bdd_context: dict[str, Any], persona: str, cmd: str):
    root = bdd_context["root"]
    parts = cmd.split()
    assert parts[0] == "spec-ops"
    res = _run_cli(root, parts[1:])
    bdd_context["res"] = res


@then(parsers.parse('the audit report displays "{expected_text}"'))
def verify_audit_displays(bdd_context: dict[str, Any], expected_text: str):
    res = bdd_context["res"]
    assert expected_text in res.stdout, f"Expected '{expected_text}' in stdout:\n{res.stdout}\nStderr:\n{res.stderr}"


@then(parsers.parse('outputs "{expected_text}"'))
def verify_outputs_text(bdd_context: dict[str, Any], expected_text: str):
    res = bdd_context["res"]
    assert expected_text in res.stdout, f"Expected '{expected_text}' in stdout:\n{res.stdout}"


@then(parsers.parse("the command exits with exit code {exit_code:d}."))
def verify_exit_code(bdd_context: dict[str, Any], exit_code: int):
    res = bdd_context["res"]
    assert res.returncode == exit_code, f"Expected exit code {exit_code}, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"


@then(parsers.parse("the audit report flags {prd_id} with a warning"))
def verify_flagged_with_warning(bdd_context: dict[str, Any], prd_id: str):
    res = bdd_context["res"]
    combined = res.stdout + res.stderr
    assert prd_id in combined
    assert "Orphaned" in combined or "Warning" in combined or "⚠️" in combined


@then(parsers.parse('displays "{expected_text}"'))
def verify_displays_text(bdd_context: dict[str, Any], expected_text: str):
    res = bdd_context["res"]
    assert expected_text in res.stdout, f"Expected '{expected_text}' in stdout:\n{res.stdout}"


@then(parsers.re(r'suggests "(?P<expected_text>[^"]+)"\.?'))
def verify_suggests_text(bdd_context: dict[str, Any], expected_text: str):
    res = bdd_context["res"]
    assert expected_text in res.stdout, f"Expected '{expected_text}' in stdout:\n{res.stdout}"


@then(parsers.parse('the audit output flags "{expected_text}"'))
def verify_flags_text(bdd_context: dict[str, Any], expected_text: str):
    res = bdd_context["res"]
    assert expected_text in res.stdout, f"Expected '{expected_text}' in stdout:\n{res.stdout}"


@then(parsers.parse('the audit summary marks buffer health as "{buffer_health}".'))
def verify_buffer_health(bdd_context: dict[str, Any], buffer_health: str):
    res = bdd_context["res"]
    assert buffer_health in res.stdout, f"Expected '{buffer_health}' in stdout:\n{res.stdout}"
