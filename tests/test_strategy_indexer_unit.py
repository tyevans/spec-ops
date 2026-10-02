"""Unit and mutation kill tests for spec_ops.rescue.strategy_indexer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from spec_ops.config.loader import load_config
from spec_ops.rescue.strategy_indexer import (
    BASELINE_STRATEGIES,
    HealingPlaybook,
    HealingStrategy,
    StrategyIndexer,
    export_playbook,
    handle_playbooks_command,
)
from spec_ops.scaffold.init import init_project


def test_healing_strategy_to_dict() -> None:
    s = HealingStrategy(
        strategy_id="strat-custom",
        category="test_cat",
        failure_signature="Custom Failure",
        ranking_score=5.5,
        summary="A summary",
        actionable_remedy="A remedy",
        code_snippet="echo 1",
        prompt_instruction="Do not fail",
    )
    d = s.to_dict()
    assert d["strategy_id"] == "strat-custom"
    assert d["ranking_score"] == 5.5
    assert d["category"] == "test_cat"


def test_healing_playbook_search_and_format() -> None:
    s1 = HealingStrategy(
        strategy_id="strat-adr0002",
        category="file_length",
        failure_signature="ADR-0002 file length limit",
        ranking_score=10.0,
        summary="Decompose module",
        actionable_remedy="Run decompose",
    )
    s2 = HealingStrategy(
        strategy_id="strat-adr0003",
        category="mock_backdoor",
        failure_signature="ADR-0003 mock backdoor",
        ranking_score=8.0,
        summary="Use public frontdoors",
        actionable_remedy="Avoid mock",
    )
    pb = HealingPlaybook(strategies=[s2, s1])
    assert pb.total_strategies == 2

    # Empty search returns all sorted by ranking score descending
    all_res = pb.search()
    assert all_res[0].strategy_id == "strat-adr0002"
    assert all_res[1].strategy_id == "strat-adr0003"

    # Targeted query search
    res = pb.search("mock")
    assert len(res) == 1
    assert res[0].strategy_id == "strat-adr0003"

    # Empty match
    no_res = pb.search("nonexistent_signature_xyz")
    assert len(no_res) == 0

    # format_text with empty match
    empty_txt = pb.format_text("nonexistent_xyz")
    assert "No matching healing strategies found" in empty_txt

    # format_text with match
    match_txt = pb.format_text("file_length")
    assert "[strat-adr0002]" in match_txt
    assert "Decompose module" in match_txt


@pytest.fixture
def mock_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "mock_rescue_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="MockRescue", target_dir=repo)

    failures_dir = repo / ".specops" / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    (failures_dir / "f1.json").write_text(
        json.dumps(
            [
                {"task_id": "TASK-0001", "reason": "ADR-0002 violation", "failed_invariants": ["ADR-0002"]},
                {"task_id": "TASK-0002", "reason": "random custom crash in parser syntax", "failed_invariants": []},
            ]
        ),
        encoding="utf-8",
    )
    (failures_dir / "f2.json").write_text(
        json.dumps({"task_id": "TASK-0003", "reason": "ADR-0002 again", "failed_invariants": ["ADR-0002"]}),
        encoding="utf-8",
    )
    (failures_dir / "corrupted.json").write_text("{corrupt", encoding="utf-8")

    # Add task with failure_history in backlog
    comp_dir = repo / "docs" / "project" / "backlog" / "complete"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "0001-task.md").write_text(
        """---
id: '0001'
title: Task 1
status: Complete
failure_history:
  - reason: "ADR-0003 mock detected"
    failed_invariants:
      - ADR-0003
---
# Task 1
""",
        encoding="utf-8",
    )

    return repo


def test_strategy_indexer_harvest_and_compile(mock_repo: Path) -> None:
    indexer = StrategyIndexer(mock_repo)
    entries = indexer.harvest_failure_entries()
    assert len(entries) >= 3

    pb = indexer.compile_playbook()
    # Baseline strategies
    assert pb.total_strategies >= len(BASELINE_STRATEGIES)

    # ADR-0002 should have score boost from multiple occurrences
    adr2_strat = [s for s in pb.strategies if s.strategy_id == "strat-adr0002-file-length"][0]
    assert adr2_strat.ranking_score > 10.0

    # Custom learned strategy generated for unmapped crash
    learned = [s for s in pb.strategies if "custom" in s.strategy_id]
    assert len(learned) >= 1
    assert "random" in learned[0].failure_signature or "crash" in learned[0].failure_signature


def test_export_playbook(mock_repo: Path, tmp_path: Path) -> None:
    indexer = StrategyIndexer(mock_repo)
    pb = indexer.compile_playbook()

    # Markdown export
    md_p = tmp_path / "playbook.md"
    export_playbook(pb, md_p)
    assert md_p.is_file()
    text = md_p.read_text(encoding="utf-8")
    assert "# SpecOps Autonomous Failure Healing Playbook" in text
    assert "## Remediation Strategies" in text

    # JSON export
    json_p = tmp_path / "playbook.json"
    export_playbook(pb, json_p)
    assert json_p.is_file()
    data = json.loads(json_p.read_text(encoding="utf-8"))
    assert "total_strategies" in data
    assert len(data["strategies"]) == pb.total_strategies


def test_handle_playbooks_command(mock_repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    cfg = load_config(mock_repo)

    # Default invocation
    args = type("Args", (), {"query": None, "json": False, "export": None})()
    rc = handle_playbooks_command(args, cfg)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Autonomous Failure Healing Playbook" in out

    # With query and export
    exp_file = tmp_path / "exported.md"
    args2 = type("Args", (), {"query": "ADR-0002", "json": False, "export": str(exp_file)})()
    rc2 = handle_playbooks_command(args2, cfg)
    assert rc2 == 0
    assert exp_file.is_file()
    out2 = capsys.readouterr().out
    assert "Exported autonomous healing playbook" in out2
    assert "strat-adr0002-file-length" in out2

    # JSON mode with query
    args3 = type("Args", (), {"query": "ADR-0003", "json": True, "export": None})()
    rc3 = handle_playbooks_command(args3, cfg)
    assert rc3 == 0
    out3 = capsys.readouterr().out
    jdata = json.loads(out3)
    assert jdata["query"] == "ADR-0003"
    assert jdata["total_matched"] >= 1
