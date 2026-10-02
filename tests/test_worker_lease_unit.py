"""Comprehensive unit tests for spec_ops.worker.lease_manager to maximize mutant kill rate."""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import pytest

from spec_ops.cli.worker_handler import handle_worker_lease
from spec_ops.config.models import SpecOpsConfig
from spec_ops.worker.lease_manager import (
    WorkerLease,
    WorkerLeaseManager,
    is_pid_alive,
    parse_utc_timestamp,
)


def test_is_pid_alive():
    assert not is_pid_alive(0)
    assert not is_pid_alive(-1)
    assert is_pid_alive(os.getpid())
    # 99999999 is almost certainly not running on linux
    assert not is_pid_alive(99999999)


def test_parse_utc_timestamp():
    now = datetime.datetime.now(datetime.timezone.utc)
    # Already datetime
    assert parse_utc_timestamp(now) == now
    naive = datetime.datetime(2026, 1, 1, 12, 0, 0)
    assert parse_utc_timestamp(naive).tzinfo == datetime.timezone.utc

    # Numeric
    ts = 1767225600.0
    dt_num = parse_utc_timestamp(ts)
    assert dt_num.timestamp() == ts

    # String timestamp
    dt_str = parse_utc_timestamp("1767225600.0")
    assert dt_str.timestamp() == ts

    # ISO string
    iso = "2026-06-15T10:30:00+00:00"
    assert parse_utc_timestamp(iso).isoformat() == iso

    # Date string
    date_str = "2026-06-15"
    parsed_date = parse_utc_timestamp(date_str)
    assert parsed_date.year == 2026 and parsed_date.month == 6 and parsed_date.day == 15

    # Fallback to now
    fallback = parse_utc_timestamp("completely invalid text")
    assert isinstance(fallback, datetime.datetime)


def test_worker_lease_serialization():
    lease = WorkerLease(
        lease_token="abcdef123456",
        task_id="TASK-0042",
        worker_id="agent-007",
        pid=1234,
        created_at="2026-01-01T00:00:00+00:00",
        last_heartbeat="2026-01-01T00:05:00+00:00",
        expires_at="2026-01-01T00:10:00+00:00",
        ttl_seconds=300,
        metadata={"key": "val"},
    )
    d = lease.to_dict()
    assert d["task_id"] == "TASK-0042"
    assert d["metadata"] == {"key": "val"}

    copy_lease = WorkerLease.from_dict(d)
    assert copy_lease.lease_token == lease.lease_token
    assert copy_lease.ttl_seconds == 300
    assert copy_lease.metadata == {"key": "val"}


def test_lease_manager_lifecycle(tmp_path: Path):
    mgr = WorkerLeaseManager(tmp_path, default_ttl_seconds=120)

    # 1. Create lease
    lease = mgr.create_lease(
        task_id="42",
        worker_id="worker-alpha",
        pid=os.getpid(),
        ttl_seconds=200,
        metadata={"purpose": "testing"},
    )
    assert lease.task_id == "TASK-0042"
    assert lease.ttl_seconds == 200
    assert lease.metadata["purpose"] == "testing"

    # 2. Get lease
    fetched = mgr.get_lease("TASK-0042")
    assert fetched is not None
    assert fetched.lease_token == lease.lease_token

    # 3. Non-existent get
    assert mgr.get_lease("TASK-9999") is None

    # 4. List leases
    leases = mgr.list_leases()
    assert len(leases) == 1
    assert leases[0].task_id == "TASK-0042"

    # 5. Heartbeat with invalid token
    with pytest.raises(ValueError, match="Invalid lease token"):
        mgr.record_heartbeat("TASK-0042", lease_token="wrong_token")

    # 6. Heartbeat on non-existent task
    assert mgr.record_heartbeat("TASK-9999") is None

    # 7. Valid heartbeat
    t1 = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=10)
    updated = mgr.record_heartbeat("TASK-0042", lease_token=lease.lease_token, now=t1)
    assert updated is not None
    assert updated.last_heartbeat == t1.isoformat()

    # 8. Revoke lease
    assert mgr.revoke_lease("TASK-0042") is True
    assert mgr.revoke_lease("TASK-0042") is False
    assert mgr.get_lease("TASK-0042") is None


def test_evaluate_lease_scenarios(tmp_path: Path):
    mgr = WorkerLeaseManager(tmp_path)
    now = datetime.datetime.now(datetime.timezone.utc)
    past = (now - datetime.timedelta(minutes=10)).isoformat()
    future = (now + datetime.timedelta(minutes=10)).isoformat()

    # 1. Unexpired + living PID -> Active
    l1 = WorkerLease("tok1", "TASK-0001", "w1", os.getpid(), past, past, future)
    valid, reason = mgr.evaluate_lease(l1, now=now)
    assert valid is True
    assert "Active" in reason

    # 2. Unexpired + dead PID -> Zombie
    l2 = WorkerLease("tok2", "TASK-0002", "w2", 99999999, past, past, future)
    valid, reason = mgr.evaluate_lease(l2, now=now)
    assert valid is False
    assert "Zombie" in reason and "terminated" in reason

    # 3. Expired + dead PID -> Zombie
    l3 = WorkerLease("tok3", "TASK-0003", "w3", 99999999, past, past, past)
    valid, reason = mgr.evaluate_lease(l3, now=now)
    assert valid is False
    assert "Zombie" in reason and "expired" in reason

    # 4. Expired + live PID -> Expired (heartbeat timed out)
    l4 = WorkerLease("tok4", "TASK-0004", "w4", os.getpid(), past, past, past)
    valid, reason = mgr.evaluate_lease(l4, now=now)
    assert valid is False
    assert "Expired" in reason and "TTL lapsed" in reason


def test_reclaim_zombies_with_orphan_task(tmp_path: Path):
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    task1 = backlog_dir / "0005-orphan-task.md"
    task1.write_text(
        "---\nid: TASK-0005\ntitle: Orphan\nstatus: In-Progress\nclaimed_by: dead-agent\n---\n# Orphan\n",
        encoding="utf-8",
    )

    mgr = WorkerLeaseManager(tmp_path)
    # Reclaim without lease file
    reclaimed, active = mgr.reclaim_zombies(dry_run=True)
    assert len(reclaimed) == 1
    assert reclaimed[0]["task_id"] == "TASK-0005"
    assert len(active) == 0

    # Dry run should leave task claimed
    assert "claimed_by: dead-agent" in task1.read_text(encoding="utf-8")

    # Real run reclaims
    reclaimed, active = mgr.reclaim_zombies(dry_run=False)
    assert len(reclaimed) == 1
    assert "claimed_by: dead-agent" not in task1.read_text(encoding="utf-8")
    assert "status: Refined" in task1.read_text(encoding="utf-8")


def test_cli_worker_lease_subcommands(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    config = SpecOpsConfig(root_dir=tmp_path)
    mgr = WorkerLeaseManager(tmp_path)

    # 1. Heartbeat error when --task missing
    args_hb_err = argparse.Namespace(json=False, dry_run=False, ttl=300, heartbeat=True, task_id=None, reclaim=False, status=False)
    assert handle_worker_lease(args_hb_err, config) == 1
    assert "--task must be specified" in capsys.readouterr().err

    # 2. Heartbeat error when task lease missing
    args_hb_missing = argparse.Namespace(json=False, dry_run=False, ttl=300, heartbeat=True, task_id="TASK-0001", reclaim=False, status=False)
    assert handle_worker_lease(args_hb_missing, config) == 1
    assert "No active worker lease found" in capsys.readouterr().err

    # 3. Create lease and record heartbeat (text & json)
    mgr.create_lease("TASK-0001", pid=os.getpid())
    args_hb_ok = argparse.Namespace(json=False, dry_run=False, ttl=300, heartbeat=True, task_id="TASK-0001", reclaim=False, status=False)
    assert handle_worker_lease(args_hb_ok, config) == 0
    assert "Heartbeat recorded for TASK-0001" in capsys.readouterr().out

    args_hb_json = argparse.Namespace(json=True, dry_run=False, ttl=300, heartbeat=True, task_id="TASK-0001", reclaim=False, status=False)
    assert handle_worker_lease(args_hb_json, config) == 0
    out_json = json.loads(capsys.readouterr().out)
    assert out_json["task_id"] == "TASK-0001"

    # 4. Status inspection (text & json)
    args_status_text = argparse.Namespace(json=False, dry_run=False, ttl=300, heartbeat=False, task_id=None, reclaim=False, status=True)
    assert handle_worker_lease(args_status_text, config) == 0
    assert "[ACTIVE] TASK-0001" in capsys.readouterr().out

    args_status_json = argparse.Namespace(json=True, dry_run=False, ttl=300, heartbeat=False, task_id=None, reclaim=False, status=True)
    assert handle_worker_lease(args_status_json, config) == 0
    statuses = json.loads(capsys.readouterr().out)
    assert len(statuses) == 1

    # 5. Reclaim command (text & json)
    args_rec_text = argparse.Namespace(json=False, dry_run=False, ttl=300, heartbeat=False, task_id=None, reclaim=True, status=False)
    assert handle_worker_lease(args_rec_text, config) == 0
    out_rec = capsys.readouterr().out
    assert "Worker Lease Reconciliation" in out_rec

    args_rec_json = argparse.Namespace(json=True, dry_run=False, ttl=300, heartbeat=False, task_id=None, reclaim=True, status=False)
    assert handle_worker_lease(args_rec_json, config) == 0
    rec_obj = json.loads(capsys.readouterr().out)
    assert "reclaimed" in rec_obj
