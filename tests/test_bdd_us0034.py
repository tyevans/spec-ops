"""Executable BDD acceptance tests for US-0034: Autonomous Agent Onboarding and Discovery."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0034_agent_onboarding_discovery.feature")

CLI_ENV = {**os.environ, "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}


@pytest.fixture
def us0034_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="OnboardingApp")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Morgan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "morgan@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "agents_md_content": "",
        "cli_result": None,
        "json_payload": None,
    }


# ==============================================================================
# Scenario: Agent Constitution Ingestion and Command Discovery
# ==============================================================================


@given("a freshly cloned repository governed by SpecOps")
def setup_freshly_cloned_repo(us0034_context: dict[str, Any]):
    repo: Path = us0034_context["repo"]
    assert (repo / "AGENTS.md").is_file()
    assert (repo / "specops.toml").is_file()


@when('an autonomous agent inspects "AGENTS.md" at the repository root')
def agent_inspects_agents_md(us0034_context: dict[str, Any]):
    repo: Path = us0034_context["repo"]
    content = (repo / "AGENTS.md").read_text(encoding="utf-8")
    us0034_context["agents_md_content"] = content


@then("the agent discovers the 8 Hard Invariants including <500 line limits and blackbox testing")
def verify_hard_invariants_in_agents_md(us0034_context: dict[str, Any]):
    content: str = us0034_context["agents_md_content"]
    assert "File Length Limit (<500 lines)" in content
    assert "Blackbox Frontdoor Verification" in content
    assert "Strict Backlog Isolation" in content
    assert "UV Workspace Package Management" in content
    assert "Specification as Code" in content
    assert "Executable BDD User Stories" in content
    assert "Domain-Driven Design" in content
    assert "Property-Based Testing" in content


@then("the agent discovers the mandatory Diataxis documentation integrity requirements")
def verify_diataxis_in_agents_md(us0034_context: dict[str, Any]):
    content: str = us0034_context["agents_md_content"]
    assert "Diataxis" in content
    assert "Documentation Integrity (Diataxis)" in content or "Diataxis Standards" in content


@then('when the agent runs "spec-ops profiles info --json"')
@when('when the agent runs "spec-ops profiles info --json"')
def agent_runs_profiles_info_json(us0034_context: dict[str, Any]):
    repo: Path = us0034_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "profiles", "info", "--json"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    us0034_context["cli_result"] = res
    assert res.returncode == 0
    us0034_context["json_payload"] = json.loads(res.stdout)


@then("the CLI returns active architectural profile rules and quality preflight commands in JSON")
def verify_profiles_info_json_payload(us0034_context: dict[str, Any]):
    payload: dict[str, Any] = us0034_context["json_payload"]

    assert "active_profiles" in payload
    assert "invariants" in payload
    assert "preflight" in payload

    invariants = payload["invariants"]
    rule_names = [inv.get("name") for inv in invariants]
    assert "file_length_limit" in rule_names
    assert "blackbox_verification" in rule_names

    preflight = payload["preflight"]
    assert "commands" in preflight
    assert "chain" in preflight


@then("the agent confirms all verification requirements before generating any code.")
def verify_criteria_confirmed(us0034_context: dict[str, Any]):
    payload: dict[str, Any] = us0034_context["json_payload"]
    criteria = payload.get("verification_criteria", [])
    assert len(criteria) >= 3
    assert any("500" in c for c in criteria)
    assert any("blackbox" in c.lower() for c in criteria)
