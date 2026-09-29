"""Git pre-commit hook configuration scaffolding for SpecOps."""

from __future__ import annotations


def generate_pre_commit_config() -> str:
    """Generates an opinionated .pre-commit-config.yaml enforcing Ruff and SpecOps invariants."""
    return """# See https://pre-commit.com for more information
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.10
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: spec-ops-health
        name: SpecOps Invariant & Health Gate (<500 lines)
        entry: uv run spec-ops health
        language: system
        pass_filenames: false
        always_run: true
"""
