"""Executable BDD acceptance tests for US-0067: Hierarchical Profile Inheritance, Composition, and Invariant Overrides."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.profiles.composer import compose_profiles, load_profile_definition

scenarios("features/us_0067_hierarchical_profile_inheritance_composition.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


@pytest.fixture
def repo_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    return {"repo": repo, "result": None}


@given('a profile definition file "profiles/enterprise-fintech/profile.toml"')
def given_profile_definition(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    prof_dir = repo / "profiles" / "enterprise-fintech"
    prof_dir.mkdir(parents=True, exist_ok=True)
    repo_context["prof_dir"] = prof_dir


@given('the profile specifies "extends = [\'core\', \'security\', \'ddd\']"')
def given_profile_extends(repo_context: dict[str, Any]):
    repo_context["extends"] = ["core", "security", "ddd"]


@given("defines custom vertical slices for audit trails and regulatory compliance")
def given_custom_vertical_slices(repo_context: dict[str, Any]):
    prof_dir = repo_context["prof_dir"]
    extends_str = ", ".join(f'"{x}"' for x in repo_context.get("extends", ["core"]))
    content = f"""[profile]
id = "enterprise-fintech"
name = "Enterprise Fintech Profile"
version = "1.2.0"
description = "Financial compliance profile."
extends = [{extends_str}]

[overrides.architecture]
file_length_limit = 350

[overrides.quality]
require_mutation_testing = true

[[vertical_slices.slices]]
type = "audit"
name = "Audit Trails"
prefix = "AUDIT:"
requires_adr = true

[[vertical_slices.slices]]
type = "compliance"
name = "Regulatory Compliance"
prefix = "COMP:"
requires_adr = true
"""
    (prof_dir / "profile.toml").write_text(content, encoding="utf-8")

    adrs_dir = prof_dir / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "adr-0020-financial-auditing.md").write_text(
        """---
id: '0020'
title: Enterprise Financial Auditing
status: Accepted
date: 2026-09-29
---
# ADR-0020: Enterprise Financial Auditing
""",
        encoding="utf-8",
    )


@when('the architect runs "spec-ops profiles validate profiles/enterprise-fintech"')
def when_run_validate_profile(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["profiles", "validate", "profiles/enterprise-fintech"])
    repo_context["result"] = res


@then("the profile dependency tree resolves without circular dependencies")
def then_resolves_without_cycle(repo_context: dict[str, Any]):
    res = repo_context["result"]
    assert res.returncode == 0
    assert "validated successfully" in res.stdout


@then("aggregates all inherited baseline ADRs sequentially without slug collisions.")
@then("And aggregates all inherited baseline ADRs sequentially without slug collisions.")
def then_aggregates_adrs_without_collision(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    prof_path = repo / "profiles" / "enterprise-fintech"
    comp = compose_profiles([prof_path])
    assert "core" in comp.profile_ids
    assert "security" in comp.profile_ids
    assert "ddd" in comp.profile_ids
    assert "enterprise-fintech" in comp.profile_ids
    assert any(a.canonical_id == "ADR-0001" for a in comp.adrs)
    assert any("financial-auditing" in a.slug for a in comp.adrs)


@given('an inherited profile "enterprise-fintech" extending "core"')
def given_inherited_profile(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    prof_dir = repo / "profiles" / "enterprise-fintech"
    prof_dir.mkdir(parents=True, exist_ok=True)
    repo_context["prof_dir"] = prof_dir


@given('And "profile.toml" configures "[overrides.architecture] file_length_limit = 350" and "[overrides.quality] require_mutation_testing = true"')
@given('"profile.toml" configures "[overrides.architecture] file_length_limit = 350" and "[overrides.quality] require_mutation_testing = true"')
def given_profile_overrides(repo_context: dict[str, Any]):
    prof_dir = repo_context["prof_dir"]
    toml_content = """[profile]
id = "enterprise-fintech"
name = "Enterprise Fintech Profile"
version = "1.0.0"
extends = ["core"]

[overrides.architecture]
file_length_limit = 350

[overrides.quality]
require_mutation_testing = true
"""
    (prof_dir / "profile.toml").write_text(toml_content, encoding="utf-8")
    adrs_dir = prof_dir / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "adr-0020-financial-auditing.md").write_text(
        "---\nid: '0020'\ntitle: Financial Auditing\nstatus: Accepted\n---\n# ADR-0020: Financial Auditing\n",
        encoding="utf-8",
    )


@when('a project is initialized with "spec-ops init --profile ./profiles/enterprise-fintech"')
def when_init_with_custom_profile(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    target = repo / "new_project"
    target.mkdir(parents=True, exist_ok=True)
    repo_context["target_repo"] = target
    res = run_spec_ops(target, ["init", "--profile", str(repo / "profiles" / "enterprise-fintech")])
    repo_context["result"] = res
    assert res.returncode == 0


@then('then "specops.toml" is generated with "file_length_limit = 350"')
@then('"specops.toml" is generated with "file_length_limit = 350"')
def then_specops_has_file_limit_350(repo_context: dict[str, Any]):
    target = repo_context["target_repo"]
    toml_text = (target / "specops.toml").read_text(encoding="utf-8")
    assert "file_length_limit = 350" in toml_text


@then('And "AGENTS.md" reflects the strict 350-line limit in its Hard Invariants section')
@then('"AGENTS.md" reflects the strict 350-line limit in its Hard Invariants section')
def then_agents_md_has_file_limit_350(repo_context: dict[str, Any]):
    target = repo_context["target_repo"]
    agents_text = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "<350 lines" in agents_text
    assert "~350 lines" in agents_text


@then("And the generated ADR registry incorporates both base and enterprise-specific ADRs.")
@then("the generated ADR registry incorporates both base and enterprise-specific ADRs.")
def then_adr_registry_has_both_adrs(repo_context: dict[str, Any]):
    target = repo_context["target_repo"]
    reg_text = (target / "docs" / "project" / "adrs" / "REGISTRY.md").read_text(encoding="utf-8")
    assert "ADR-0001" in reg_text
    assert "Financial Auditing" in reg_text or "ADR-0020" in reg_text


@given('profile "profile-a" extending "profile-b" and "profile-b" extending "profile-a"')
def given_circular_profiles(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    pa_dir = repo / "profiles" / "profile-a"
    pb_dir = repo / "profiles" / "profile-b"
    pa_dir.mkdir(parents=True, exist_ok=True)
    pb_dir.mkdir(parents=True, exist_ok=True)

    (pa_dir / "profile.toml").write_text(
        """[profile]
id = "profile-a"
name = "Profile A"
extends = ["profile-b"]
""",
        encoding="utf-8",
    )
    (pb_dir / "profile.toml").write_text(
        """[profile]
id = "profile-b"
name = "Profile B"
extends = ["profile-a"]
""",
        encoding="utf-8",
    )


@when('the architect runs "spec-ops profiles validate profiles/profile-a"')
def when_validate_circular_profile(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["profiles", "validate", "profiles/profile-a"])
    repo_context["result"] = res


@then("the validation fails with exit code 1")
def then_validation_fails_exit_1(repo_context: dict[str, Any]):
    res = repo_context["result"]
    assert res.returncode == 1


@then('displays "Profile Inheritance Error: Circular dependency detected (profile-a -> profile-b -> profile-a)".')
@then('And displays "Profile Inheritance Error: Circular dependency detected (profile-a -> profile-b -> profile-a)".')
def then_displays_circular_error(repo_context: dict[str, Any]):
    res = repo_context["result"]
    combined = res.stderr + "\n" + res.stdout
    assert "Profile Inheritance Error: Circular dependency detected (profile-a -> profile-b -> profile-a)" in combined
