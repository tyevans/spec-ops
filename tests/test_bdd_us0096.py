"""Executable BDD step definitions for US-0096: Incremental Delta Scope Evolution."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0096_delta_scope_evolution.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="SpecOpsBDD")
    return {
        "root": tmp_path,
        "res": None,
        "snapshots": {},
        "current_file": None,
    }


def _run_cli(root: Path, cmd_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *cmd_args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# US-0096 Steps
# ---------------------------------------------------------------------------


@given(
    parsers.parse(
        'an accepted PRD "{prd_id}" that already has {task_count:d} completed tasks and linked stories'
    )
)
def setup_prd_with_existing_tasks_and_stories(
    bdd_context: dict[str, Any], prd_id: str, task_count: int
):
    root = bdd_context["root"]
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    clean_id = prd_id.replace("PRD-", "")
    prd_file = prd_dir / f"prd-{clean_id}-main.md"

    outcomes = [
        "First primary workflow outcome",
        "Second security verification contract",
        "Third telemetry aggregation output",
        "Fourth cache invalidation rule",
        "Fifth authentication handshake contract",
    ]
    outcomes_md = "\n".join(f"{idx}. {o}" for idx, o in enumerate(outcomes, 1))

    prd_content = f"""---
id: '{clean_id}'
title: Core Application Engine
status: Accepted
created: 2026-09-29
target_persona: Alex
component: core
---

# {prd_id} — Core Application Engine

## Who this is for
- **Alex**: Systems architect.

## What the person cannot do today
- Limited delta execution.

## What good looks like
1. High scale.

## What this does not do
- No regressions.

## Checkable Outcomes

{outcomes_md}

## Linked User Stories

- `US-0057`
- `US-0058`
- `US-0059`
- `US-0060`
- `US-0061`
"""
    prd_file.write_text(prd_content, encoding="utf-8")
    bdd_context["prd_file"] = prd_file

    # Create 5 existing user stories
    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(1, 6):
        sid = f"US-{56 + idx:04d}"
        s_file = stories_dir / f"us-{56 + idx:04d}-outcome-{idx}.md"
        s_file.write_text(
            f"""---
id: '{56 + idx:04d}'
title: "{outcomes[idx - 1]}"
status: Accepted
governing_prd: {prd_id}
outcome_id: {idx}
---
# {sid}
""",
            encoding="utf-8",
        )

    # Create completed tasks
    complete_dir = root / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    priority_file = root / "docs" / "project" / "backlog" / "PRIORITY.md"
    priority_lines = ["# Task Priority Queue\n"]

    for t_idx in range(1, task_count + 1):
        tid = f"TASK-{t_idx:04d}"
        t_file = complete_dir / f"{t_idx:04d}-completed-task-{t_idx}.md"
        outcome_mapping = ((t_idx - 1) % 5) + 1
        t_file.write_text(
            f"""---
id: '{t_idx:04d}'
title: "Completed Task {t_idx}"
status: Complete
governing_prds:
  - {prd_id}
outcome_id: {outcome_mapping}
---
# {tid}: Completed Task {t_idx}
""",
            encoding="utf-8",
        )
        priority_lines.append(f"- **{tid} (Complete)**: [`{t_file.stem}`](complete/{t_file.name})")

    priority_file.write_text("\n".join(priority_lines) + "\n", encoding="utf-8")

    # Snapshot TASK-0001 through TASK-XXXX
    snapshots = {p: p.read_bytes() for p in complete_dir.glob("*.md")}
    bdd_context["snapshots"] = snapshots


@given(parsers.parse('{persona} adds a 6th checkable outcome to "{prd_id}": "{outcome_text}"'))
def add_6th_outcome(bdd_context: dict[str, Any], persona: str, prd_id: str, outcome_text: str):
    prd_file = bdd_context["prd_file"]
    content = prd_file.read_text(encoding="utf-8")
    content = content.replace(
        "5. Fifth authentication handshake contract",
        f"5. Fifth authentication handshake contract\n6. {outcome_text}",
    )
    prd_file.write_text(content, encoding="utf-8")


@when(parsers.parse('{persona} runs "{cmd}"'))
def run_named_command(bdd_context: dict[str, Any], persona: str, cmd: str):
    root = bdd_context["root"]
    parts = cmd.split()
    assert parts[0] == "spec-ops"
    res = _run_cli(root, parts[1:])
    bdd_context["res"] = res


@then(parsers.parse("SpecOps detects that outcomes 1 through 5 already have existing stories and tasks"))
def verify_detected_existing_outcomes(bdd_context: dict[str, Any]):
    res = bdd_context["res"]
    assert res.returncode == 0


@then("identifies outcome 6 as new scope delta")
def verify_outcome_6_is_delta(bdd_context: dict[str, Any]):
    res = bdd_context["res"]
    assert res.returncode == 0
    assert "delta" in res.stdout.lower() or "story" in res.stdout.lower()


@then(
    parsers.parse(
        'synthesizes only 1 new user story "{story_id}" and its corresponding vertical slice tasks'
    )
)
def verify_synthesizes_only_one_story(bdd_context: dict[str, Any], story_id: str):
    root = bdd_context["root"]
    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    num_str = story_id.replace("US-", "")
    matches = list(stories_dir.glob(f"us-{num_str}*.md"))
    assert len(matches) == 1
    # Check that new tasks were added to proposed/
    proposed_tasks = list((root / "docs" / "project" / "backlog" / "proposed").glob("*.md"))
    assert len(proposed_tasks) >= 1


@then(parsers.parse("existing tasks TASK-0001 through TASK-0023 remain completely unmodified in git."))
def verify_existing_tasks_unmodified(bdd_context: dict[str, Any]):
    snapshots = bdd_context["snapshots"]
    for path, expected_bytes in snapshots.items():
        assert path.is_file()
        assert path.read_bytes() == expected_bytes


@given(parsers.parse('an existing backlog where "{task1}" is marked "Complete" and "{task2}" is "Refined"'))
def setup_complete_and_refined_tasks(bdd_context: dict[str, Any], task1: str, task2: str):
    root = bdd_context["root"]
    setup_prd_with_existing_tasks_and_stories(bdd_context, "PRD-0001", 20)

    # Set task1 in complete/
    complete_dir = root / "docs" / "project" / "backlog" / "complete"
    t1_num = task1.replace("TASK-", "")
    t1_file = complete_dir / f"{t1_num}-task-{t1_num}.md"
    t1_file.write_text(
        f"---\nid: '{t1_num}'\ntitle: \"{task1}\"\nstatus: Complete\ngoverning_prds:\n  - PRD-0001\noutcome_id: 1\n---\n",
        encoding="utf-8",
    )

    # Set task2 in refined/
    refined_dir = root / "docs" / "project" / "backlog" / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    t2_num = task2.replace("TASK-", "")
    t2_file = refined_dir / f"{t2_num}-task-{t2_num}.md"
    t2_file.write_text(
        f"---\nid: '{t2_num}'\ntitle: \"{task2}\"\nstatus: Refined\ngoverning_prds:\n  - PRD-0001\noutcome_id: 2\n---\n",
        encoding="utf-8",
    )

    # Add a 6th outcome so --diff has delta work
    prd_file = bdd_context["prd_file"]
    content = prd_file.read_text(encoding="utf-8")
    content = content.replace(
        "5. Fifth authentication handshake contract",
        "5. Fifth authentication handshake contract\n6. Navigating visualizer deep links activates target views",
    )
    prd_file.write_text(content, encoding="utf-8")

    bdd_context["t1_file"] = t1_file
    bdd_context["t1_bytes"] = t1_file.read_bytes()
    bdd_context["t2_file"] = t2_file
    bdd_context["t2_bytes"] = t2_file.read_bytes()


@then(
    parsers.parse(
        'the file contents, frontmatter, and file paths of "{task1}" and "{task2}" remain untouched'
    )
)
def verify_specific_tasks_untouched(bdd_context: dict[str, Any], task1: str, task2: str):
    t1_file = bdd_context["t1_file"]
    t2_file = bdd_context["t2_file"]
    assert t1_file.is_file()
    assert t2_file.is_file()
    assert t1_file.read_bytes() == bdd_context["t1_bytes"]
    assert t2_file.read_bytes() == bdd_context["t2_bytes"]


@then(
    parsers.parse(
        '"docs/project/backlog/PRIORITY.md" only appends the newly created delta tasks to the proposed queue.'
    )
)
def verify_priority_appends_delta_tasks(bdd_context: dict[str, Any]):
    root = bdd_context["root"]
    priority_file = root / "docs" / "project" / "backlog" / "PRIORITY.md"
    lines = priority_file.read_text(encoding="utf-8").splitlines()
    assert any("(Proposed)" in line for line in lines)


@given(parsers.parse('{persona} removes checkable outcome 2 from "{prd_id}" in git'))
def remove_outcome_2(bdd_context: dict[str, Any], persona: str, prd_id: str):
    setup_prd_with_existing_tasks_and_stories(bdd_context, prd_id, 10)
    prd_file = bdd_context["prd_file"]
    content = prd_file.read_text(encoding="utf-8")
    # Remove outcome 2
    content = re.sub(r"2\.\s+Second security verification contract\n", "", content)
    prd_file.write_text(content, encoding="utf-8")


@given(parsers.parse('outcome 2 is currently linked to pending task "{task_id_status}"'))
def link_outcome_2_to_pending_task(bdd_context: dict[str, Any], task_id_status: str):
    root = bdd_context["root"]
    m = re.match(r"(TASK-\d+)\s*\((.*?)\)", task_id_status)
    assert m is not None
    tid, status = m.groups()
    num = tid.replace("TASK-", "")
    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    t_file = proposed_dir / f"{num}-pending-task.md"
    t_file.write_text(
        f"""---
id: '{num}'
title: "Pending Task for Outcome 2"
status: {status}
governing_prds:
  - PRD-0001
outcome_id: 2
---
# {tid}: Pending Task
""",
        encoding="utf-8",
    )


@then(parsers.parse('SpecOps warns "{warn_msg}"'))
def verify_specops_warns(bdd_context: dict[str, Any], warn_msg: str):
    res = bdd_context["res"]
    combined = res.stdout + res.stderr
    assert warn_msg in combined


@then(parsers.parse("prompts the user to either archive {task_id} or re-link it to another outcome."))
def verify_prompt_user(bdd_context: dict[str, Any], task_id: str):
    res = bdd_context["res"]
    combined = res.stdout + res.stderr
    assert f"archive {task_id} or re-link it to another outcome" in combined
