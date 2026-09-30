"""Executable BDD acceptance tests for US-0070: Architectural Profile Version Lifecycle, Semantic Diffs, and Invariant Migrations."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.profiles.registry import (
    CORE_ADR_0001,
    CORE_ADR_0002,
    CORE_ADR_0003,
    CORE_ADR_0004,
    CORE_ADR_0005,
    CORE_ADR_0008,
    CORE_PROFILE_V1,
    CORE_PROFILE_V2,
    get_profile,
    register_profile_release,
)

scenarios("features/us_0070_profile_version_lifecycle_semantic_diffs_migrations.feature")

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


def _initialize_core_v1_repo(repo: Path) -> None:
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)

    for adr in [CORE_ADR_0001, CORE_ADR_0002, CORE_ADR_0003, CORE_ADR_0004, CORE_ADR_0005]:
        (adrs_dir / adr.filename).write_text(adr.content, encoding="utf-8")

    registry_lines = [
        "# ADR Registry",
        "",
        "| ID | Title | Status | Date |",
        "|---|---|---|---|",
        "| ADR-0001 | Specification as Code and Opinionated SDLC Guardrails | Accepted | 2026-09-29 |",
        "| ADR-0002 | Modular Source File Length Limit (<500 Lines Anti-Rot Rule) | Accepted | 2026-09-29 |",
        "| ADR-0003 | Blackbox Frontdoor Verification and Zero Backdoor Testing | Accepted | 2026-09-29 |",
        "| ADR-0004 | Continuous Pre-flight Verification and Self-Healing CI Loops | Accepted | 2026-09-29 |",
        "| ADR-0005 | Git Worktree Concurrency and Strict Backlog Isolation | Accepted | 2026-09-29 |",
        "",
    ]
    (repo / "docs" / "project" / "adrs" / "REGISTRY.md").write_text("\n".join(registry_lines), encoding="utf-8")

    (repo / "specops.toml").write_text(
        """[project]
name = "demo-app"

[architecture]
file_length_limit = 500

[profiles]
installed = ["core@1.0.0"]
version = "1.0.0"
""",
        encoding="utf-8",
    )

    (repo / "AGENTS.md").write_text(
        """# SpecOps Agent Operating Manual

## Hard Invariants
1. **File Length Limit (<500 lines)**:
   Source files over ~500 lines are strictly forbidden.
""",
        encoding="utf-8",
    )


@given('a repository initialized with profile "core@1.0.0" recorded in "specops.toml"')
def given_repo_with_core_v1(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    _initialize_core_v1_repo(repo)


@given('a new upstream profile release "core@2.0.0" introducing an updated invariant and ADR')
def given_upstream_core_v2(repo_context: dict[str, Any]):
    # Ensure CORE_PROFILE_V2 is registered
    register_profile_release(CORE_PROFILE_V2, "2.0.0")


@when('the architect runs "spec-ops profiles diff core"')
def when_run_profiles_diff_core(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["profiles", "diff", "core"])
    repo_context["result"] = res


@then("the terminal outputs a semantic diff of newly added ADRs, modified invariant clauses, and configuration changes")
def then_outputs_semantic_diff(repo_context: dict[str, Any]):
    res = repo_context["result"]
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"
    out = res.stdout
    assert "ADR-0008" in out or "Generative Property-Based Testing" in out
    assert "Invariant Rules" in out or "invariants" in out.lower()
    assert "file_length_limit" in out


@then("highlights breaking changes (e.g. decreased file length limit or newly mandated mutation testing).")
@then("And highlights breaking changes (e.g. decreased file length limit or newly mandated mutation testing).")
def then_highlights_breaking_changes(repo_context: dict[str, Any]):
    res = repo_context["result"]
    out = res.stdout
    assert "BREAKING" in out
    assert "Decreased file length limit" in out or "350 lines" in out
    assert "mutation testing" in out


@given('a project configured with profile "core@1.0.0"')
def given_project_configured_core_v1(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    _initialize_core_v1_repo(repo)
    register_profile_release(CORE_PROFILE_V2, "2.0.0")


@when('the architect runs "spec-ops profiles upgrade core"')
def when_run_profiles_upgrade_core(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["profiles", "upgrade", "core"])
    repo_context["result"] = res


@then('then "specops.toml" is updated to "core@2.0.0"')
@then('"specops.toml" is updated to "core@2.0.0"')
def then_specops_updated_to_core_v2(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    toml_text = (repo / "specops.toml").read_text(encoding="utf-8")
    assert "core@2.0.0" in toml_text
    assert 'version = "2.0.0"' in toml_text


@then('new baseline ADR files are installed into "docs/project/adrs/accepted/" with sequential numbering')
@then('And new baseline ADR files are installed into "docs/project/adrs/accepted/" with sequential numbering')
def then_new_adrs_installed_sequentially(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"
    files = [f.name for f in adrs_dir.glob("*.md")]
    assert any("generative-property-and-mutation-testing" in f for f in files)


@then('"docs/project/adrs/REGISTRY.md" is updated atomically')
@then('And "docs/project/adrs/REGISTRY.md" is updated atomically')
def then_registry_updated_atomically(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    reg_text = (repo / "docs" / "project" / "adrs" / "REGISTRY.md").read_text(encoding="utf-8")
    assert "Generative Property-Based Testing and Mutation Testing" in reg_text


@then('"AGENTS.md" is re-synchronized to reflect the updated profile invariants.')
@then('And "AGENTS.md" is re-synchronized to reflect the updated profile invariants.')
def then_agents_md_resynchronized(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    agents_text = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "<350 lines" in agents_text
    assert "Generative Property-Based Testing" in agents_text


@given('a local project that has modified the content of installed "ADR-0002"')
def given_project_with_modified_adr2(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    _initialize_core_v1_repo(repo)
    register_profile_release(CORE_PROFILE_V2, "2.0.0")

    adr2_file = repo / "docs" / "project" / "adrs" / "accepted" / "adr-0002-modular-file-length-limits-anti-rot.md"
    adr2_content = adr2_file.read_text(encoding="utf-8")
    adr2_file.write_text(
        adr2_content + "\n## Local Exception\nWe allow legacy monolith module up to 800 lines.\n",
        encoding="utf-8",
    )


@when('the architect runs "spec-ops profiles upgrade core" without the force flag')
def when_run_upgrade_without_force(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["profiles", "upgrade", "core"])
    repo_context["result"] = res


@then('the migration pauses and flags a conflict for "ADR-0002"')
def then_migration_flags_conflict(repo_context: dict[str, Any]):
    res = repo_context["result"]
    combined = res.stdout + "\n" + res.stderr
    assert "ADR-0002" in combined
    assert "conflict" in combined.lower()


@then("prompts the architect to choose between keeping the local override, accepting upstream, or creating a custom ADR diff.")
@then("And prompts the architect to choose between keeping the local override, accepting upstream, or creating a custom ADR diff.")
def then_prompts_for_resolution(repo_context: dict[str, Any]):
    res = repo_context["result"]
    combined = res.stdout + "\n" + res.stderr
    assert "keep the local override" in combined.lower() or "keep-local" in combined.lower()
    assert "accepting upstream" in combined.lower() or "accept-upstream" in combined.lower()
    assert "custom adr diff" in combined.lower() or "custom-diff" in combined.lower() or "diff" in combined.lower()
