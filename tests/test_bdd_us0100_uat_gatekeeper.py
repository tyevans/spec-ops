"""BDD tests for US-0100: Customer UAT Sign-Off Cryptographic Token Exporter and Release Gatekeeper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.prd.uat import record_uat_signoff
from spec_ops.prd.uat_gatekeeper import evaluate_uat_gate, export_uat_token, handle_prd_gate
from spec_ops.scaffold.init import init_project

scenarios("features/us_0100_uat_gatekeeper.feature")


@pytest.fixture
def uat_gate_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="UATGateApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Taylor Lead PM"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "taylor@specops.local"], cwd=repo, check=True, capture_output=True)

    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd_file = prd_dir / "prd-0003-uat-testing.md"
    prd_content = """---
id: PRD-0003
title: Customer UAT Testing
status: Accepted
---

# PRD-0003: Customer UAT Testing

## Checkable Outcomes
1. Live customer visualizer displays all checkable outcomes
2. Cryptographic sign-off tokens are verifiable
"""
    prd_file.write_text(prd_content, encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup prd-0003"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "prd_id": "PRD-0003",
        "decision": None,
        "exit_code": None,
    }


@given("a PRD where 100% of checkable outcomes possess valid cryptographic UAT receipts")
def prd_with_all_approved_and_token(uat_gate_ctx: dict[str, Any]) -> None:
    repo = uat_gate_ctx["repo"]
    prd_id = uat_gate_ctx["prd_id"]

    # Record sign-offs for both outcomes
    record_uat_signoff(
        repo_root=repo,
        prd_id=prd_id,
        outcome_id="1",
        reviewer="Taylor Lead PM <taylor@specops.local>",
        status="Approved",
    )
    record_uat_signoff(
        repo_root=repo,
        prd_id=prd_id,
        outcome_id="2",
        reviewer="Taylor Lead PM <taylor@specops.local>",
        status="Approved",
    )

    # Export cryptographic UAT token
    export_uat_token(
        repo_root=repo,
        prd_id=prd_id,
        signer="Taylor Lead PM <taylor@specops.local>",
    )


@given("a PRD containing unverified checkable outcomes")
def prd_with_unverified_outcomes(uat_gate_ctx: dict[str, Any]) -> None:
    repo = uat_gate_ctx["repo"]
    prd_id = uat_gate_ctx["prd_id"]

    # Record sign-off for outcome 1 only as Approved, outcome 2 is left Pending
    record_uat_signoff(
        repo_root=repo,
        prd_id=prd_id,
        outcome_id="1",
        reviewer="Taylor Lead PM <taylor@specops.local>",
        status="Approved",
    )
    record_uat_signoff(
        repo_root=repo,
        prd_id=prd_id,
        outcome_id="2",
        reviewer="Taylor Lead PM <taylor@specops.local>",
        status="Pending",
    )


@when("the gatekeeper evaluates release readiness")
def gatekeeper_evaluates_readiness(uat_gate_ctx: dict[str, Any]) -> None:
    repo = uat_gate_ctx["repo"]
    prd_id = uat_gate_ctx["prd_id"]
    decision = evaluate_uat_gate(repo_root=repo, prd_id=prd_id, strict=False)
    uat_gate_ctx["decision"] = decision

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "prd", "gate", "--prd", prd_id],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    uat_gate_ctx["exit_code"] = res.returncode
    uat_gate_ctx["stdout"] = res.stdout


@when("the gatekeeper evaluates release readiness with strict mode")
def gatekeeper_evaluates_readiness_strict(uat_gate_ctx: dict[str, Any]) -> None:
    repo = uat_gate_ctx["repo"]
    prd_id = uat_gate_ctx["prd_id"]
    decision = evaluate_uat_gate(repo_root=repo, prd_id=prd_id, strict=True)
    uat_gate_ctx["decision"] = decision

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "prd", "gate", "--prd", prd_id, "--strict"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    uat_gate_ctx["exit_code"] = res.returncode
    uat_gate_ctx["stdout"] = res.stdout


@then("the release gate returns PASS with verification details")
def verify_pass_details(uat_gate_ctx: dict[str, Any]) -> None:
    decision = uat_gate_ctx["decision"]
    assert decision.decision == "PASS"
    assert decision.readiness_percentage == 100.0
    assert len(decision.blocking_reasons) == 0
    assert decision.approved_outcomes == 2
    assert decision.total_outcomes == 2


@then("the unverified criteria are listed as release blockers")
def verify_release_blockers(uat_gate_ctx: dict[str, Any]) -> None:
    decision = uat_gate_ctx["decision"]
    assert decision.decision == "BLOCKED"
    assert len(decision.blocking_reasons) > 0
    assert any("Outcome 2" in b for b in decision.blocking_reasons)


@then(r"the command terminates with exit code 0")
def verify_exit_0(uat_gate_ctx: dict[str, Any]) -> None:
    assert uat_gate_ctx["exit_code"] == 0


@then(r"the command terminates with exit code 1")
def verify_exit_1(uat_gate_ctx: dict[str, Any]) -> None:
    assert uat_gate_ctx["exit_code"] == 1
