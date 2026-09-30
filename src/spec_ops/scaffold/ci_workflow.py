"""GitHub Actions CI workflow scaffolding for SpecOps."""

from __future__ import annotations


def generate_ci_workflow(project_name: str = "SpecOps") -> str:
    """Generates an opinionated GitHub Actions CI quality gate workflow with targeted path filters."""
    return f"""name: CI Quality Gate ({project_name})

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: read

jobs:
  preflight-and-invariants:
    name: SpecOps Invariant & Health Check
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Detect file changes
        uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            lockfile:
              - 'uv.lock'
              - 'pyproject.toml'
              - '.github/workflows/ci.yml'
            artifacts:
              - 'docs/project/adrs/**'
              - 'docs/project/product/**'
              - 'docs/project/backlog/**'
              - 'docs/project/user_stories/**'
              - 'src/spec_ops/core/numbering.py'
              - '.github/workflows/ci.yml'
            health:
              - 'src/**'
              - 'tests/**'
              - 'spikes/**'
              - 'scripts/**'
              - '**/*.py'
              - '**/*.ts'
              - '**/*.js'
              - '**/*.html'
              - '**/*.css'
              - 'docs/project/backlog/**'
              - 'docs/project/adrs/**'
              - 'AGENTS.md'
              - 'specops.toml'
              - 'Makefile'
              - '.github/workflows/ci.yml'
            python:
              - 'src/**'
              - 'tests/**'
              - 'spikes/**'
              - 'scripts/**'
              - '**/*.py'
              - 'pyproject.toml'
              - 'uv.lock'
              - '.python-version'
              - 'specops.toml'
              - 'Makefile'
              - '.github/workflows/ci.yml'

      - name: Install uv
        if: steps.filter.outputs.lockfile == 'true' || steps.filter.outputs.artifacts == 'true' || steps.filter.outputs.health == 'true' || steps.filter.outputs.python == 'true'
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
          enable-cache: true

      - name: Set up Python
        if: steps.filter.outputs.artifacts == 'true' || steps.filter.outputs.health == 'true' || steps.filter.outputs.python == 'true'
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        if: steps.filter.outputs.artifacts == 'true' || steps.filter.outputs.health == 'true' || steps.filter.outputs.python == 'true'
        run: uv sync

      - name: Verify dependency lockfile integrity
        if: steps.filter.outputs.lockfile == 'true'
        run: uv lock --check

      - name: Verify artifact numbering uniqueness (ADRs, PRDs, Tasks, Stories)
        if: steps.filter.outputs.artifacts == 'true'
        run: uv run spec-ops health --numbering

      - name: Verify SpecOps health & file length invariants (<500 lines)
        if: steps.filter.outputs.health == 'true'
        run: uv run spec-ops health

      - name: Execute blackbox test suite
        if: steps.filter.outputs.python == 'true'
        run: uv run pytest
"""


def generate_gitlab_ci_workflow(project_name: str = "SpecOps") -> str:
    """Generates an opinionated GitLab CI quality gate workflow."""
    return f"""# GitLab CI Quality Gate ({project_name})
stages:
  - test

variables:
  UV_CACHE_DIR: .uv-cache/

cache:
  paths:
    - .uv-cache/

specops-quality-gate:
  stage: test
  image: python:3.13-slim
  before_script:
    - pip install uv
    - uv sync
  script:
    - uv lock --check
    - uv run spec-ops health --numbering
    - uv run spec-ops health
    - uv run pytest
"""
