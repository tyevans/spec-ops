"""Executable BDD acceptance tests for US-0077: Stalled Claim Reclamation.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0009; PRD-0005; US-0077.
Target Bounded Context: backlog. Frontdoor blackbox verification without private mocks.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.core.models import Task
from spec_ops.core.parser import extract_frontmatter, parse_task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0077_stalled_claim_reclamation.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops_cmd(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Frontdoor CLI invoker via subprocess (ADR-0003)."""
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


@pytest.fixture
def reclaim_repo(tmp_path: Path) -> Path:
    """Sets up a realistic test workspace with initialized backlog directories and priority index."""
    repo = tmp_path / "reclaim_workspace"
    init_project(repo, name="ReclaimTest")
    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    complete_dir = backlog_dir / "complete"
    refined_dir.mkdir(parents=True, exist_ok=True)
    complete_dir.mkdir(parents=True, exist_ok=True)
    return repo


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    return {}


@given('a task "TASK-0020" in "refined/" has status "In-Progress" and is claimed by "stalled-worker-01" with claim timestamp 5 hours ago')
def setup_stalled_task_0020(reclaim_repo: Path, bdd_ctx: dict[str, Any]):
    bdd_ctx["repo"] = reclaim_repo
    refined_dir = reclaim_repo / "docs" / "project" / "backlog" / "refined"
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    stalled_ts = (now - datetime.timedelta(hours=5)).isoformat()

    task_file = refined_dir / "0020-stalled-feature.md"
    task = Task(
        id="0020",
        title="Stalled Feature Implementation",
        status="In-Progress",
        claimed_by="stalled-worker-01",
        claimed_at=stalled_ts,
        target_bc="backlog",
        file_path=task_file,
    )
    write_task_file(task)
    bdd_ctx["task_file_0020"] = task_file

    pfile = reclaim_repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    pfile.write_text(
        "# Backlog Priority Index\n\n- **TASK-0020 (In-Progress)**: [`0020-stalled-feature`](refined/0020-stalled-feature.md)\n",
        encoding="utf-8",
    )


@when('the engineering lead runs "spec-ops queue reclaim-stalled --timeout-hours 4.0"')
def run_reclaim_command(bdd_ctx: dict[str, Any]):
    res = run_spec_ops_cmd(bdd_ctx["repo"], ["queue", "reclaim-stalled", "--timeout-hours", "4.0"])
    bdd_ctx["res"] = res


@then("the command output confirms 1 task claim was reclaimed")
def verify_one_reclaimed(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert res.returncode == 0, f"Command failed: {res.stderr}"
    assert "1" in res.stdout
    assert "TASK-0020" in res.stdout


@then('task "TASK-0020" claimed_by is reset to empty')
def verify_task_0020_claimed_by_empty(bdd_ctx: dict[str, Any]):
    task_file = bdd_ctx["task_file_0020"]
    parsed = parse_task(task_file)
    assert parsed.claimed_by == ""


@then('task "TASK-0020" status is restored to "Refined" in the task file and PRIORITY.md')
def verify_task_0020_status_refined(bdd_ctx: dict[str, Any]):
    task_file = bdd_ctx["task_file_0020"]
    parsed = parse_task(task_file)
    assert parsed.status == "Refined"

    pfile = bdd_ctx["repo"] / "docs" / "project" / "backlog" / "PRIORITY.md"
    content = pfile.read_text(encoding="utf-8")
    assert "TASK-0020 (Refined)" in content


@given('a task "TASK-0021" in "refined/" is claimed by "active-worker-02" with claim timestamp 6 hours ago and heartbeat timestamp 15 minutes ago')
def setup_active_task_with_heartbeat(reclaim_repo: Path, bdd_ctx: dict[str, Any]):
    bdd_ctx["repo"] = reclaim_repo
    refined_dir = reclaim_repo / "docs" / "project" / "backlog" / "refined"
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    claim_ts = (now - datetime.timedelta(hours=6)).isoformat()
    hb_ts = (now - datetime.timedelta(minutes=15)).isoformat()

    task_file = refined_dir / "0021-active-feature.md"
    task = Task(
        id="0021",
        title="Active Feature Implementation",
        status="In-Progress",
        claimed_by="active-worker-02",
        claimed_at=claim_ts,
        heartbeat_at=hb_ts,
        target_bc="backlog",
        file_path=task_file,
    )
    write_task_file(task)
    bdd_ctx["task_file_0021"] = task_file

    pfile = reclaim_repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    pfile.write_text(
        "# Backlog Priority Index\n\n- **TASK-0021 (In-Progress)**: [`0021-active-feature`](refined/0021-active-feature.md)\n",
        encoding="utf-8",
    )


@then("zero task claims are reclaimed")
def verify_zero_reclaimed(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert res.returncode == 0, f"Command failed: {res.stderr}"
    assert "Zero stalled worker claims detected" in res.stdout


@then('task "TASK-0021" remains claimed by "active-worker-02"')
def verify_task_0021_remains_claimed(bdd_ctx: dict[str, Any]):
    task_file = bdd_ctx["task_file_0021"]
    parsed = parse_task(task_file)
    assert parsed.claimed_by == "active-worker-02"
    assert parsed.status == "In-Progress"


@given('a task "TASK-0022" in "refined/" has status "In-Progress" and is claimed by "stalled-worker-03" with claim timestamp 8 hours ago')
def setup_stalled_task_0022(reclaim_repo: Path, bdd_ctx: dict[str, Any]):
    bdd_ctx["repo"] = reclaim_repo
    refined_dir = reclaim_repo / "docs" / "project" / "backlog" / "refined"
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    stalled_ts = (now - datetime.timedelta(hours=8)).isoformat()

    task_file = refined_dir / "0022-stalled-dryrun.md"
    task = Task(
        id="0022",
        title="Stalled Dry Run Feature",
        status="In-Progress",
        claimed_by="stalled-worker-03",
        claimed_at=stalled_ts,
        target_bc="backlog",
        file_path=task_file,
    )
    write_task_file(task)
    bdd_ctx["task_file_0022"] = task_file

    pfile = reclaim_repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    pfile.write_text(
        "# Backlog Priority Index\n\n- **TASK-0022 (In-Progress)**: [`0022-stalled-dryrun`](refined/0022-stalled-dryrun.md)\n",
        encoding="utf-8",
    )


@when('the engineering lead runs "spec-ops queue reclaim-stalled --dry-run --timeout-hours 4.0"')
def run_dry_run_command(bdd_ctx: dict[str, Any]):
    res = run_spec_ops_cmd(bdd_ctx["repo"], ["queue", "reclaim-stalled", "--dry-run", "--timeout-hours", "4.0"])
    bdd_ctx["res"] = res


@then('the command output previews reclamation of "TASK-0022"')
def verify_dry_run_preview(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert res.returncode == 0, f"Command failed: {res.stderr}"
    assert "DRY RUN" in res.stdout
    assert "TASK-0022" in res.stdout


@then('task "TASK-0022" remains claimed by "stalled-worker-03" on disk')
def verify_task_0022_unmodified_disk(bdd_ctx: dict[str, Any]):
    task_file = bdd_ctx["task_file_0022"]
    parsed = parse_task(task_file)
    assert parsed.claimed_by == "stalled-worker-03"
    assert parsed.status == "In-Progress"


@then('PRIORITY.md remains unmodified for "TASK-0022"')
def verify_priority_unmodified(bdd_ctx: dict[str, Any]):
    pfile = bdd_ctx["repo"] / "docs" / "project" / "backlog" / "PRIORITY.md"
    assert "TASK-0022 (In-Progress)" in pfile.read_text(encoding="utf-8")


@given('a task "TASK-0023" in "refined/" has status "In-Progress" and is claimed by "stalled-worker-04" with claim timestamp 5 hours ago')
def setup_stalled_task_0023(reclaim_repo: Path, bdd_ctx: dict[str, Any]):
    bdd_ctx["repo"] = reclaim_repo
    refined_dir = reclaim_repo / "docs" / "project" / "backlog" / "refined"
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    stalled_ts = (now - datetime.timedelta(hours=5)).isoformat()

    task_file = refined_dir / "0023-stalled-json.md"
    task = Task(
        id="0023",
        title="Stalled JSON Feature",
        status="In-Progress",
        claimed_by="stalled-worker-04",
        claimed_at=stalled_ts,
        target_bc="backlog",
        file_path=task_file,
    )
    write_task_file(task)
    bdd_ctx["task_file_0023"] = task_file

    pfile = reclaim_repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    pfile.write_text(
        "# Backlog Priority Index\n\n- **TASK-0023 (In-Progress)**: [`0023-stalled-json`](refined/0023-stalled-json.md)\n",
        encoding="utf-8",
    )


@when('the engineering lead runs "spec-ops queue reclaim-stalled --json --timeout-hours 4.0"')
def run_json_command(bdd_ctx: dict[str, Any]):
    res = run_spec_ops_cmd(bdd_ctx["repo"], ["queue", "reclaim-stalled", "--json", "--timeout-hours", "4.0"])
    bdd_ctx["res"] = res


@then('the output is valid JSON with reclaimed_count 1 containing "TASK-0023"')
def verify_json_output(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert res.returncode == 0, f"Command failed: {res.stderr}"
    data = json.loads(res.stdout)
    assert data["reclaimed_count"] == 1
    assert "TASK-0023" in data["reclaimed_ids"]
    assert len(data["reclaimed_tasks"]) == 1
    assert data["reclaimed_tasks"][0]["task_id"] == "TASK-0023"


@then("the JSON output includes audit_trail entries")
def verify_json_audit_trail(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    data = json.loads(res.stdout)
    assert "audit_trail" in data
    assert len(data["audit_trail"]) == 1
    assert "TASK-0023" in data["audit_trail"][0]
