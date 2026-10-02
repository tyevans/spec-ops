"""Unit tests for CI workflow targeting and path-filter configuration."""

from __future__ import annotations

from pathlib import Path
import yaml

from spec_ops.scaffold.ci_workflow import generate_ci_workflow, generate_gitlab_ci_workflow


def test_repo_ci_workflow_yaml_is_valid():
    """Verify that .github/workflows/ci.yml parses as valid YAML."""
    ci_file = Path(".github/workflows/ci.yml")
    assert ci_file.is_file()

    content = ci_file.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert data["name"] == "CI Quality Gate (SpecOps)"

    steps = data["jobs"]["preflight-and-invariants"]["steps"]
    step_names = [s.get("name") for s in steps]

    assert "Detect file changes" in step_names
    assert "Verify dependency lockfile integrity" in step_names
    assert "Verify artifact numbering uniqueness (ADRs, PRDs, Tasks, Stories)" in step_names
    assert "Verify SpecOps health & file length invariants (<500 lines)" in step_names
    assert "Execute blackbox test suite" in step_names


def test_repo_ci_workflow_has_targeted_filters():
    """Verify that .github/workflows/ci.yml defines targeted filters for all CI steps."""
    ci_file = Path(".github/workflows/ci.yml")
    content = ci_file.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    steps = data["jobs"]["preflight-and-invariants"]["steps"]
    filter_step = next(s for s in steps if s.get("id") == "filter")

    assert filter_step["uses"] == "dorny/paths-filter@v3"
    filters = yaml.safe_load(filter_step["with"]["filters"])

    # Lockfile filter
    assert "uv.lock" in filters["lockfile"]
    assert "pyproject.toml" in filters["lockfile"]

    # Artifacts filter (ADRs, PRDs, Tasks, Stories)
    assert "docs/project/adrs/**" in filters["artifacts"]
    assert "docs/project/product/**" in filters["artifacts"]
    assert "docs/project/backlog/**" in filters["artifacts"]
    assert "docs/project/user_stories/**" in filters["artifacts"]

    # Health filter
    assert "src/**" in filters["health"]
    assert "tests/**" in filters["health"]
    assert "docs/project/backlog/**" in filters["health"]
    assert "docs/project/adrs/**" in filters["health"]
    assert "AGENTS.md" in filters["health"]

    # Python test filter
    assert "src/**" in filters["python"]
    assert "tests/**" in filters["python"]
    assert "**/*.py" in filters["python"]
    assert "pyproject.toml" in filters["python"]
    assert "uv.lock" in filters["python"]
    assert ".python-version" in filters["python"]
    assert "specops.toml" in filters["python"]


def test_repo_ci_workflow_step_conditions():
    """Verify that steps in ci.yml are conditionally guarded by path filter outputs."""
    ci_file = Path(".github/workflows/ci.yml")
    content = ci_file.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    steps = data["jobs"]["preflight-and-invariants"]["steps"]
    step_by_name = {s.get("name"): s for s in steps}

    lock_step = step_by_name["Verify dependency lockfile integrity"]
    assert "steps.filter.outputs.lockfile == 'true'" in lock_step["if"]

    num_step = step_by_name["Verify artifact numbering uniqueness (ADRs, PRDs, Tasks, Stories)"]
    assert "steps.filter.outputs.artifacts == 'true'" in num_step["if"]

    health_step = step_by_name["Verify SpecOps health & file length invariants (<500 lines)"]
    assert "steps.filter.outputs.health == 'true'" in health_step["if"]

    test_step = step_by_name["Execute blackbox test suite"]
    assert "steps.filter.outputs.python == 'true'" in test_step["if"]


def test_generate_ci_workflow_scaffolding():
    """Verify that generate_ci_workflow produces identical targeted structure."""
    generated = generate_ci_workflow("CustomProject")
    data = yaml.safe_load(generated)
    assert data["name"] == "CI Quality Gate (CustomProject)"

    steps = data["jobs"]["preflight-and-invariants"]["steps"]
    step_by_name = {s.get("name"): s for s in steps}

    assert "Detect file changes" in step_by_name
    filter_step = step_by_name["Detect file changes"]
    assert filter_step["uses"] == "dorny/paths-filter@v3"

    assert "steps.filter.outputs.python == 'true'" in step_by_name["Execute blackbox test suite"]["if"]


def test_generate_gitlab_ci_workflow_valid_yaml():
    """Verify that generate_gitlab_ci_workflow produces valid YAML."""
    gitlab_yaml = generate_gitlab_ci_workflow("CustomProject")
    data = yaml.safe_load(gitlab_yaml)
    assert "specops-quality-gate" in data
    assert "stages" in data


def test_generate_ci_workflow_has_explicit_timeout():
    from spec_ops.scaffold.ci_workflow import generate_ci_workflow

    # Default timeout
    default_wf = yaml.safe_load(generate_ci_workflow("ProjectA"))
    assert default_wf["jobs"]["preflight-and-invariants"]["timeout-minutes"] == 15

    # Custom timeout
    custom_wf = yaml.safe_load(generate_ci_workflow("ProjectB", timeout_minutes=45))
    assert custom_wf["jobs"]["preflight-and-invariants"]["timeout-minutes"] == 45


def test_generate_pages_workflow_has_explicit_timeout():
    from spec_ops.scaffold.pages_workflow import generate_pages_workflow

    # Default timeout
    default_pages = yaml.safe_load(generate_pages_workflow("ProjectA"))
    assert default_pages["jobs"]["deploy-pages"]["timeout-minutes"] == 15

    # Custom timeout
    custom_pages = yaml.safe_load(generate_pages_workflow("ProjectB", timeout_minutes=25))
    assert custom_pages["jobs"]["deploy-pages"]["timeout-minutes"] == 25


def test_every_scaffolded_github_workflow_job_has_explicit_timeout():
    """Governance audit: Assert that every job in all generated GitHub Actions workflows has timeout-minutes."""
    from spec_ops.scaffold.ci_multi import generate_github_ci_workflow
    from spec_ops.scaffold.ci_workflow import generate_ci_workflow
    from spec_ops.scaffold.pages_workflow import generate_pages_workflow

    workflows = [
        generate_ci_workflow("TestApp"),
        generate_pages_workflow("TestApp"),
        generate_github_ci_workflow("TestApp"),
    ]

    for wf_str in workflows:
        parsed = yaml.safe_load(wf_str)
        jobs = parsed.get("jobs", {})
        assert len(jobs) > 0
        for job_id, job_def in jobs.items():
            assert "timeout-minutes" in job_def, f"Job '{job_id}' missing timeout-minutes in workflow:\n{wf_str}"
            assert isinstance(job_def["timeout-minutes"], int)
            assert job_def["timeout-minutes"] > 0

