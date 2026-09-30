"""Executable BDD acceptance tests for US-0012: Custom Architectural Profile Authoring and Multi-Repo Distribution."""

from __future__ import annotations

import os
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.profiles.packager import load_profile_from_bundle

scenarios("features/us_0012_custom_profile_authoring_distribution.feature")

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
    return {"repo": repo, "result": None, "bundle_path": None}


@given('a local profile definition directory "profiles/fintech-service" containing custom ADRs and "profile.toml"')
def given_local_profile_dir(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    prof_dir = repo / "profiles" / "fintech-service"
    prof_dir.mkdir(parents=True, exist_ok=True)

    profile_toml = """[profile]
id = "fintech-service"
name = "Fintech Service Profile"
version = "1.0.0"
description = "Financial services baseline with strict audit logging."
extends = ["core"]

[overrides.architecture]
file_length_limit = 450

[invariants]
rules = [
  "All transactions must record immutable audit logs.",
  "PCI-DSS cardholder data compliance must be enforced."
]
"""
    (prof_dir / "profile.toml").write_text(profile_toml, encoding="utf-8")

    adrs_dir = prof_dir / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    adr_content = """---
id: '0008'
title: Mandatory Transaction Audit Logging
status: Accepted
date: 2026-09-29
---

# ADR-0008: Mandatory Transaction Audit Logging

## Status
Accepted

## Context
Financial compliance requires append-only audit records.
"""
    (adrs_dir / "adr-0008-audit-logging.md").write_text(adr_content, encoding="utf-8")


@when('the architect runs "spec-ops profiles package profiles/fintech-service --out dist/fintech-service.sop"')
def when_package_profile(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["profiles", "package", "profiles/fintech-service", "--out", "dist/fintech-service.sop"])
    repo_context["result"] = res


@then('a verified profile bundle "dist/fintech-service.sop" is created')
def then_bundle_created(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    bundle = repo / "dist" / "fintech-service.sop"
    assert bundle.is_file()
    repo_context["bundle_path"] = bundle


@then('the bundle contains validated ADR frontmatter, custom file limits, and agent rule fragments.')
@then('And the bundle contains validated ADR frontmatter, custom file limits, and agent rule fragments.')
def then_bundle_contents_verified(repo_context: dict[str, Any]):
    bundle = repo_context["bundle_path"]
    prof = load_profile_from_bundle(bundle)
    assert prof.id == "fintech-service"
    assert prof.version == "1.0.0"
    assert prof.overrides.get("architecture", {}).get("file_length_limit") == 450
    assert len(prof.invariants) >= 2
    assert any("audit logs" in inv for inv in prof.invariants)
    assert len(prof.adrs) >= 1
    assert prof.adrs[0].number == 8


@given("a blank repository directory")
def given_blank_repo_dir(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    # Ensure target is clean
    target_repo = repo / "target_project"
    target_repo.mkdir(parents=True, exist_ok=True)
    repo_context["target_repo"] = target_repo


@given('a custom profile bundle "fintech-service.sop"')
def given_bundle_exists(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    bundle_path = repo / "dist" / "fintech-service.sop"
    if not bundle_path.exists():
        prof_dir = repo / "profiles" / "fintech-service"
        prof_dir.mkdir(parents=True, exist_ok=True)
        (prof_dir / "profile.toml").write_text(
            """[profile]
id = "fintech-service"
name = "Fintech Service Profile"
version = "1.0.0"
description = "Fintech profile."
extends = ["core"]

[invariants]
rules = [
  "All transactions must record immutable audit logs."
]
""",
            encoding="utf-8",
        )
        adrs_dir = prof_dir / "adrs" / "accepted"
        adrs_dir.mkdir(parents=True, exist_ok=True)
        (adrs_dir / "adr-0008-audit-logging.md").write_text(
            "---\nid: '0008'\ntitle: Audit Logging\nstatus: Accepted\n---\n# ADR-0008: Audit Logging\n",
            encoding="utf-8",
        )
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(bundle_path, "w:gz") as tar:
            for item in sorted(prof_dir.rglob("*")):
                if item.is_file():
                    tar.add(item, arcname=item.relative_to(prof_dir).as_posix())
    repo_context["bundle_path"] = bundle_path


@when('the architect runs "spec-ops init --profile dist/fintech-service.sop"')
def when_run_init_with_bundle(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    target_repo = repo_context.get("target_repo", repo)
    res = run_spec_ops(target_repo, ["init", "--profile", str(repo_context["bundle_path"])])
    repo_context["result"] = res


@then('the custom organization ADRs are installed in "docs/project/adrs/accepted/"')
def then_adrs_installed(repo_context: dict[str, Any]):
    target = repo_context.get("target_repo", repo_context["repo"])
    adrs_dir = target / "docs" / "project" / "adrs" / "accepted"
    assert adrs_dir.is_dir()
    adr_files = [f.name for f in adrs_dir.glob("*.md")]
    assert any("audit-logging" in name for name in adr_files)


@then('the generated "AGENTS.md" incorporates the custom profile\'s specific compliance invariants')
@then('And the generated "AGENTS.md" incorporates the custom profile\'s specific compliance invariants')
def then_agents_md_has_invariants(repo_context: dict[str, Any]):
    target = repo_context.get("target_repo", repo_context["repo"])
    agents_md = target / "AGENTS.md"
    assert agents_md.is_file()
    content = agents_md.read_text(encoding="utf-8")
    assert "audit logs" in content.lower()


@then('"specops.toml" records the installed profile identifier and version.')
@then('And "specops.toml" records the installed profile identifier and version.')
def then_specops_records_profile(repo_context: dict[str, Any]):
    target = repo_context.get("target_repo", repo_context["repo"])
    toml_file = target / "specops.toml"
    assert toml_file.is_file()
    content = toml_file.read_text(encoding="utf-8")
    assert "fintech-service" in content
    assert "1.0.0" in content


@given('an architect attempts to initialize a project with profiles "core" and an invalid custom profile reusing "ADR-0001"')
def given_invalid_custom_profile(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    inv_dir = repo / "invalid-profile"
    inv_dir.mkdir(parents=True, exist_ok=True)
    (inv_dir / "profile.toml").write_text(
        """[profile]
id = "invalid-profile"
name = "Invalid Profile"
version = "0.1.0"
description = "Reuses ADR-0001 with conflicting title."
""",
        encoding="utf-8",
    )
    adrs_dir = inv_dir / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "adr-0001-conflicting.md").write_text(
        """---
id: '0001'
title: Conflicting Architecture Decision
status: Accepted
---
# ADR-0001: Conflicting Architecture Decision
""",
        encoding="utf-8",
    )


@when('the architect runs "spec-ops init --profile core,./invalid-profile"')
def when_run_init_with_conflict(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    target = repo / "conflict_target"
    target.mkdir(parents=True, exist_ok=True)
    res = run_spec_ops(target, ["init", "--profile", f"core,{repo / 'invalid-profile'}"])
    repo_context["result"] = res


@then("the command exits with code 1")
def then_exits_code_1(repo_context: dict[str, Any]):
    res = repo_context["result"]
    assert res.returncode == 1


@then('displays "Profile Error: Conflict detected for ADR-0001 between \'core\' and \'invalid-profile\'".')
@then('And displays "Profile Error: Conflict detected for ADR-0001 between \'core\' and \'invalid-profile\'".')
def then_displays_conflict(repo_context: dict[str, Any]):
    res = repo_context["result"]
    combined = res.stderr + "\n" + res.stdout
    assert "Profile Error: Conflict detected for ADR-0001 between 'core' and 'invalid-profile'" in combined
