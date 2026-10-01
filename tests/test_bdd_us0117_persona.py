"""BDD step definitions for US-0117: Autonomous Persona Discovery and Living Maintenance Engine."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0117_persona_discovery.feature")


def _run_cli(root: Path, cmd_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *cmd_args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def bdd_env(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="PersonaBDD")
    return {
        "root": tmp_path,
        "last_res": None,
    }


@given("a repository with evolving bounded contexts and newly introduced architectural roles")
def repo_with_emerging_roles(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)

    # Introduce a new architectural role: Casey (The Security Compliance Officer)
    (prd_dir / "prd-0010.md").write_text(
        "---\n"
        "id: '0010'\n"
        "title: Enterprise Compliance Shield\n"
        "status: Accepted\n"
        "target_persona: Casey (The Security Compliance Officer)\n"
        "component: security\n"
        "---\n"
        "# Enterprise Compliance Shield\n"
        "## Checkable Outcomes\n"
        "1. Automated SOC2 compliance auditing.\n",
        encoding="utf-8",
    )


@when('the orchestrator executes "spec-ops persona audit"')
def orchestrator_executes_persona_audit(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    res = _run_cli(root, ["persona", "audit", "--json"])
    bdd_env["last_res"] = res
    assert res.returncode == 0


@then("the engine inspects all accepted PRDs, stories, and git commits")
def engine_inspects_specifications(bdd_env: dict[str, Any]):
    res = bdd_env["last_res"]
    data = json.loads(res.stdout)
    assert data["total_personas"] >= 4
    assert "Alex" in data["distribution"]
    assert "Jordan" in data["distribution"]


@then('highlights uncovered archetypes with recommended profile drafts for "PERSONAS.md".')
def highlights_uncovered_archetypes(bdd_env: dict[str, Any]):
    res = bdd_env["last_res"]
    data = json.loads(res.stdout)
    emerging = data.get("emerging_archetypes", [])
    assert any(arch["name"] == "Casey" for arch in emerging)
    casey = next(arch for arch in emerging if arch["name"] == "Casey")
    assert casey["role"] == "The Security Compliance Officer"
    assert "PRD-0010" in casey["sources"]


@given("uncovered emerging archetypes detected in repository specifications")
def uncovered_archetypes_detected(bdd_env: dict[str, Any]):
    repo_with_emerging_roles(bdd_env)
    orchestrator_executes_persona_audit(bdd_env)
    highlights_uncovered_archetypes(bdd_env)


@when('the orchestrator executes "spec-ops persona sync --apply"')
def orchestrator_executes_persona_sync(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    res = _run_cli(root, ["persona", "sync", "--apply"])
    bdd_env["sync_res"] = res
    assert res.returncode == 0


@then('synthesized persona profile additions are written to "docs/project/user_stories/PERSONAS.md"')
def persona_written_to_doc(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    personas_path = root / "docs" / "project" / "user_stories" / "PERSONAS.md"
    content = personas_path.read_text(encoding="utf-8")
    assert "Casey — The Security Compliance Officer" in content
    assert "- **Role**: Subject matter specialist and core contributor" in content


@then("subsequent persona audits confirm zero unrepresented archetypes.")
def audits_confirm_zero_emerging(bdd_env: dict[str, Any]):
    root = bdd_env["root"]
    audit_res = _run_cli(root, ["persona", "audit", "--json"])
    assert audit_res.returncode == 0
    audit_data = json.loads(audit_res.stdout)
    assert audit_data["emerging_archetypes"] == []
    assert "Casey" in audit_data["distribution"]
    assert audit_data["distribution"]["Casey"]["status"] == "Active"
