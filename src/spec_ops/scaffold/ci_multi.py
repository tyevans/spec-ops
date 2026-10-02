"""Multi-platform CI/CD pipeline scaffolding across GitHub Actions and GitLab CI."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import textwrap
from typing import Any

import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore

DEFAULT_PYTHON_VERSIONS = ["3.12", "3.13"]
BEGIN_CUSTOM_ENV = "# BEGIN CUSTOM ENV"
END_CUSTOM_ENV = "# END CUSTOM ENV"
BEGIN_CUSTOM_STEPS = "# BEGIN CUSTOM STEPS"
END_CUSTOM_STEPS = "# END CUSTOM STEPS"


def extract_block(content: str, begin_tag: str, end_tag: str) -> str | None:
    """Extracts raw content enclosed between comment delimiter tags."""
    s = content.find(begin_tag)
    if s == -1:
        return None
    e = content.find(end_tag, s + len(begin_tag))
    if e == -1:
        return None
    inner = content[s + len(begin_tag) : e]
    return textwrap.dedent(inner).strip()


def extract_preserved_steps(content: str) -> str:
    """Extracts custom organizational steps enclosed in preservation tags or comments."""
    for b_tag, e_tag in [
        (BEGIN_CUSTOM_STEPS, END_CUSTOM_STEPS),
        ("# BEGIN CUSTOM", "# END CUSTOM"),
        ("# BEGIN PRESERVED", "# END PRESERVED"),
    ]:
        block = extract_block(content, b_tag, e_tag)
        if block:
            return block

    lines = content.splitlines()
    preserved_steps: list[str] = []
    in_preserved = False
    current_step: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- name:") or stripped.startswith("- uses:") or stripped.startswith("- run:"):
            if in_preserved and current_step:
                preserved_steps.extend(current_step)
            current_step = [line]
            in_preserved = "preserve" in line.lower() or "custom" in line.lower()
        elif current_step:
            if "preserve" in line.lower() or "custom" in line.lower():
                in_preserved = True
            current_step.append(line)
    if in_preserved and current_step:
        preserved_steps.extend(current_step)

    return "\n".join(preserved_steps).strip()


def extract_env_vars(content: str) -> dict[str, str]:
    """Extracts custom environment variables from existing workflow YAML."""
    vars_dict: dict[str, str] = {}
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            if isinstance(data.get("env"), dict):
                for k, v in data["env"].items():
                    vars_dict[str(k)] = str(v)
            jobs = data.get("jobs", {})
            if isinstance(jobs, dict):
                for job in jobs.values():
                    if isinstance(job, dict) and isinstance(job.get("env"), dict):
                        for k, v in job["env"].items():
                            vars_dict[str(k)] = str(v)
            variables = data.get("variables", {})
            if isinstance(variables, dict):
                for k, v in variables.items():
                    if k != "UV_CACHE_DIR":
                        vars_dict[str(k)] = str(v)
    except Exception:
        pass
    return vars_dict


def extract_custom_env(content: str) -> tuple[dict[str, str], str | None]:
    """Extracts structured and raw custom environment variables."""
    raw = extract_block(content, BEGIN_CUSTOM_ENV, END_CUSTOM_ENV)
    env_vars = extract_env_vars(content)
    return env_vars, raw


def resolve_python_versions(root_dir: Path, cli_matrix: str | None = None) -> list[str]:
    """Resolves target Python versions from CLI argument, specops.toml, or defaults."""
    if cli_matrix:
        versions = [v.strip() for v in cli_matrix.split(",") if v.strip()]
        if versions:
            return versions

    specops_toml = root_dir / "specops.toml"
    if specops_toml.is_file():
        try:
            data = tomllib.loads(specops_toml.read_text(encoding="utf-8"))
            for sec in ("project", "ci", "quality", "architecture"):
                sub = data.get(sec, {})
                if isinstance(sub, dict):
                    for key in ("target_python", "python_version", "supported_pythons", "python_versions", "matrix"):
                        if key in sub:
                            val = sub[key]
                            if isinstance(val, list):
                                res = [str(x).strip() for x in val if str(x).strip()]
                                if res:
                                    return res
                            if isinstance(val, str) and val.strip():
                                return [val.strip()]
        except Exception:
            pass

    return list(DEFAULT_PYTHON_VERSIONS)


def resolve_workflow_timeout(root_dir: Path, cli_timeout: int | None = None) -> int:
    """Resolves workflow job timeout-minutes from CLI, specops.toml, or default (15)."""
    if cli_timeout and cli_timeout > 0:
        return cli_timeout
    specops_toml = root_dir / "specops.toml"
    if specops_toml.is_file():
        try:
            data = tomllib.loads(specops_toml.read_text(encoding="utf-8"))
            for sec in ("ci", "project", "quality"):
                val = data.get(sec, {}).get("timeout_minutes", data.get(sec, {}).get("timeout"))
                if isinstance(val, int) and val > 0:
                    return val
        except Exception:
            pass
    return 15


def generate_github_ci_workflow(
    project_name: str = "SpecOps",
    python_versions: list[str] | None = None,
    custom_env: dict[str, Any] | None = None,
    raw_custom_env: str | None = None,
    custom_steps: str | None = None,
    timeout_minutes: int = 15,
) -> str:
    """Generates a GitHub Actions quality gate workflow with matrix testing and preservation seams."""
    py_versions = python_versions or list(DEFAULT_PYTHON_VERSIONS)
    matrix_json = json.dumps(py_versions)

    env_section = ""
    if custom_env:
        lines = ["env:"]
        for k, v in sorted(custom_env.items()):
            lines.append(f"  {json.dumps(str(k))}: {json.dumps(str(v))}")
        env_section = "\n".join(lines) + "\n"

    raw_env_content = f"\n{raw_custom_env}\n" if raw_custom_env else "\n"
    env_block = f"{BEGIN_CUSTOM_ENV}{raw_env_content}{END_CUSTOM_ENV}"

    steps_block = f"      {BEGIN_CUSTOM_STEPS}\n"
    if custom_steps and custom_steps.strip():
        dedented = textwrap.dedent(custom_steps.strip())
        indented = textwrap.indent(dedented, "      ")
        steps_block += f"{indented}\n"
    steps_block += f"      {END_CUSTOM_STEPS}"

    return f"""name: CI Quality Gate ({project_name})

"on":
  push:
    branches: [main]
  pull_request:
    branches: [main]

{env_section}{env_block}

jobs:
  specops-quality-gate:
    name: SpecOps Invariant & Health Check (Python ${{{{ matrix.python-version }}}})
    runs-on: ubuntu-latest
    timeout-minutes: {timeout_minutes}
    strategy:
      matrix:
        python-version: {matrix_json}

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          version: "latest"
          enable-cache: true

      - name: Set up Python ${{{{ matrix.python-version }}}}
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ matrix.python-version }}}}

      - name: Install dependencies
        run: uv sync

      - name: Verify dependency lockfile integrity
        run: uv lock --check

      - name: Verify SpecOps health & file length invariants (<500 lines)
        run: uv run spec-ops health

      - name: Execute blackbox test suite
        run: uv run pytest

{steps_block}
"""


def generate_gitlab_ci_workflow(
    project_name: str = "SpecOps",
    python_versions: list[str] | None = None,
    custom_env: dict[str, Any] | None = None,
    raw_custom_env: str | None = None,
    custom_steps: str | None = None,
) -> str:
    """Generates a GitLab CI quality gate workflow with matrix testing and persistent caching."""
    py_versions = python_versions or list(DEFAULT_PYTHON_VERSIONS)
    matrix_json = json.dumps(py_versions)

    cache_dir = custom_env.get("UV_CACHE_DIR", ".uv-cache/") if custom_env else ".uv-cache/"
    var_lines = ["variables:", f"  UV_CACHE_DIR: {json.dumps(str(cache_dir))}"]
    if custom_env:
        for k, v in sorted(custom_env.items()):
            if k == "UV_CACHE_DIR":
                continue
            var_lines.append(f"  {json.dumps(str(k))}: {json.dumps(str(v))}")
    var_section = "\n".join(var_lines)

    raw_env_content = f"\n{raw_custom_env}\n" if raw_custom_env else "\n"
    env_block = f"{BEGIN_CUSTOM_ENV}{raw_env_content}{END_CUSTOM_ENV}"

    steps_block = f"{BEGIN_CUSTOM_STEPS}\n"
    if custom_steps and custom_steps.strip():
        dedented = textwrap.dedent(custom_steps.strip())
        steps_block += f"{dedented}\n"
    steps_block += f"{END_CUSTOM_STEPS}"

    return f"""# GitLab CI Quality Gate ({project_name})
stages:
  - lint
  - health
  - test
  - security

{var_section}
{env_block}

cache:
  paths:
    - .uv-cache/

specops-lint:
  stage: lint
  image: python:3.13-slim
  before_script:
    - pip install uv
  script:
    - uv lock --check

specops-health:
  stage: health
  image: python:3.13-slim
  before_script:
    - pip install uv
    - uv sync
  script:
    - uv run spec-ops health

specops-test:
  stage: test
  image: python:${{PYTHON_VERSION}}-slim
  parallel:
    matrix:
      - PYTHON_VERSION: {matrix_json}
  before_script:
    - pip install uv
    - uv sync
  script:
    - uv run pytest

specops-security:
  stage: security
  image: python:3.13-slim
  before_script:
    - pip install uv
    - uv sync
  script:
    - uv run spec-ops health --security

{steps_block}
"""


def resolve_github_path(root_dir: Path) -> Path:
    """Resolves target GitHub Actions workflow path, preferring ci.yml if already present."""
    specops_path = root_dir / ".github" / "workflows" / "specops.yml"
    ci_path = root_dir / ".github" / "workflows" / "ci.yml"
    if ci_path.exists() and not specops_path.exists():
        return ci_path
    return specops_path


def scaffold_ci_command(
    root_dir: Path,
    platform: str = "all",
    force: bool = False,
    matrix: str | None = None,
    project_name: str = "SpecOps",
    timeout_minutes: int | None = None,
) -> int:
    """Executes CI workflow scaffolding across requested platforms with preservation support."""
    normalized_platform = platform.lower().strip()
    if normalized_platform not in ("github", "gitlab", "all"):
        print(f"❌ Error: Invalid platform '{platform}'. Choose from: github, gitlab, all.")
        return 1

    python_versions = resolve_python_versions(root_dir, matrix)
    timeout = resolve_workflow_timeout(root_dir, timeout_minutes)

    targets: list[tuple[str, Path]] = []
    if normalized_platform in ("github", "all"):
        gh_target = resolve_github_path(root_dir)
        targets.append(("github", gh_target))
        alt_ci = root_dir / ".github" / "workflows" / "ci.yml"
        if force and gh_target.name == "specops.yml" and alt_ci.exists():
            targets.append(("github", alt_ci))

    if normalized_platform in ("gitlab", "all"):
        targets.append(("gitlab", root_dir / ".gitlab-ci.yml"))

    if not force:
        for p_name, path in targets:
            if path.exists():
                try:
                    rel = path.relative_to(root_dir)
                except ValueError:
                    rel = path
                print(f"⚠️ Error: CI workflow manifest '{rel}' already exists. Use --force to overwrite.")
                return 1

    for p_name, path in targets:
        existing_text = path.read_text(encoding="utf-8") if path.exists() else None
        custom_env: dict[str, str] = {}
        raw_env: str | None = None
        custom_steps: str | None = None

        if existing_text:
            custom_env, raw_env = extract_custom_env(existing_text)
            custom_steps = extract_preserved_steps(existing_text)

        if p_name == "github":
            content = generate_github_ci_workflow(
                project_name=project_name,
                python_versions=python_versions,
                custom_env=custom_env,
                raw_custom_env=raw_env,
                custom_steps=custom_steps,
                timeout_minutes=timeout,
            )
        else:
            content = generate_gitlab_ci_workflow(
                project_name=project_name,
                python_versions=python_versions,
                custom_env=custom_env,
                raw_custom_env=raw_env,
                custom_steps=custom_steps,
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        try:
            rel = path.relative_to(root_dir)
        except ValueError:
            rel = path
        verb = "Updated" if existing_text is not None else "Generated"
        print(f"✨ {verb} {p_name.title()} CI workflow: {rel}")

    return 0
