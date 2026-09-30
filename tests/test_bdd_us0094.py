"""Executable BDD step definitions for US-0094: Checkable Outcome-to-BDD Decomposition."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.parser import extract_frontmatter
from spec_ops.scaffold.init import init_project

scenarios("features/us_0094_outcome_decomposition.feature")


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
# US-0094 Steps
# ---------------------------------------------------------------------------


@given(
    parsers.parse(
        'an accepted PRD "{prd_id}" with 3 distinct checkable outcomes in "{file_path}":'
    )
)
def accepted_prd_with_3_outcomes(bdd_context: dict[str, Any], prd_id: str, file_path: str):
    root = bdd_context["root"]
    full_path = root / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    content = f"""---
id: '{prd_id.replace("PRD-", "")}'
title: Telemetry and Observability Engine
status: Accepted
created: 2026-09-29
target_persona: Jordan
component: telemetry
---

# {prd_id} — Telemetry and Observability Engine

## Who this is for
- **Jordan**: Engineering lead.

## What the person cannot do today
- Cannot monitor telemetry metrics in real time.

## What good looks like
1. Real-time metric streaming.

## What this does not do
- Does not replace external APM agents.

## Checkable Outcomes

1. CLI emits JSON metrics matching telemetry schema when run with --json
2. Heartbeat agent transmits ping payload to visualizer every 5 seconds
3. Disconnected agents trigger stale warning alert within 15 seconds
"""
    full_path.write_text(content, encoding="utf-8")
    bdd_context["prd_file"] = full_path


@when(parsers.parse('{persona} runs "{cmd}"'))
def run_named_command(bdd_context: dict[str, Any], persona: str, cmd: str):
    root = bdd_context["root"]
    parts = cmd.split()
    assert parts[0] == "spec-ops"
    res = _run_cli(root, parts[1:])
    bdd_context["res"] = res


@then(parsers.parse("SpecOps parses the {count:d} checkable outcomes"))
def specops_parses_checkable_outcomes(bdd_context: dict[str, Any], count: int):
    res = bdd_context["res"]
    assert res.returncode == 0
    assert f"into {count} story" in res.stdout or f"{count} task" in res.stdout


@then(parsers.parse('generates {count:d} distinct BDD user story files under "{dir_path}"'))
def generates_distinct_stories(bdd_context: dict[str, Any], count: int, dir_path: str):
    root = bdd_context["root"]
    target_dir = root / dir_path
    story_files = list(target_dir.glob("*.md"))
    assert len(story_files) == count


@then(
    parsers.parse(
        'each user story frontmatter sets "governing_prd: {prd_id}" and maps the specific outcome ID'
    )
)
def verify_story_frontmatter(bdd_context: dict[str, Any], prd_id: str):
    root = bdd_context["root"]
    story_files = list((root / "docs" / "project" / "user_stories" / "accepted").glob("*.md"))
    assert len(story_files) > 0
    for sf in story_files:
        meta, _ = extract_frontmatter(sf.read_text(encoding="utf-8"))
        assert meta.get("governing_prd") == prd_id
        assert meta.get("outcome_id") is not None


@then("each user story contains an executable Gherkin skeleton reflecting the outcome behavior.")
def verify_story_gherkin(bdd_context: dict[str, Any]):
    root = bdd_context["root"]
    story_files = list((root / "docs" / "project" / "user_stories" / "accepted").glob("*.md"))
    for sf in story_files:
        content = sf.read_text(encoding="utf-8")
        assert "```gherkin" in content
        assert "Scenario:" in content
        assert "Given" in content
        assert "When" in content
        assert "Then" in content


@given(parsers.parse('an accepted PRD "{prd_id}" containing a subjective outcome "{outcome_text}"'))
def accepted_prd_subjective(bdd_context: dict[str, Any], prd_id: str, outcome_text: str):
    root = bdd_context["root"]
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    clean_id = prd_id.replace("PRD-", "")
    prd_file = prd_dir / f"prd-{clean_id}-performance.md"
    content = f"""---
id: '{clean_id}'
title: Performance Optimization
status: Accepted
created: 2026-09-29
target_persona: Jordan
component: core
---

# {prd_id} — Performance Optimization

## Who this is for
- **Jordan**: Engineering lead.

## What the person cannot do today
- System is perceived as sluggish.

## What good looks like
1. High responsiveness.

## What this does not do
- Does not change network protocols.

## Checkable Outcomes

1. {outcome_text}
"""
    prd_file.write_text(content, encoding="utf-8")


@then(parsers.parse("the command exits with exit code {code:d}"))
def verify_exit_code(bdd_context: dict[str, Any], code: int):
    res = bdd_context["res"]
    assert res.returncode == code


@then(parsers.parse('outputs a falsifiability failure: "{expected_msg}"'))
def verify_falsifiability_failure(bdd_context: dict[str, Any], expected_msg: str):
    res = bdd_context["res"]
    combined = res.stdout + res.stderr
    assert expected_msg in combined


@then("no user stories or backlog tasks are generated until the outcome is corrected.")
def verify_no_stories_or_tasks_generated(bdd_context: dict[str, Any]):
    root = bdd_context["root"]
    stories = list((root / "docs" / "project" / "user_stories" / "accepted").glob("*.md"))
    proposed_tasks = list((root / "docs" / "project" / "backlog" / "proposed").glob("*.md"))
    assert len(stories) == 0
    assert len(proposed_tasks) == 0


@given(
    parsers.parse(
        'the successful outcome-driven decomposition of "{prd_id}" into stories "{s1}", "{s2}", and "{s3}"'
    )
)
def setup_successful_outcome_decomposition(
    bdd_context: dict[str, Any], prd_id: str, s1: str, s2: str, s3: str
):
    accepted_prd_with_3_outcomes(
        bdd_context, prd_id, "docs/project/product/accepted/prd-0002-telemetry.md"
    )
    root = bdd_context["root"]
    target_num = int(s1.replace("US-", ""))
    prev_num = target_num - 1
    if prev_num > 0:
        stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
        stories_dir.mkdir(parents=True, exist_ok=True)
        (stories_dir / f"us-{prev_num:04d}-placeholder.md").write_text(
            f"---\nid: '{prev_num:04d}'\ntitle: Placeholder\nstatus: Accepted\n---\n",
            encoding="utf-8",
        )
    res = _run_cli(root, ["prd", "decompose", prd_id, "--by-outcomes"])
    assert res.returncode == 0


@when(parsers.parse('{persona} inspects "{file_path}"'))
def inspect_file(bdd_context: dict[str, Any], persona: str, file_path: str):
    root = bdd_context["root"]
    p = root / file_path
    assert p.is_file()
    bdd_context["current_file_content"] = p.read_text(encoding="utf-8")


@then(
    parsers.parse(
        'the "## Linked User Stories" section contains references to "{s1}", "{s2}", and "{s3}"'
    )
)
def verify_linked_user_stories(bdd_context: dict[str, Any], s1: str, s2: str, s3: str):
    content = bdd_context["current_file_content"]
    assert s1 in content
    assert s2 in content
    assert s3 in content


@then(
    'the generated vertical slice tasks in "docs/project/backlog/proposed/" cite their governing stories in "governing_stories".'
)
def verify_tasks_cite_governing_stories(bdd_context: dict[str, Any]):
    root = bdd_context["root"]
    tasks = list((root / "docs" / "project" / "backlog" / "proposed").glob("*.md"))
    assert len(tasks) > 0
    for tf in tasks:
        meta, _ = extract_frontmatter(tf.read_text(encoding="utf-8"))
        gov_stories = meta.get("governing_stories", [])
        assert len(gov_stories) > 0
