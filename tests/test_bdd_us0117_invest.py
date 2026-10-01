"""BDD step definitions for US-0117: INVEST Task Decomposition and Automated DoR Contract Synthesis."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.dor_gate import audit_task_health
from spec_ops.config.loader import load_config
from spec_ops.core.parser import parse_task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0117_invest_decomposition.feature")


def _run_cli(root: Path, cmd_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *cmd_args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def bdd_invest_env(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="INVESTBDD")
    config = load_config(root_dir=tmp_path)
    return {
        "root": tmp_path,
        "config": config,
        "last_res": None,
    }


@given("an accepted PRD with multiple checkable outcomes")
def given_accepted_prd_multiple_outcomes(bdd_invest_env: dict[str, Any]):
    root = bdd_invest_env["root"]
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0006-autonomous-sdlc.md").write_text(
        """---
id: '0006'
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

# PRD-0006 — Autonomous SDLC Orchestrator Skill

## Checkable Outcomes
1. Automated vertical INVEST task decomposition from checkable outcomes.
2. Automated Definition of Ready contract synthesis for proposed backlog tasks.
""",
        encoding="utf-8",
    )

    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0117-sdlc-orchestrator.md").write_text(
        """---
id: '0117'
title: SDLC Orchestrator Skill
status: Accepted
persona: Jordan (The AI-Native Engineering Lead)
governing_prd: PRD-0006
---

# US-0117 — SDLC Orchestrator Skill

## Acceptance Criteria

```gherkin
Scenario: Verify SDLC Orchestrator
  Given the system is initialized
  When orchestrating tasks
  Then INVEST slicing occurs.
```
""",
        encoding="utf-8",
    )


@given("an accepted PRD containing an outcome with architectural uncertainty")
def given_accepted_prd_with_uncertainty(bdd_invest_env: dict[str, Any]):
    root = bdd_invest_env["root"]
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0006-autonomous-sdlc.md").write_text(
        """---
id: '0006'
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

# PRD-0006 — Autonomous SDLC Orchestrator Skill

## Checkable Outcomes
1. Architectural spike and feasibility benchmark prototype for distributed AST graph indexing.
2. Production AST graph query API implementation.
""",
        encoding="utf-8",
    )


@given("an unrefined proposed task lacking DoR acceptance criteria")
def given_unrefined_proposed_task(bdd_invest_env: dict[str, Any]):
    root = bdd_invest_env["root"]
    # Ensure baseline PRD & story exist
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0001-core.md").write_text(
        """---
id: '0001'
title: Core System
status: Accepted
target_persona: Jordan (The AI-Native Engineering Lead)
component: core
---
# PRD-0001
## Checkable Outcomes
1. System core contract.
""",
        encoding="utf-8",
    )

    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    task_file = proposed_dir / "0099-unrefined-task.md"
    task_file.write_text(
        """---
id: '0099'
title: Unrefined Task Feature
status: Proposed
---

# TASK-0099: Unrefined Task Feature

## Summary
Initial stub of a task lacking DoR contracts.
""",
        encoding="utf-8",
    )
    bdd_invest_env["unrefined_task_file"] = task_file


@when(parsers.parse('the orchestrator executes "{cli_cmd}"'))
def when_orchestrator_executes_cmd(bdd_invest_env: dict[str, Any], cli_cmd: str):
    root = bdd_invest_env["root"]
    args = cli_cmd.split()[1:]  # strip 'spec-ops'
    res = _run_cli(root, args)
    bdd_invest_env["last_res"] = res


@then("the engine slices the scope into INVEST-compliant vertical tasks <500 lines")
def then_slices_scope_invest_tasks(bdd_invest_env: dict[str, Any]):
    root = bdd_invest_env["root"]
    res = bdd_invest_env["last_res"]
    assert res.returncode == 0, f"Decompose failed: {res.stderr}\n{res.stdout}"

    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    task_files = [p for p in proposed_dir.glob("*.md") if not p.name.startswith("spike")]
    assert len(task_files) >= 2

    for tf in task_files:
        content = tf.read_text(encoding="utf-8")
        assert len(content.splitlines()) < 500
        assert "<500 lines" in content or "strictly <500 lines" in content
        assert "target_bc: orchestrator" in content


@then("generates executable Gherkin scenarios and property test targets for each task.")
def then_generates_gherkin_and_properties(bdd_invest_env: dict[str, Any]):
    root = bdd_invest_env["root"]
    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    task_files = list(proposed_dir.glob("*.md"))

    for tf in task_files:
        content = tf.read_text(encoding="utf-8")
        assert "## Acceptance Criteria" in content
        assert "```gherkin" in content
        assert "Scenario:" in content
        assert "Given" in content
        assert "When" in content
        assert "Then" in content
        assert "## Mutation Testing Scope" in content
        assert "mutmut" in content.lower()
        assert "## Hypothesis Invariant Properties" in content
        assert "@given" in content


@then("an architectural spike is scaffolded in proposed backlog")
def then_architectural_spike_scaffolded(bdd_invest_env: dict[str, Any]):
    root = bdd_invest_env["root"]
    res = bdd_invest_env["last_res"]
    assert res.returncode == 0, f"Decompose failed: {res.stderr}\n{res.stdout}"

    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    spike_files = [p for p in proposed_dir.glob("*.md") if "spike" in p.name.lower()]
    assert len(spike_files) >= 1
    bdd_invest_env["spike_file"] = spike_files[0]


@then('an empirical benchmark test harness is initialized in "spikes/".')
def then_benchmark_harness_initialized(bdd_invest_env: dict[str, Any]):
    root = bdd_invest_env["root"]
    spikes_dir = root / "spikes"
    assert spikes_dir.is_dir()
    harnesses = list(spikes_dir.glob("spike_*"))
    assert len(harnesses) >= 1
    assert any((h / "__init__.py").exists() for h in harnesses)


@then("missing Gherkin scenarios, mutation scopes, and property invariants are synthesized")
def then_contracts_synthesized(bdd_invest_env: dict[str, Any]):
    res = bdd_invest_env["last_res"]
    assert res.returncode == 0, f"Synthesize failed: {res.stderr}\n{res.stdout}"
    assert "Synthesized DoR contracts" in res.stdout

    task_file = bdd_invest_env["unrefined_task_file"]
    content = task_file.read_text(encoding="utf-8")
    assert "## Acceptance Criteria" in content
    assert "```gherkin" in content
    assert "## Mutation Testing Scope" in content
    assert "mutmut" in content.lower()
    assert "## Hypothesis Invariant Properties" in content
    assert "@given" in content


@then("the task satisfies all Definition of Ready rules for queue refinement.")
def then_task_satisfies_dor_for_refinement(bdd_invest_env: dict[str, Any]):
    root = bdd_invest_env["root"]
    config = bdd_invest_env["config"]
    task_file = bdd_invest_env["unrefined_task_file"]

    parsed = parse_task(task_file)
    report = audit_task_health(parsed, config, strict=True)
    assert report.is_ready is True, f"DoR audit failed after synthesis: {report.errors}"

    # Verify queue refine CLI accepts it
    res_refine = _run_cli(root, ["queue", "refine", "TASK-0099"])
    assert res_refine.returncode == 0, f"Queue refine failed: {res_refine.stderr}\n{res_refine.stdout}"
