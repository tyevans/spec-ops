"""Unit tests for Customer UAT CLI subcommands and receipt verification."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from spec_ops.config.models import SpecOpsConfig
from spec_ops.prd.uat import record_uat_signoff
from spec_ops.prd.uat_cli import (
    compute_uat_receipt_signature,
    dispatch_uat_command,
    generate_customer_uat_receipt,
    handle_uat_receipt,
    handle_uat_sign,
    handle_uat_status,
    verify_customer_uat_receipt,
)
from spec_ops.scaffold.init import init_project


@pytest.fixture
def repo_fixture(tmp_path: Path) -> tuple[Path, SpecOpsConfig]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="TestApp")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo, check=True, capture_output=True)

    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0001.md").write_text(
        """---
id: '0001'
title: Sample Feature
status: Accepted
component: core
---

# PRD-0001 — Sample Feature

## Checkable Outcomes

1. System provides fast receipt generation.
2. System detects any git tree tampering.
""",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    from spec_ops.config.loader import load_config
    config = load_config(repo)
    return repo, config


def test_uat_status_text_and_json(repo_fixture: tuple[Path, SpecOpsConfig], capsys: pytest.CaptureFixture[str]):
    repo, config = repo_fixture

    # Text mode
    rc = handle_uat_status(config, json_output=False)
    assert rc == 0
    out = capsys.readouterr().out
    assert "=== Customer UAT Readiness Matrix ===" in out
    assert "PRD-0001 Outcome 1" in out

    # JSON mode
    rc_json = handle_uat_status(config, json_output=True)
    assert rc_json == 0
    out_json = capsys.readouterr().out
    data = json.loads(out_json)
    assert "readiness_percentage" in data
    assert "matrix" in data
    assert len(data["matrix"]) == 2


def test_uat_sign_approved_and_rejected(repo_fixture: tuple[Path, SpecOpsConfig], capsys: pytest.CaptureFixture[str]):
    repo, config = repo_fixture

    # Sign outcome 1 as Approved
    rc = handle_uat_sign(
        config,
        prd="PRD-0001",
        outcome="1",
        reviewer="Taylor <taylor@specops.local>",
        status="Approved",
        notes="Verified feature 1",
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Recorded PM business acceptance sign-off for PRD-0001 Outcome 1: Approved" in out

    # Sign outcome 2 as Rejected
    rc2 = handle_uat_sign(
        config,
        prd="PRD-0001",
        outcome="2",
        reviewer="Jordan <jordan@specops.local>",
        status="Rejected",
        notes="Tampering detection incomplete",
    )
    assert rc2 == 0
    out2 = capsys.readouterr().out
    assert "Recorded PM business acceptance sign-off for PRD-0001 Outcome 2: Rejected" in out2

    # Verify persisted in uat-signoff.json
    signoffs_file = repo / "docs" / "project" / "product" / "uat-signoff.json"
    assert signoffs_file.is_file()
    saved = json.loads(signoffs_file.read_text(encoding="utf-8"))
    assert saved["signoffs"]["PRD-0001:1"]["status"] == "Approved"
    assert saved["signoffs"]["PRD-0001:2"]["status"] == "Rejected"


def test_uat_receipt_generation_and_verification(repo_fixture: tuple[Path, SpecOpsConfig], capsys: pytest.CaptureFixture[str]):
    repo, config = repo_fixture

    # Approve all outcomes
    record_uat_signoff(repo, "PRD-0001", "1", "Taylor <taylor@specops.local>", "Approved")
    record_uat_signoff(repo, "PRD-0001", "2", "Taylor <taylor@specops.local>", "Approved")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "signoffs"], cwd=repo, check=True, capture_output=True)

    # 1. Generate receipt with custom path
    custom_out = repo / "dist" / "custom" / "receipt.json"
    rc_gen = handle_uat_receipt(config, prd="PRD-0001", out=str(custom_out), verify=False)
    assert rc_gen == 0
    assert custom_out.is_file()

    # 2. Verify receipt successfully
    rc_ver = handle_uat_receipt(config, out=str(custom_out), verify=True)
    assert rc_ver == 0
    out_ver = capsys.readouterr().out
    assert "verified successfully" in out_ver

    # 3. Tamper with a file in git repo
    f = repo / "tampered.py"
    f.write_text("print('tampered')\n", encoding="utf-8")
    subprocess.run(["git", "add", "tampered.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "tampered"], cwd=repo, check=True, capture_output=True)

    rc_tampered = handle_uat_receipt(config, out=str(custom_out), verify=True)
    assert rc_tampered == 1
    out_tampered = capsys.readouterr().out
    assert "verification failed" in out_tampered
    assert "Tampering detected" in out_tampered


def test_uat_receipt_verification_error_cases(tmp_path: Path):
    # Nonexistent file
    valid, issues = verify_customer_uat_receipt(tmp_path / "nonexistent.json", tmp_path)
    assert valid is False
    assert any("does not exist" in i.lower() for i in issues)

    # Malformed JSON
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    valid_bad, issues_bad = verify_customer_uat_receipt(bad, tmp_path)
    assert valid_bad is False
    assert any("malformed" in i.lower() for i in issues_bad)

    # Missing fields
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    valid_empty, issues_empty = verify_customer_uat_receipt(empty, tmp_path)
    assert valid_empty is False
    assert any("missing required" in i.lower() for i in issues_empty)


def test_dispatch_uat_command(repo_fixture: tuple[Path, SpecOpsConfig]):
    repo, config = repo_fixture
    parser = argparse.ArgumentParser()

    # Dispatch status
    args_status = argparse.Namespace(uat_action="status", json=True)
    rc_status = dispatch_uat_command(args_status, config, parser)
    assert rc_status == 0

    # Dispatch sign
    args_sign = argparse.Namespace(
        uat_action="sign",
        prd="PRD-0001",
        outcome="1",
        reviewer="Taylor <taylor@specops.local>",
        status="Approved",
        notes="OK",
    )
    rc_sign = dispatch_uat_command(args_sign, config, parser)
    assert rc_sign == 0

    # Dispatch receipt
    args_receipt = argparse.Namespace(
        uat_action="receipt",
        prd="PRD-0001",
        out=str(repo / "dist" / "uat" / "test.json"),
        verify=False,
    )
    rc_receipt = dispatch_uat_command(args_receipt, config, parser)
    assert rc_receipt == 0
