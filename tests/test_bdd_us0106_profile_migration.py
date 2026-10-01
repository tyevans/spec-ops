"""Executable BDD acceptance tests for US-0106: Profile Schema Migration and Version Evolvability."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when
import yaml

scenarios("features/us_0106_profile_migration.feature")

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


@given("a project configured with a legacy v1 profile.yaml")
def project_with_legacy_v1_profile(repo_context: dict[str, Any]) -> None:
    repo = repo_context["repo"]
    spec_ops_dir = repo / ".spec-ops"
    spec_ops_dir.mkdir(parents=True, exist_ok=True)
    profile_file = spec_ops_dir / "profile.yaml"

    content = """---
profile: core
version: 1.0.0
file_length_limit: 450
custom_rules:
  - no-unauthorized-db-access
  - strict-bounded-context-coupling
rule_extensions:
  security:
    allow_signed_only: true
custom_metadata:
  team: agentic-architecture
---
# Architecture Profile Configuration
# Body markdown section preserved
"""
    profile_file.write_text(content, encoding="utf-8")


@when("the developer runs spec-ops profile migrate")
def run_profile_migrate(repo_context: dict[str, Any]) -> None:
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["profile", "migrate"])
    repo_context["result"] = res


@then("the configuration is upgraded to the current schema version")
def verify_schema_upgraded(repo_context: dict[str, Any]) -> None:
    res = repo_context["result"]
    assert res.returncode == 0, f"Expected returncode 0, got {res.returncode}. Output:\n{res.stderr}\n{res.stdout}"

    profile_file = repo_context["repo"] / ".spec-ops" / "profile.yaml"
    assert profile_file.exists()

    content = profile_file.read_text(encoding="utf-8")
    assert "schema_version: '2.0.0'" in content or 'schema_version: "2.0.0"' in content or "schema_version: 2.0.0" in content

    # Verify via YAML parser
    raw_yaml = content
    if content.startswith("---"):
        parts = content.split("---")
        if len(parts) >= 3:
            raw_yaml = parts[1]
    data = yaml.safe_load(raw_yaml)
    assert data["schema_version"] == "2.0.0"
    assert "profiles" in data
    assert "core" in data["profiles"]
    assert data.get("overrides", {}).get("file_length_limit") == 450


@then("all custom project rules and frontmatter settings are preserved intact")
def verify_custom_rules_preserved(repo_context: dict[str, Any]) -> None:
    profile_file = repo_context["repo"] / ".spec-ops" / "profile.yaml"
    content = profile_file.read_text(encoding="utf-8")

    raw_yaml = content
    if content.startswith("---"):
        parts = content.split("---")
        if len(parts) >= 3:
            raw_yaml = parts[1]
            body = parts[2]
            assert "Architecture Profile Configuration" in body
            assert "Body markdown section preserved" in body

    data = yaml.safe_load(raw_yaml)
    assert data["custom_rules"] == [
        "no-unauthorized-db-access",
        "strict-bounded-context-coupling",
    ]
    assert data["rule_extensions"]["security"]["allow_signed_only"] is True
    assert data["custom_metadata"]["team"] == "agentic-architecture"


@given("a project profile already synchronized with the current schema")
def project_with_current_schema_profile(repo_context: dict[str, Any]) -> None:
    repo = repo_context["repo"]
    spec_ops_dir = repo / ".spec-ops"
    spec_ops_dir.mkdir(parents=True, exist_ok=True)
    profile_file = spec_ops_dir / "profile.yaml"

    content = """schema_version: '2.0.0'
profiles:
  - core
overrides:
  file_length_limit: 500
custom_rules:
  - no-bypassing-frontdoor
"""
    profile_file.write_text(content, encoding="utf-8")


@when("the developer runs spec-ops profile migrate with check flag")
def run_profile_migrate_check(repo_context: dict[str, Any]) -> None:
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["profile", "migrate", "--check"])
    repo_context["result"] = res


@then("the command confirms profile is up to date")
def verify_command_confirms_up_to_date(repo_context: dict[str, Any]) -> None:
    res = repo_context["result"]
    assert "up to date" in res.stdout.lower() or "up to date" in res.stderr.lower()


@then("terminates with exit code 0")
def verify_exit_code_zero(repo_context: dict[str, Any]) -> None:
    res = repo_context["result"]
    assert res.returncode == 0, f"Expected 0, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"
