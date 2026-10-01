"""Unit tests for orchestration retrospective and self-healing engine (ADR-0020, US-0117)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_ops.cli.main import build_parser
from spec_ops.cli.orchestrate_handler import handle_orchestrate_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.worker.retrospective import (
    FailurePattern,
    classify_failure,
    get_orchestration_health,
    run_retrospective,
    scan_failure_logs,
    synthesize_remediation_task,
)


def test_classify_failure_all_five_categories():
    # 1. Mock backdoor (ADR-0003)
    p3 = classify_failure("Prohibited invocation of mock backdoor unittest.mock.patch")
    assert any(p.invariant_id == "ADR-0003" for p in p3)
    assert any("mock" in p.mandate.lower() for p in p3)

    # 2. File length limit (ADR-0002)
    p2 = classify_failure("File length limit violation: module has 520 lines > limit 500")
    assert any(p.invariant_id == "ADR-0002" for p in p2)
    assert any("500 lines" in p.mandate for p in p2)

    # 3. Secret scanner leak (ADR-0019)
    p19 = classify_failure("High-entropy credential detected: AWS API Key token leak")
    assert any(p.invariant_id == "ADR-0019" for p in p19)
    assert any("never hardcode credentials" in p.mandate.lower() for p in p19)

    # 4. Lockfile drift (ADR-0018)
    p18 = classify_failure("Supply-chain lockfile mutation detected in uv.lock")
    assert any(p.invariant_id == "ADR-0018" for p in p18)
    assert any("lockfile" in p.mandate.lower() for p in p18)

    # 5. DAG cycle deadlock (ADR-0017)
    p17 = classify_failure("Tarjan SCC detected circular dependency cycle deadlock between tasks")
    assert any(p.invariant_id == "ADR-0017" for p in p17)
    assert any("acyclic" in p.mandate.lower() for p in p17)


def test_classify_failure_fallback_on_unknown():
    fallback = classify_failure("Some completely unknown non-specific error string without domain keywords")
    assert len(fallback) == 1
    assert fallback[0].invariant_id == "ADR-0020"
    assert fallback[0].category == "Generic orchestration failure"


def test_synthesize_remediation_task_dry_run_and_write(tmp_path: Path):
    backlog_dir = tmp_path / "docs" / "project" / "backlog"
    backlog_dir.mkdir(parents=True)
    pat = FailurePattern(
        invariant_id="ADR-0003",
        category="Mock backdoors / private internal tampering",
        mandate="You must strictly use public frontdoor entrypoints with zero mock backdoors.",
        governing_adrs=["ADR-0003", "ADR-0020"],
        governing_prds=["PRD-0001", "PRD-0006"],
        matched_text="Prohibited mock call",
    )

    # Dry run
    f_dry, meta_dry = synthesize_remediation_task(pat, backlog_dir, dry_run=True, next_task_id=200)
    assert f_dry is None
    assert meta_dry["id"] == "0200"
    assert not (backlog_dir / "proposed").exists()

    # Actual write
    f_real, meta_real = synthesize_remediation_task(pat, backlog_dir, dry_run=False, next_task_id=200)
    assert f_real is not None
    assert f_real.exists()
    content = f_real.read_text(encoding="utf-8")
    assert "id: '0200'" in content
    assert "status: Proposed" in content
    assert "ADR-0003" in content
    assert "## Prior Attempt Failures & Anti-Patterns (DO NOT REPEAT)" in content
    assert "Prohibited mock call" in content


def test_scan_failure_logs_various_artifacts(tmp_path: Path):
    wt_dir = tmp_path / "wt1"
    wt_dir.mkdir()

    # Handover artifact
    (wt_dir / "HANDOVER.md").write_text(
        "## Exact Failure Log\n```text\nFile length violation: 540 lines > limit 500\n```\n",
        encoding="utf-8",
    )
    # Security audit log
    (wt_dir / ".security-audit.log").write_text(
        "{\"command\": \"curl\", \"details\": \"High-entropy secret exposed\"}\n",
        encoding="utf-8",
    )

    patterns = scan_failure_logs(target_dir=tmp_path)
    inv_ids = {p.invariant_id for p in patterns}
    assert "ADR-0002" in inv_ids
    assert "ADR-0019" in inv_ids


def test_get_orchestration_health_calculation(tmp_path: Path):
    wt_dir = tmp_path / ".worktrees"
    wt_dir.mkdir()

    # Successful/active worktree
    wt_ok = wt_dir / "task-0001"
    wt_ok.mkdir()
    (wt_ok / ".worker.json").write_text(json.dumps({"status": "Completed", "stalled": False}), encoding="utf-8")

    # Stalled worktree
    wt_stalled = wt_dir / "task-0002"
    wt_stalled.mkdir()
    (wt_stalled / ".failure.log").write_text("Fatal error occurred in preflight", encoding="utf-8")

    summary = get_orchestration_health(repo_root=tmp_path)
    assert summary.total_attempts == 2
    assert summary.passed_attempts == 1
    assert summary.failed_attempts == 1
    assert summary.pass_rate == 50.0
    assert len(summary.stalled_worktrees) == 1
    assert summary.is_healthy is False


def test_cli_orchestrate_retrospect_and_health(tmp_path: Path, capsys: pytest.CaptureFixture):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    backlog_dir = repo_root / "docs" / "project" / "backlog"
    backlog_dir.mkdir(parents=True)
    cfg = SpecOpsConfig(root_dir=repo_root)
    parser = build_parser()

    # Retrospect with dry-run and json
    args_retro = parser.parse_args(["orchestrate", "retrospect", "--dry-run", "--json"])
    rc_retro = handle_orchestrate_command(args_retro, cfg, parser)
    assert rc_retro == 0
    out_retro = capsys.readouterr().out
    data_retro = json.loads(out_retro)
    assert data_retro["success"] is True
    assert data_retro["dry_run"] is True

    # Health with json
    args_health = parser.parse_args(["orchestrate", "health", "--json"])
    rc_health = handle_orchestrate_command(args_health, cfg, parser)
    assert rc_health == 0
    out_health = capsys.readouterr().out
    data_health = json.loads(out_health)
    assert "pass_rate" in data_health
    assert "stalled_worktrees" in data_health
