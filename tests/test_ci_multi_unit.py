"""Unit tests for multi-platform CI/CD scaffolding (ci_multi.py)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from spec_ops.scaffold.ci_multi import (
    DEFAULT_PYTHON_VERSIONS,
    extract_block,
    extract_custom_env,
    extract_env_vars,
    extract_preserved_steps,
    generate_github_ci_workflow,
    generate_gitlab_ci_workflow,
    resolve_github_path,
    resolve_python_versions,
    scaffold_ci_command,
)


def test_extract_block():
    text = "prefix\n# BEGIN TEST\nhello world\n# END TEST\nsuffix"
    assert extract_block(text, "# BEGIN TEST", "# END TEST") == "hello world"
    assert extract_block(text, "# MISSING", "# END TEST") is None
    assert extract_block(text, "# BEGIN TEST", "# MISSING") is None


def test_extract_preserved_steps_tags():
    text = """
    steps:
      # BEGIN CUSTOM STEPS
      - name: Custom Step
        run: echo 1
      # END CUSTOM STEPS
    """
    assert extract_preserved_steps(text) == "- name: Custom Step\n  run: echo 1"


def test_extract_preserved_steps_comments():
    text = """
    steps:
      - name: Regular Step
        run: echo 0
      - name: Preserve Step
        # preserve this
        run: echo 1
    """
    res = extract_preserved_steps(text)
    assert "- name: Preserve Step" in res
    assert "echo 1" in res
    assert "Regular Step" not in res


def test_extract_preserved_steps_empty():
    assert extract_preserved_steps("random text without steps") == ""


def test_extract_env_vars():
    gh_yaml = """
    name: Test
    env:
      FOO: "bar"
    jobs:
      test:
        env:
          BAZ: "qux"
    """
    vars_dict = extract_env_vars(gh_yaml)
    assert vars_dict.get("FOO") == "bar"
    assert vars_dict.get("BAZ") == "qux"

    gl_yaml = """
    variables:
      UV_CACHE_DIR: .uv-cache/
      MY_VAR: "val"
    """
    gl_vars = extract_env_vars(gl_yaml)
    assert gl_vars.get("MY_VAR") == "val"
    assert "UV_CACHE_DIR" not in gl_vars

    assert extract_env_vars("invalid: [yaml: :") == {}
    assert extract_env_vars("a string") == {}


def test_extract_custom_env():
    text = """
    # BEGIN CUSTOM ENV
    MY_RAW_ENV: true
    # END CUSTOM ENV
    env:
      API_KEY: "secret"
    """
    env_vars, raw = extract_custom_env(text)
    assert env_vars.get("API_KEY") == "secret"
    assert raw == "MY_RAW_ENV: true"


def test_resolve_python_versions(tmp_path: Path):
    assert resolve_python_versions(tmp_path, "3.11,3.12") == ["3.11", "3.12"]
    assert resolve_python_versions(tmp_path, "") == DEFAULT_PYTHON_VERSIONS

    # With specops.toml string target
    (tmp_path / "specops.toml").write_text('[project]\ntarget_python = "3.13"\n', encoding="utf-8")
    assert resolve_python_versions(tmp_path) == ["3.13"]

    # With specops.toml list matrix
    (tmp_path / "specops.toml").write_text('[ci]\nmatrix = ["3.11", "3.12"]\n', encoding="utf-8")
    assert resolve_python_versions(tmp_path) == ["3.11", "3.12"]

    # Empty list falls back to default
    (tmp_path / "specops.toml").write_text('[ci]\nmatrix = []\n', encoding="utf-8")
    assert resolve_python_versions(tmp_path) == DEFAULT_PYTHON_VERSIONS


def test_resolve_github_path(tmp_path: Path):
    # Neither exists
    res = resolve_github_path(tmp_path)
    assert res == tmp_path / ".github" / "workflows" / "specops.yml"

    # Only ci.yml exists
    ci_file = tmp_path / ".github" / "workflows" / "ci.yml"
    ci_file.parent.mkdir(parents=True, exist_ok=True)
    ci_file.write_text("dummy", encoding="utf-8")
    assert resolve_github_path(tmp_path) == ci_file

    # Both exist -> prefers specops.yml
    specops_file = tmp_path / ".github" / "workflows" / "specops.yml"
    specops_file.write_text("dummy", encoding="utf-8")
    assert resolve_github_path(tmp_path) == specops_file


def test_scaffold_ci_command_invalid_platform(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rc = scaffold_ci_command(tmp_path, platform="bitbucket")
    assert rc == 1
    assert "Invalid platform" in capsys.readouterr().out


def test_scaffold_ci_command_already_exists_without_force(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    gl_file = tmp_path / ".gitlab-ci.yml"
    gl_file.write_text("existing", encoding="utf-8")

    rc = scaffold_ci_command(tmp_path, platform="gitlab", force=False)
    assert rc == 1
    assert "already exists. Use --force" in capsys.readouterr().out


def test_scaffold_ci_command_all_platforms(tmp_path: Path):
    rc = scaffold_ci_command(tmp_path, platform="all", force=False)
    assert rc == 0

    gh_file = tmp_path / ".github" / "workflows" / "specops.yml"
    gl_file = tmp_path / ".gitlab-ci.yml"
    assert gh_file.is_file()
    assert gl_file.is_file()


def test_scaffold_ci_command_preserves_custom_content(tmp_path: Path):
    gh_dir = tmp_path / ".github" / "workflows"
    gh_dir.mkdir(parents=True, exist_ok=True)
    orig_gh = """name: Old
env:
  MY_SECRET: "token123"
jobs:
  specops-quality-gate:
    runs-on: ubuntu-latest
    steps:
      # BEGIN CUSTOM STEPS
      - name: Deploy
        run: ./deploy.sh
      # END CUSTOM STEPS
"""
    (gh_dir / "specops.yml").write_text(orig_gh, encoding="utf-8")

    rc = scaffold_ci_command(tmp_path, platform="github", force=True)
    assert rc == 0

    new_content = (gh_dir / "specops.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(new_content)
    assert parsed["env"]["MY_SECRET"] == "token123"
    assert "Deploy" in new_content
    assert "./deploy.sh" in new_content


def test_extract_preserved_steps_alternative_tags():
    text1 = """
    # BEGIN CUSTOM
    - name: Alt Step
      run: echo alt
    # END CUSTOM
    """
    assert extract_preserved_steps(text1) == "- name: Alt Step\n  run: echo alt"

    text2 = """
    # BEGIN PRESERVED
    - name: Preserved Step
      run: echo pres
    # END PRESERVED
    """
    assert extract_preserved_steps(text2) == "- name: Preserved Step\n  run: echo pres"


def test_scaffold_ci_command_gitlab_preservation(tmp_path: Path):
    gl_file = tmp_path / ".gitlab-ci.yml"
    orig_gl = """# GitLab
variables:
  UV_CACHE_DIR: .uv-cache/
  MY_CI_VAR: "prod_val"
# BEGIN CUSTOM ENV
RAW_ENV_KEY: 99
# END CUSTOM ENV
# BEGIN CUSTOM STEPS
custom-job:
  script: echo "custom"
# END CUSTOM STEPS
"""
    gl_file.write_text(orig_gl, encoding="utf-8")

    rc = scaffold_ci_command(tmp_path, platform="gitlab", force=True)
    assert rc == 0

    new_gl = gl_file.read_text(encoding="utf-8")
    parsed = yaml.safe_load(new_gl)
    assert parsed["variables"]["MY_CI_VAR"] == "prod_val"
    assert "RAW_ENV_KEY: 99" in new_gl
    assert "custom-job:" in new_gl


def test_scaffold_ci_command_updates_both_ci_and_specops_when_forced(tmp_path: Path):
    gh_dir = tmp_path / ".github" / "workflows"
    gh_dir.mkdir(parents=True, exist_ok=True)
    (gh_dir / "specops.yml").write_text("old specops", encoding="utf-8")
    (gh_dir / "ci.yml").write_text("old ci", encoding="utf-8")

    rc = scaffold_ci_command(tmp_path, platform="github", force=True)
    assert rc == 0

    assert "CI Quality Gate" in (gh_dir / "specops.yml").read_text(encoding="utf-8")
    assert "CI Quality Gate" in (gh_dir / "ci.yml").read_text(encoding="utf-8")


def test_resolve_python_versions_malformed_toml(tmp_path: Path):
    (tmp_path / "specops.toml").write_text("malformed toml [[[", encoding="utf-8")
    assert resolve_python_versions(tmp_path) == DEFAULT_PYTHON_VERSIONS

