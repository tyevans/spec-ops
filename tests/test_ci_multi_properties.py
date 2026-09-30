"""Hypothesis generative property tests for multi-platform CI/CD scaffolding (ADR-0009)."""

from __future__ import annotations

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.scaffold.ci_multi import (
    generate_github_ci_workflow,
    generate_gitlab_ci_workflow,
)


ALPHANUM_CHARS = st.characters(codec="ascii", whitelist_categories=("Ll", "Lu", "Nd"))
PROJECT_NAME_CHARS = st.characters(
    codec="ascii", whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters=("-", "_")
)
ENV_KEY_CHARS = st.characters(codec="ascii", whitelist_categories=("Lu",), whitelist_characters=("_"))


@settings(max_examples=40, deadline=None)
@given(
    project_name=st.text(PROJECT_NAME_CHARS, min_size=1, max_size=25),
    python_versions=st.lists(
        st.sampled_from(["3.10", "3.11", "3.12", "3.13", "3.14"]),
        min_size=1,
        max_size=4,
        unique=True,
    ),
    custom_env=st.dictionaries(
        st.text(ENV_KEY_CHARS, min_size=1, max_size=12),
        st.text(ALPHANUM_CHARS, min_size=1, max_size=20),
        max_size=4,
    ),
)
def test_github_ci_generative_manifest_schema_invariants(
    project_name: str,
    python_versions: list[str],
    custom_env: dict[str, str],
):
    """Asserts all generated GitHub Actions manifests parse as valid, strictly-typed schemas."""
    manifest = generate_github_ci_workflow(
        project_name=project_name,
        python_versions=python_versions,
        custom_env=custom_env,
    )

    parsed = yaml.safe_load(manifest)
    assert isinstance(parsed, dict)
    assert f"CI Quality Gate ({project_name})" in parsed["name"]
    assert "push" in parsed["on"]
    assert "pull_request" in parsed["on"]

    job = parsed["jobs"]["specops-quality-gate"]
    assert job["strategy"]["matrix"]["python-version"] == python_versions

    steps = job["steps"]
    step_runs = [s.get("run", "") for s in steps]
    assert any("uv lock --check" in r for r in step_runs)
    assert any("uv run spec-ops health" in r for r in step_runs)
    assert any("uv run pytest" in r for r in step_runs)

    if custom_env:
        assert "env" in parsed
        for k, v in custom_env.items():
            assert str(parsed["env"].get(k)) == str(v)


@settings(max_examples=40, deadline=None)
@given(
    project_name=st.text(PROJECT_NAME_CHARS, min_size=1, max_size=25),
    python_versions=st.lists(
        st.sampled_from(["3.10", "3.11", "3.12", "3.13", "3.14"]),
        min_size=1,
        max_size=4,
        unique=True,
    ),
    custom_env=st.dictionaries(
        st.text(ENV_KEY_CHARS, min_size=1, max_size=12),
        st.text(ALPHANUM_CHARS, min_size=1, max_size=20),
        max_size=4,
    ),
)
def test_gitlab_ci_generative_manifest_schema_invariants(
    project_name: str,
    python_versions: list[str],
    custom_env: dict[str, str],
):
    """Asserts all generated GitLab CI manifests parse as valid, strictly-typed schemas."""
    manifest = generate_gitlab_ci_workflow(
        project_name=project_name,
        python_versions=python_versions,
        custom_env=custom_env,
    )

    parsed = yaml.safe_load(manifest)
    assert isinstance(parsed, dict)
    assert parsed["stages"] == ["lint", "health", "test", "security"]
    assert parsed["variables"]["UV_CACHE_DIR"] == ".uv-cache/"
    assert parsed["cache"]["paths"] == [".uv-cache/"]

    test_job = parsed["specops-test"]
    assert test_job["stage"] == "test"
    assert test_job["parallel"]["matrix"][0]["PYTHON_VERSION"] == python_versions
    assert "uv run pytest" in test_job["script"]

    assert "uv lock --check" in parsed["specops-lint"]["script"]
    assert "uv run spec-ops health" in parsed["specops-health"]["script"]
    assert "uv run spec-ops health --security" in parsed["specops-security"]["script"]

    if custom_env:
        for k, v in custom_env.items():
            assert str(parsed["variables"].get(k)) == str(v)
