"""Unit tests for INVEST task decomposition and automated DoR contract synthesis."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from spec_ops.backlog.dor_gate import audit_task_health, validate_task_dor
from spec_ops.backlog.dor_synthesizer import DORSynthesizer
from spec_ops.backlog.queue import BacklogQueue
from spec_ops.config.loader import load_config
from spec_ops.core.parser import extract_frontmatter, parse_task
from spec_ops.prd.invest_decomposer import INVESTDecomposer
from spec_ops.scaffold.init import init_project


def _run_cli(root: Path, cmd_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *cmd_args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def test_project(tmp_path: Path):
    init_project(tmp_path, name="INVESTTest")
    config = load_config(root_dir=tmp_path)

    # Scaffold accepted PRD
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd_path = prd_dir / "prd-0001-autonomous-orchestrator.md"
    prd_path.write_text(
        """---
id: '0001'
title: Autonomous SDLC Orchestrator Skill
status: Accepted
target_persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
component: orchestrator
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0006
---

# PRD-0001 — Autonomous SDLC Orchestrator Skill

## Summary
Autonomous orchestrator coordinating personas, living PRDs, BDD stories, and tasks.

## Checkable Outcomes
1. Automated vertical INVEST task decomposition from accepted PRD checkable outcomes.
2. Architectural spike prototype and feasibility benchmark harness for AST seams.
3. Automated Definition of Ready contract synthesis for proposed backlog tasks.
""",
        encoding="utf-8",
    )

    # Scaffold accepted story
    stories_dir = tmp_path / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    story_path = stories_dir / "us-0001-invest-task-decomposition.md"
    story_path.write_text(
        """---
id: '0001'
title: INVEST Task Decomposition
status: Accepted
persona: Jordan (The AI-Native Engineering Lead)
governing_prd: PRD-0001
---

# US-0001 — INVEST Task Decomposition

## Acceptance Criteria

```gherkin
Scenario: Automated INVEST decomposition
  Given an accepted PRD with checkable outcomes
  When the orchestrator executes task decomposition
  Then INVEST-compliant vertical tasks are generated.
```
""",
        encoding="utf-8",
    )

    return {"root": tmp_path, "config": config, "prd_file": prd_path}


def test_invest_decomposer_slices_and_spike(test_project):
    root = test_project["root"]
    config = test_project["config"]

    decomposer = INVESTDecomposer(config)
    results = decomposer.decompose("PRD-0001")

    assert len(results) >= 3

    # Check for presence of spike
    spikes = [r for r in results if r["is_spike"]]
    assert len(spikes) == 1
    spike = spikes[0]
    assert "SPIKE-" in spike["id"]
    assert spike["path"].is_file()

    # Check spike benchmark harness
    spike_num = spike["id"].replace("SPIKE-", "")
    harness_file = root / "spikes" / f"spike_{spike_num}" / f"test_spike_{spike_num}.py"
    assert harness_file.is_file()

    # Check generated tasks
    tasks = [r for r in results if not r["is_spike"]]
    assert len(tasks) == 3

    for t in tasks:
        assert t["path"].is_file()
        parsed = parse_task(t["path"])
        assert parsed is not None

        # Verify DoR completeness
        report = audit_task_health(parsed, config, strict=True)
        assert report.is_ready is True, f"Task {t['id']} failed DoR: {report.errors}"

        content = t["path"].read_text(encoding="utf-8")
        assert "## Acceptance Criteria" in content
        assert "## Mutation Testing Scope" in content
        assert "mutmut" in content.lower()
        assert ">=80%" in content
        assert "## Hypothesis Invariant Properties" in content
        assert "@given" in content
        assert parsed.target_bc == "orchestrator"


def test_invest_decomposer_dry_run(test_project):
    config = test_project["config"]
    proposed_dir = test_project["root"] / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    initial_files = list(proposed_dir.glob("*.md"))

    decomposer = INVESTDecomposer(config)
    results = decomposer.decompose("PRD-0001", dry_run=True)

    assert len(results) >= 3
    # Verify no files written during dry run
    current_files = list(proposed_dir.glob("*.md"))
    assert len(current_files) == len(initial_files)


def test_dor_synthesizer_incomplete_task(test_project):
    root = test_project["root"]
    config = test_project["config"]

    # Create a bare/incomplete task lacking Gherkin, mutation scope, Hypothesis, etc.
    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    incomplete_task_file = proposed_dir / "0099-bare-task.md"
    incomplete_task_file.write_text(
        """---
id: '0099'
title: Bare Proposed Feature
status: Proposed
---

# TASK-0099: Bare Proposed Feature

## Summary
Initial unrefined draft of a feature.
""",
        encoding="utf-8",
    )

    parsed_before = parse_task(incomplete_task_file)
    report_before = audit_task_health(parsed_before, config, strict=True)
    assert report_before.is_ready is False

    # Synthesize DoR contracts
    synthesizer = DORSynthesizer(config)
    ok, msg, details = synthesizer.synthesize("TASK-0099")
    assert ok is True
    assert len(details["changes"]) >= 4

    parsed_after = parse_task(incomplete_task_file)
    report_after = audit_task_health(parsed_after, config, strict=True)
    assert report_after.is_ready is True, f"Failed DoR after synthesis: {report_after.errors}"

    # Verify that the task can now be refined in the queue
    queue = BacklogQueue(config.backlog_dir)
    promoted_dest = queue.refine_task(parsed_after)
    assert promoted_dest.is_file()
    assert promoted_dest.parent.name == "refined"


def test_dor_synthesizer_dry_run(test_project):
    root = test_project["root"]
    config = test_project["config"]

    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    task_file = proposed_dir / "0098-dry-run-task.md"
    original_text = """---
id: '0098'
title: Dry Run Test Task
status: Proposed
---

# TASK-0098: Dry Run Test Task
"""
    task_file.write_text(original_text, encoding="utf-8")

    synthesizer = DORSynthesizer(config)
    ok, msg, details = synthesizer.synthesize("TASK-0098", dry_run=True)
    assert ok is True
    assert "[DRY-RUN]" in msg

    # Verify file content was unchanged
    assert task_file.read_text(encoding="utf-8") == original_text


def test_cli_task_decompose_and_synthesize_dor(test_project):
    root = test_project["root"]

    # 1. Test CLI decompose
    res_decomp = _run_cli(root, ["task", "decompose", "--prd", "PRD-0001"])
    assert res_decomp.returncode == 0, f"Decompose CLI failed: {res_decomp.stderr}\n{res_decomp.stdout}"
    assert "INVEST decomposition complete" in res_decomp.stdout

    # 2. Test CLI synthesize-dor
    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    task_file = proposed_dir / "0097-cli-test-task.md"
    task_file.write_text(
        """---
id: '0097'
title: CLI Draft Feature
status: Proposed
---

# TASK-0097: CLI Draft Feature
""",
        encoding="utf-8",
    )

    res_synth = _run_cli(root, ["task", "synthesize-dor", "TASK-0097"])
    assert res_synth.returncode == 0, f"Synthesize-dor CLI failed: {res_synth.stderr}\n{res_synth.stdout}"
    assert "Synthesized DoR contracts" in res_synth.stdout

    # 3. Test queue refine passes cleanly after synthesis
    res_refine = _run_cli(root, ["queue", "refine", "TASK-0097"])
    assert res_refine.returncode == 0, f"Queue refine CLI failed: {res_refine.stderr}\n{res_refine.stdout}"
    assert "Promoted task TASK-0097 to refined" in res_refine.stdout
