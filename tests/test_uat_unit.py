"""Unit tests for UAT sign-off management, normalization, readiness harvesting, and health gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_ops.config.loader import load_config
from spec_ops.prd.uat import (
    check_uat_readiness,
    handle_check_uat,
    harvest_uat_readiness,
    load_uat_signoffs,
    normalize_reviewer_identity,
    normalize_uat_status,
    record_uat_signoff,
    save_uat_signoffs,
)
from spec_ops.scaffold.init import init_project


def test_normalize_reviewer_identity():
    # Valid RFC 2822
    assert normalize_reviewer_identity("Taylor <taylor@example.com>") == "Taylor <taylor@example.com>"
    # Plain name normalized to RFC 2822
    norm = normalize_reviewer_identity("Taylor")
    assert norm == "Taylor <taylor@specops.local>"
    # Multi-word name
    norm2 = normalize_reviewer_identity("Taylor Swift")
    assert norm2 == "Taylor Swift <taylor.swift@specops.local>"


def test_normalize_uat_status():
    assert normalize_uat_status("Approved (PM UAT)") == "Approved"
    assert normalize_uat_status("approved") == "Approved"
    assert normalize_uat_status("Rejected (PM)") == "Rejected"
    assert normalize_uat_status("pending") == "Pending"
    assert normalize_uat_status("other") == "Pending"


def test_load_and_save_uat_signoffs(tmp_path: Path):
    # Nonexistent
    empty = load_uat_signoffs(tmp_path)
    assert empty["signoffs"] == {}

    # Save
    data = {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": {
            "PRD-0001:1": {
                "outcome_id": "1",
                "prd_id": "PRD-0001",
                "status": "Approved",
                "reviewer": "Taylor <taylor@specops.local>",
                "timestamp": "2026-09-29T18:00:00Z",
                "notes": "Good",
            }
        },
    }
    p = save_uat_signoffs(tmp_path, data)
    assert p.is_file()

    # Load again
    loaded = load_uat_signoffs(tmp_path)
    assert "PRD-0001:1" in loaded["signoffs"]
    assert loaded["signoffs"]["PRD-0001:1"]["status"] == "Approved"


def test_record_uat_signoff_history_and_reconciliation(tmp_path: Path):
    # First signoff
    rec1 = record_uat_signoff(
        tmp_path,
        prd_id="PRD-0001",
        outcome_id="1",
        reviewer="Taylor",
        status="Pending",
        notes="Review started",
        timestamp="2026-09-29T10:00:00Z",
    )
    assert rec1["status"] == "Pending"

    # Second signoff updates status and preserves history
    rec2 = record_uat_signoff(
        tmp_path,
        prd_id="PRD-0001",
        outcome_id="1",
        reviewer="Taylor",
        status="Approved",
        notes="All good",
        timestamp="2026-09-29T12:00:00Z",
    )
    assert rec2["status"] == "Approved"
    assert len(rec2["history"]) >= 1


def test_check_uat_readiness_and_handler(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="CheckUatApp")

    import subprocess
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Taylor"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "taylor@specops.dev"], cwd=repo, check=True, capture_output=True)

    prd_file = repo / "docs" / "project" / "product" / "accepted" / "prd-0001-test.md"
    prd_file.parent.mkdir(parents=True, exist_ok=True)
    prd_file.write_text(
        "---\nid: '0001'\ntitle: Test PRD\nstatus: Accepted\ncomponent: core\n---\n\n# PRD-0001\n\n## Checkable Outcomes\n1. Outcome one\n2. Outcome two\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    # 1. Neither outcome approved
    ok, msgs = check_uat_readiness(repo)
    assert ok is False
    assert len(msgs) == 2
    assert "Release blocked: UAT sign-off missing for PRD-0001 Outcome 1" in msgs[0]
    assert "Release blocked: UAT sign-off missing for PRD-0001 Outcome 2" in msgs[1]

    config = load_config(repo)
    code = handle_check_uat(config)
    assert code == 1
    out, _ = capsys.readouterr()
    assert "Release blocked: UAT sign-off missing for PRD-0001 Outcome 1" in out
    assert "request Taylor's sign-off via the UAT visualizer matrix" in out

    # 2. Approve outcome 1 only -> readiness 50%
    record_uat_signoff(repo, "PRD-0001", "1", "Taylor", "Approved")
    h = harvest_uat_readiness(repo)
    assert h["readiness_percentage"] == 50.0

    # 3. Approve outcome 2 -> readiness 100% and handler exits 0
    record_uat_signoff(repo, "PRD-0001", "2", "Taylor", "Approved")
    h2 = harvest_uat_readiness(repo)
    assert h2["readiness_percentage"] == 100.0

    ok2, msgs2 = check_uat_readiness(repo)
    assert ok2 is True

    code2 = handle_check_uat(config)
    assert code2 == 0
    out2, _ = capsys.readouterr()
    assert "All checkable outcomes have approved PM UAT sign-offs" in out2
