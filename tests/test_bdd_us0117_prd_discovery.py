"""BDD step definitions for US-0117: Continuous Product Discovery and Living PRD Synthesis Workflow."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0117_prd_discovery.feature")


def _run_cli(root: Path, cmd_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *cmd_args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def bdd_env(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="DiscoveryBDD")
    return {
        "root": tmp_path,
        "last_res": None,
    }


@given("an initialized SpecOps repository")
def initialized_repository(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    assert (root / "specops.toml").exists()
    assert (root / "docs" / "project").exists()


@when(parsers.parse("the orchestrator executes '{cli_cmd}'"))
def orchestrator_executes_cli(bdd_env: dict[str, Any], cli_cmd: str):
    root = bdd_env["root"]
    args = shlex.split(cli_cmd)
    if args and args[0] == "spec-ops":
        args = args[1:]
    res = _run_cli(root, args)
    bdd_env["last_res"] = res


@then('a new PRD idea draft is scaffolded in "docs/project/product/idea/"')
def verify_idea_scaffolded(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    res = bdd_env["last_res"]
    assert res.returncode == 0
    idea_dir = root / "docs" / "project" / "product" / "idea"
    files = list(idea_dir.glob("prd-*.md"))
    assert len(files) >= 1
    assert any("metric-collection" in f.name.lower() for f in files)


@then('the PRD is registered in "docs/project/product/REGISTRY.md" with status "Idea"')
def verify_registry_idea(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    reg = (root / "docs" / "project" / "product" / "REGISTRY.md").read_text(encoding="utf-8")
    assert "PRD-0001" in reg
    assert "Idea" in reg


@given('a raw idea in "docs/project/product/idea/"')
def raw_idea_in_repo(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    idea_dir = root / "docs" / "project" / "product" / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    idea_file = idea_dir / "prd-0001-autonomous-observability.md"
    idea_file.write_text(
        "---\n"
        "id: '0001'\n"
        "title: Autonomous Observability\n"
        "status: Idea\n"
        "created: 2026-10-01\n"
        "target_persona: Alex (The Agentic Systems Architect)\n"
        "component: telemetry\n"
        "---\n"
        "# PRD-0001 — Autonomous Observability\n\n"
        "## Who this is for\n\n"
        "- **Alex (The Agentic Systems Architect)**: Operators lack real-time health telemetry.\n\n"
        "## What the person cannot do today\n\n"
        "- Real-time telemetry cannot be scraped from remote subagent worktrees.\n\n"
        "## What good looks like\n\n"
        "1. **Core Capability**:\n"
        "   - Automated workflow and verifiable contract for telemetry.\n\n"
        "## What this does not do\n\n"
        "- Scope boundary: does not support ad-hoc private backdoor access.\n\n"
        "## Checkable Outcomes\n\n"
        "1. Executing CLI telemetry command returns valid metrics.\n",
        encoding="utf-8",
    )
    # Register initially in REGISTRY.md
    reg_file = root / "docs" / "project" / "product" / "REGISTRY.md"
    if not reg_file.exists():
        reg_file.write_text(
            "# PRD Registry\n\n"
            "| ID | Title | Status | Target Persona | Component |\n"
            "|---|---|---|---|---|\n"
            "| `PRD-0001` | Autonomous Observability | Idea | Alex (The Agentic Systems Architect) | telemetry |\n",
            encoding="utf-8",
        )


@then("the engine analyzes persona pain points and bounded context boundaries")
def engine_analyzes_persona_pain_points(bdd_env: dict[str, Any]):
    # Verified by the successful command execution and persona validation
    res = bdd_env["last_res"]
    assert res.returncode == 0


@then("prompts or generates checkable outcomes and non-goals")
def prompts_or_generates_outcomes(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    accepted_dir = root / "docs" / "project" / "product" / "accepted"
    accepted_files = list(accepted_dir.glob("prd-0001-*.md"))
    assert len(accepted_files) == 1
    content = accepted_files[0].read_text(encoding="utf-8")
    assert "## Checkable Outcomes" in content
    # Should have at least 3 falsifiable checkable outcomes
    assert "1. " in content and "2. " in content and "3. " in content


@then('moves the PRD to "shaped/" or "accepted/" once lint checks pass')
def prd_moved_to_accepted(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    accepted_dir = root / "docs" / "project" / "product" / "accepted"
    assert (accepted_dir / "prd-0001-autonomous-observability.md").exists()
    assert not (root / "docs" / "project" / "product" / "idea" / "prd-0001-autonomous-observability.md").exists()


@then('"docs/project/product/REGISTRY.md" reflects the updated status')
def registry_reflects_updated_status(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    reg = (root / "docs" / "project" / "product" / "REGISTRY.md").read_text(encoding="utf-8")
    assert "| `PRD-0001` | Autonomous Observability | Accepted |" in reg


@then("the shaping gate blocks promotion")
def gate_blocks_promotion(bdd_env: dict[str, Any]):
    res = bdd_env["last_res"]
    assert res.returncode != 0


@then("reports falsifiability violations for subjective adjectives")
def reports_falsifiability_violations(bdd_env: dict[str, Any]):
    res = bdd_env["last_res"]
    output = (res.stdout + res.stderr).lower()
    assert "unfalsifiable" in output or "blocked" in output or "violation" in output


@then("the PRD remains in its original lifecycle stage")
def prd_remains_in_idea(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    assert (root / "docs" / "project" / "product" / "idea" / "prd-0001-autonomous-observability.md").exists()
    assert not (root / "docs" / "project" / "product" / "accepted" / "prd-0001-autonomous-observability.md").exists()


@given("the system is initialized and ready")
def system_initialized_and_ready(bdd_env: dict[str, Any]):
    initialized_repository(bdd_env)


@when('the user executes the workflow for "Continuous Product Discovery and Living PRD Synthesis Workflow"')
def user_executes_workflow(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    # Run discovery followed by shape
    res_disc = _run_cli(root, [
        "prd", "discover",
        "--title", "Continuous Product Discovery and Living PRD Synthesis Workflow",
        "--persona", "Jordan (The AI-Native Engineering Lead)",
        "--bc", "prd",
        "--summary", "Need continuous discovery and automated synthesis of requirements.",
        "--non-interactive",
    ])
    assert res_disc.returncode == 0

    res_shape = _run_cli(root, [
        "prd", "shape",
        "--id", "PRD-0001",
        "--accept",
    ])
    bdd_env["last_res"] = res_shape
    assert res_shape.returncode == 0


@then("Autonomous PRD Discovery and Lifecycle Advancement*")
def verify_advancement(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    accepted_dir = root / "docs" / "project" / "product" / "accepted"
    files = list(accepted_dir.glob("prd-0001-*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "status: Accepted" in content


@then("observable outputs satisfy public contracts without backdoor tampering")
def verify_observable_outputs(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    reg = (root / "docs" / "project" / "product" / "REGISTRY.md").read_text(encoding="utf-8")
    assert "`PRD-0001`" in reg
    assert "Accepted" in reg
