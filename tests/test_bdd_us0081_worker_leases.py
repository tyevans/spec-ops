"""Executable BDD scenarios for US-0081 / TASK-0166: Dynamic Worker Lease Heartbeat and Zombie Claim Auto-Reclaimer.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0012; PRD-0004; US-0081; TASK-0166.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any
import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.cli.parser import build_parser
from spec_ops.cli.worker_handler import handle_worker_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.parser import extract_frontmatter
from spec_ops.worker.lease_manager import WorkerLeaseManager

scenarios("features/us_0081_worker_leases.feature")


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    return {}


@given("a claimed task with an expired lease token and no active host process")
def step_given_expired_zombie_task(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)

    task_file = backlog_dir / "0001-zombie-task.md"
    task_file.write_text(
        """---
id: TASK-0001
title: Zombie Task
status: In-Progress
claimed_by: crashed-worker-99
claimed_at: 2026-01-01T00:00:00+00:00
heartbeat_at: 2026-01-01T00:00:00+00:00
---
# Zombie Task
""",
        encoding="utf-8",
    )

    # Register expired lease with a dead PID (e.g. 99999999)
    mgr = WorkerLeaseManager(tmp_path)
    mgr.create_lease(
        task_id="TASK-0001",
        worker_id="crashed-worker-99",
        pid=99999999,
        ttl_seconds=1,
    )
    # Fast forward expiration to the past
    lease = mgr.get_lease("TASK-0001")
    assert lease is not None
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
    lease.created_at = past
    lease.last_heartbeat = past
    lease.expires_at = past
    mgr._lease_file("TASK-0001").write_text(json.dumps(lease.to_dict()), encoding="utf-8")

    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)
    bdd_context["task_file"] = task_file
    bdd_context["mgr"] = mgr


@when("the worker lease manager executes claim reconciliation")
def step_when_reconcile_claims(
    bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    parser = build_parser()
    args = parser.parse_args(["worker", "lease", "--reclaim"])
    ret = handle_worker_command(args, bdd_context["config"])
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out
    bdd_context["stderr"] = captured.err


@then("the zombie lease is revoked")
def step_then_zombie_lease_revoked(bdd_context: dict[str, Any]) -> None:
    mgr: WorkerLeaseManager = bdd_context["mgr"]
    assert mgr.get_lease("TASK-0001") is None


@then("the task is safely restored to refined status for reallocation")
def step_then_task_restored_to_refined(bdd_context: dict[str, Any]) -> None:
    task_file: Path = bdd_context["task_file"]
    meta, _ = extract_frontmatter(task_file.read_text(encoding="utf-8"))
    assert meta["status"] == "Refined"
    assert not meta.get("claimed_by")


@then("the command terminates with exit code 0")
def step_then_exit_zero(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] == 0


@given("an actively running worker updating its lease heartbeat")
def step_given_active_worker_updating_heartbeat(
    bdd_context: dict[str, Any], tmp_path: Path
) -> None:
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)

    task_file = backlog_dir / "0002-active-task.md"
    task_file.write_text(
        """---
id: TASK-0002
title: Active Task
status: In-Progress
claimed_by: healthy-worker-1
---
# Active Task
""",
        encoding="utf-8",
    )

    # Use current active process PID
    current_pid = os.getpid()
    mgr = WorkerLeaseManager(tmp_path)
    mgr.create_lease(
        task_id="TASK-0002",
        worker_id="healthy-worker-1",
        pid=current_pid,
        ttl_seconds=600,
    )
    # Record fresh heartbeat
    mgr.record_heartbeat("TASK-0002")

    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)
    bdd_context["task_file"] = task_file
    bdd_context["mgr"] = mgr


@when("the lease manager evaluates active worker leases")
def step_when_evaluate_active_leases(
    bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    parser = build_parser()
    args = parser.parse_args(["worker", "lease", "--status"])
    ret = handle_worker_command(args, bdd_context["config"])
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out
    bdd_context["stderr"] = captured.err


@then("the active lease is confirmed valid and unexpired")
def step_then_lease_valid_and_unexpired(bdd_context: dict[str, Any]) -> None:
    mgr: WorkerLeaseManager = bdd_context["mgr"]
    lease = mgr.get_lease("TASK-0002")
    assert lease is not None
    is_valid, reason = mgr.evaluate_lease(lease)
    assert is_valid
    assert "Active" in reason
    assert "[ACTIVE]" in bdd_context["stdout"]


@then("the task claim remains actively held")
def step_then_task_claim_actively_held(bdd_context: dict[str, Any]) -> None:
    task_file: Path = bdd_context["task_file"]
    meta, _ = extract_frontmatter(task_file.read_text(encoding="utf-8"))
    assert meta["status"] == "In-Progress"
    assert meta.get("claimed_by") == "healthy-worker-1"
