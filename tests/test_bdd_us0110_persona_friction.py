"""Executable BDD scenarios for US-0110 / TASK-0162: Persona Journey Friction Auditor.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007; PRD-0003, PRD-0006; US-0110.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.cli.parser import build_parser
from spec_ops.cli.prd_handler import handle_prd_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.docs.models import ParsedCLICommand
from spec_ops.prd.persona_friction import FrictionAuditReport, PersonaFrictionAuditor

scenarios("features/us_0110_persona_friction.feature")


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    return {}


@given("established user personas and CLI command definitions")
def step_established_personas_and_commands(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    # Scaffold PERSONAS.md
    personas_dir = tmp_path / "docs" / "project" / "user_stories"
    personas_dir.mkdir(parents=True, exist_ok=True)
    personas_file = personas_dir / "PERSONAS.md"
    personas_file.write_text(
        """# SpecOps User Personas

## 1. Alex — The Agentic Systems Architect
- **Role**: Staff engineer and platform architect.
- **Pain Points**:
  - Context rot when specifications drift.
- **Goals with SpecOps**:
  - Version-lock specifications in git.

## 2. Taylor — The Product Manager
- **Role**: Product manager owning business outcomes.
- **Pain Points**:
  - High ceremony with CLI commands.
- **Goals with SpecOps**:
  - Clear user acceptance testing.
""",
        encoding="utf-8",
    )

    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)


@when("the developer runs spec-ops prd friction")
def step_run_prd_friction(bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    args = parser.parse_args(["prd", "friction"])
    ret = handle_prd_command(args, bdd_context["config"], parser)
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out


@then("the engine computes friction indices across persona touchpoints")
def step_assert_friction_indices(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] == 0
    out = bdd_context["stdout"]
    assert "SpecOps Persona Journey Friction Audit" in out
    assert "Average Friction Index:" in out
    assert "Evaluated Touchpoints:" in out


@then("displays actionable recommendations for reducing operational ceremony")
def step_assert_recommendations(bdd_context: dict[str, Any]) -> None:
    out = bdd_context["stdout"]
    assert "Top Friction Touchpoints:" in out or "Recommendations:" in out
    assert any(term in out for term in ["alias", "thresholds", "Support", "Group", "Introduce"])


@given("a workflow with high ceremony exceeding the configured friction threshold")
def step_high_ceremony_workflow(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    personas_dir = tmp_path / "docs" / "project" / "user_stories"
    personas_dir.mkdir(parents=True, exist_ok=True)
    personas_file = personas_dir / "PERSONAS.md"
    personas_file.write_text(
        """# SpecOps User Personas

## 1. Taylor — The Product Manager
- **Role**: Product manager.
- **Pain Points**:
  - High friction terminal interaction.
""",
        encoding="utf-8",
    )
    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)


@when("spec-ops prd friction is evaluated with threshold check")
def step_eval_friction_with_threshold(bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    # Provide a low threshold (e.g. 3.0) that real complex commands exceed
    args = parser.parse_args(["prd", "friction", "--threshold", "3.0"])
    ret = handle_prd_command(args, bdd_context["config"], parser)
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out


@then("high-friction commands are flagged with remediation hints")
def step_assert_flagged_with_hints(bdd_context: dict[str, Any]) -> None:
    out = bdd_context["stdout"]
    assert bdd_context["exit_code"] == 1
    assert "High-Friction Touchpoints (Threshold >= 3.0):" in out
    assert "⚠️" in out
    assert "Recommendations:" in out
    assert "flagged exceeding threshold" in out
