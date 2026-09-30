"""GitHub Actions CI workflow scaffolding for SpecOps."""

from __future__ import annotations


def generate_ci_workflow(project_name: str = "SpecOps") -> str:
    """Generates an opinionated GitHub Actions CI quality gate workflow."""
    return f"""name: CI Quality Gate ({project_name})

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  preflight-and-invariants:
    name: SpecOps Invariant & Health Check
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
          enable-cache: true

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: uv sync

      - name: Verify dependency lockfile integrity
        run: uv lock --check

      - name: Verify artifact numbering uniqueness (ADRs, PRDs, Tasks, Stories)
        run: uv run spec-ops health --numbering

      - name: Verify SpecOps health & file length invariants (<500 lines)
        run: uv run spec-ops health

      - name: Execute blackbox test suite
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

