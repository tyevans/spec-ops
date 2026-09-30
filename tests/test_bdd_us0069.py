"""Executable BDD scenarios for US-0069: Multi-Platform CI/CD Pipeline Scaffolding."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0069_multi_platform_ci_pipeline_scaffolding.feature")


@pytest.fixture
def bdd_ci_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="CiTestApp", target_dir=repo)

    # Clean out any init-created workflows to test scaffolding cleanly
    gh_dir = repo / ".github"
    if gh_dir.exists():
        import shutil
        shutil.rmtree(gh_dir)
    gl_file = repo / ".gitlab-ci.yml"
    if gl_file.exists():
        gl_file.unlink()

    return {
        "repo": repo,
        "last_res": None,
    }


# ============================================================================
# Scenario: Scaffolding a GitLab CI quality pipeline
# ============================================================================


@given("a repository configured with SpecOps")
def repo_configured_with_specops(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    assert (repo / "specops.toml").is_file()


@when('the architect runs "spec-ops scaffold ci --platform gitlab"')
def run_scaffold_ci_gitlab(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "scaffold", "ci", "--platform", "gitlab"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_ci_context["last_res"] = res
    assert res.returncode == 0


@then('a ".gitlab-ci.yml" file is generated at the repository root')
def verify_gitlab_ci_generated(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    gl_file = repo / ".gitlab-ci.yml"
    assert gl_file.is_file()
    data = yaml.safe_load(gl_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "stages" in data
    stages = data["stages"]
    for expected_stage in ("lint", "health", "test", "security"):
        assert expected_stage in stages


@then('the pipeline includes stages for dependency lockfile validation ("uv lock --check"), invariant health scanning ("uv run spec-ops health"), and blackbox test execution ("uv run pytest")')
def verify_gitlab_ci_stages_content(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    content = (repo / ".gitlab-ci.yml").read_text(encoding="utf-8")
    assert "uv lock --check" in content
    assert "uv run spec-ops health" in content
    assert "uv run pytest" in content


@then("configures persistent caching for UV dependencies.")
def verify_gitlab_ci_caching(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    content = (repo / ".gitlab-ci.yml").read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert "cache" in data
    assert "UV_CACHE_DIR" in str(data.get("variables", {}))


# ============================================================================
# Scenario: Scaffolding multi-platform CI pipelines simultaneously
# ============================================================================


@given("a project needing both GitHub and GitLab pipeline configurations")
def project_needing_multi_platform(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    assert not (repo / ".github" / "workflows" / "specops.yml").exists()
    assert not (repo / ".gitlab-ci.yml").exists()


@when('"spec-ops scaffold ci --platform all" is executed')
def run_scaffold_ci_all(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "scaffold", "ci", "--platform", "all"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_ci_context["last_res"] = res
    assert res.returncode == 0


@then('both ".github/workflows/specops.yml" and ".gitlab-ci.yml" are written with matrix definitions')
def verify_both_workflows_with_matrix(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    gh_file = repo / ".github" / "workflows" / "specops.yml"
    gl_file = repo / ".gitlab-ci.yml"
    assert gh_file.is_file()
    assert gl_file.is_file()

    gh_data = yaml.safe_load(gh_file.read_text(encoding="utf-8"))
    assert "strategy" in str(gh_data)
    assert "matrix" in str(gh_data)

    gl_data = yaml.safe_load(gl_file.read_text(encoding="utf-8"))
    assert "matrix" in str(gl_data)


@then("both configurations execute the exact same sequence of quality checks and invariant gates.")
def verify_same_quality_checks(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    gh_content = (repo / ".github" / "workflows" / "specops.yml").read_text(encoding="utf-8")
    gl_content = (repo / ".gitlab-ci.yml").read_text(encoding="utf-8")

    for check in ("uv lock --check", "uv run spec-ops health", "uv run pytest"):
        assert check in gh_content
        assert check in gl_content


# ============================================================================
# Scenario: Updating existing CI workflow on toolchain version bump
# ============================================================================


@given('an existing ".github/workflows/specops.yml"')
def existing_specops_workflow(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    wf_dir = repo / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    initial_content = """name: CI Quality Gate (OldApp)
on: [push]
env:
  ORG_METRICS_KEY: "secret-token-123"
  CUSTOM_TEAM_ENV: "frontend-eng"
jobs:
  specops-quality-gate:
    runs-on: ubuntu-latest
    steps:
      - name: Old checkout
        uses: actions/checkout@v3
"""
    (wf_dir / "specops.yml").write_text(initial_content, encoding="utf-8")


@when('the developer runs "spec-ops scaffold ci --platform github --force"')
def run_scaffold_ci_github_force(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "scaffold", "ci", "--platform", "github", "--force"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_ci_context["last_res"] = res
    assert res.returncode == 0


@then("workflow steps are updated with latest toolchain actions while preserving custom environment variables.")
def verify_updated_toolchain_and_preserved_env(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    content = (repo / ".github" / "workflows" / "specops.yml").read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    assert "setup-uv@v5" in content
    assert "actions/checkout@v4" in content
    assert "env" in data
    assert data["env"].get("ORG_METRICS_KEY") == "secret-token-123"
    assert data["env"].get("CUSTOM_TEAM_ENV") == "frontend-eng"


# ============================================================================
# Scenario: Updating existing CI workflow with preservation tags
# ============================================================================


@given('an existing ".github/workflows/ci.yml" generated with Python 3.12')
def existing_ci_workflow_python_312(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    wf_dir = repo / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    content = """name: CI Quality Gate (Legacy)
on: [push]
jobs:
  specops-quality-gate:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12"]
    steps:
      - uses: actions/checkout@v4
      # BEGIN CUSTOM STEPS
      - name: Slack notifications for failure
        run: ./scripts/notify_slack.sh
      # END CUSTOM STEPS
"""
    (wf_dir / "ci.yml").write_text(content, encoding="utf-8")


@when('the engineer updates "specops.toml" to target Python 3.13 and runs "spec-ops scaffold ci --update"')
def update_specops_toml_and_run_scaffold(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    toml_path = repo / "specops.toml"
    content = toml_path.read_text(encoding="utf-8")
    if "[project]" in content:
        content = content.replace("[project]", '[project]\ntarget_python = "3.13"')
    else:
        content += '\n[project]\ntarget_python = "3.13"\n'
    toml_path.write_text(content, encoding="utf-8")

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "scaffold", "ci", "--update"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_ci_context["last_res"] = res
    assert res.returncode == 0


@then("the CI workflow file is updated to Python 3.13 without removing custom organizational job steps marked with preservation tags.")
def verify_workflow_updated_with_custom_steps(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    ci_file = repo / ".github" / "workflows" / "ci.yml"
    assert ci_file.is_file()
    content = ci_file.read_text(encoding="utf-8")

    assert "3.13" in content
    assert "Slack notifications for failure" in content
    assert "./scripts/notify_slack.sh" in content


# ============================================================================
# Scenario: Attempting to overwrite existing CI workflow without force flag
# ============================================================================


@when('the developer runs "spec-ops scaffold ci --platform github" without force')
def run_scaffold_ci_without_force(bdd_ci_context: dict[str, Any]):
    repo: Path = bdd_ci_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "scaffold", "ci", "--platform", "github"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_ci_context["last_res"] = res


@then("the command fails with exit code 1 and warns that the file already exists.")
def verify_command_aborts_with_code_1(bdd_ci_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_ci_context["last_res"]
    assert res.returncode == 1
    assert "already exists" in res.stdout or "already exists" in res.stderr
