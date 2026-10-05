"""BDD step definitions for US-0132: Default SpecOps SDLC Orchestrator Skill Scaffolding on Project Onboarding.

Target bounded context: scaffold. Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006.
Source file strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/us_0132_default_skill_scaffolding.feature")


def _run_cli(root: Path, cmd_str: str) -> subprocess.CompletedProcess[str]:
    parts = shlex.split(cmd_str)
    if parts and parts[0] == "spec-ops":
        parts = parts[1:]
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *parts],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def bdd_onboarding_env(tmp_path: Path) -> dict[str, Any]:
    return {
        "root": tmp_path,
        "last_res": None,
    }


@given("a blank project directory")
def given_blank_project_dir(bdd_onboarding_env: dict[str, Any], tmp_path: Path) -> None:
    target = tmp_path / "new_project"
    target.mkdir(parents=True, exist_ok=True)
    bdd_onboarding_env["root"] = target


@when('the user runs "spec-ops init --name TestApp" without specifying agent flags')
def when_user_runs_init_no_agent_flags(bdd_onboarding_env: dict[str, Any]) -> None:
    root = bdd_onboarding_env["root"]
    res = _run_cli(root, "spec-ops init --name TestApp")
    bdd_onboarding_env["last_res"] = res


@then('".agents/skills/spec-ops/SKILL.md" is scaffolded into the repository')
def then_specops_skill_scaffolded(bdd_onboarding_env: dict[str, Any]) -> None:
    root = bdd_onboarding_env["root"]
    skill_file = root / ".agents" / "skills" / "spec-ops" / "SKILL.md"
    assert skill_file.is_file(), f"Expected skill file at {skill_file}"
    content = skill_file.read_text(encoding="utf-8")
    assert "name: spec-ops" in content
    assert "SpecOps Full-Lifecycle SDLC Orchestrator" in content


@then('"specops.toml" is created.')
def then_specops_toml_created(bdd_onboarding_env: dict[str, Any]) -> None:
    root = bdd_onboarding_env["root"]
    assert (root / "specops.toml").is_file()


@when('the user initializes a project via "spec-ops init"')
def when_user_initializes_project(bdd_onboarding_env: dict[str, Any]) -> None:
    root = bdd_onboarding_env["root"]
    res = _run_cli(root, "spec-ops init --name TestRunbooks")
    bdd_onboarding_env["last_res"] = res


@then('".agents/skills/spec-ops/references/cli_primer.md" exists')
def then_cli_primer_exists(bdd_onboarding_env: dict[str, Any]) -> None:
    root = bdd_onboarding_env["root"]
    ref_file = root / ".agents" / "skills" / "spec-ops" / "references" / "cli_primer.md"
    assert ref_file.is_file(), f"Expected primer at {ref_file}"


@then('".agents/skills/spec-ops/references/balancing_loop.md" exists')
def then_balancing_loop_exists(bdd_onboarding_env: dict[str, Any]) -> None:
    root = bdd_onboarding_env["root"]
    ref_file = root / ".agents" / "skills" / "spec-ops" / "references" / "balancing_loop.md"
    assert ref_file.is_file(), f"Expected balancing loop at {ref_file}"


@then('".agents/skills/spec-ops/references/orchestration_protocol.md" exists.')
def then_orchestration_protocol_exists(bdd_onboarding_env: dict[str, Any]) -> None:
    root = bdd_onboarding_env["root"]
    ref_file = root / ".agents" / "skills" / "spec-ops" / "references" / "orchestration_protocol.md"
    assert ref_file.is_file(), f"Expected protocol at {ref_file}"


@given("an existing codebase directory")
def given_existing_codebase_dir(bdd_onboarding_env: dict[str, Any], tmp_path: Path) -> None:
    target = tmp_path / "brownfield_repo"
    target.mkdir(parents=True, exist_ok=True)
    src_dir = target / "src" / "legacy"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "app.py").write_text("print('legacy app')\n", encoding="utf-8")
    bdd_onboarding_env["root"] = target


@when('the user executes "spec-ops adopt"')
def when_user_executes_adopt(bdd_onboarding_env: dict[str, Any]) -> None:
    root = bdd_onboarding_env["root"]
    res = _run_cli(root, "spec-ops adopt --name BrownfieldSystem")
    bdd_onboarding_env["last_res"] = res


@then('".agents/skills/spec-ops/SKILL.md" is created alongside PMaC governance documents.')
def then_skill_created_alongside_pmac(bdd_onboarding_env: dict[str, Any]) -> None:
    root = bdd_onboarding_env["root"]
    res = bdd_onboarding_env["last_res"]
    assert res is not None
    assert res.returncode == 0, f"spec-ops adopt failed: {res.stderr}\n{res.stdout}"
    assert (root / ".agents" / "skills" / "spec-ops" / "SKILL.md").is_file()
    assert (root / "docs" / "project").is_dir()
    assert (root / "specops.toml").is_file()
