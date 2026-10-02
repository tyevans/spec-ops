"""Executable BDD acceptance tests for US-0124: Self-Contained GitHub Pages and Visualizer Scaffolding."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/us_0124_self_contained_pages.feature")

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
def repo_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "brownfield_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Devon"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "devon@example.com"], cwd=repo, check=True, capture_output=True)
    return {"repo": repo, "result": None}


# Scenario 1


@given('an existing brownfield project where SpecOps is not present in "pyproject.toml"')
def given_brownfield_project(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        """[project]
name = "brownfield-service"
version = "1.0.0"
dependencies = ["requests>=2.28.0"]
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "pyproject.toml"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: initial commit"], cwd=repo, check=True, capture_output=True)


@when('the migration engineer runs "spec-ops adopt --github-pages"')
def when_run_adopt_pages(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["adopt", "--github-pages", "--name", "brownfield-service"])
    repo_ctx["result"] = res


@then('".github/workflows/deploy-pages.yml" is scaffolded')
def then_pages_workflow_scaffolded(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    wf_file = repo / ".github" / "workflows" / "deploy-pages.yml"
    assert wf_file.is_file(), f"Expected {wf_file} to exist"


@then('the workflow invokes "uv tool run --from git+https://... spec-ops docs build" (or published PyPI tool)')
def then_workflow_invokes_uv_tool(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    wf_file = repo / ".github" / "workflows" / "deploy-pages.yml"
    content = wf_file.read_text(encoding="utf-8")
    assert "uv tool run --from git+https://" in content or "uv tool run spec-ops" in content
    assert "spec-ops docs build" in content


@then("builds cleanly in clean GitHub Actions runner environments without requiring in-repo dependency modifications.")
def then_clean_actions_no_lockfile(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    wf_file = repo / ".github" / "workflows" / "deploy-pages.yml"
    content = wf_file.read_text(encoding="utf-8")
    # In standalone mode, uv sync must not be required
    assert "run: uv sync" not in content


# Scenario 2


@given('a target repository with an existing documentation configuration (such as "mkdocs.yml" or ".github/workflows/docs.yml")')
def given_existing_doc_config(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    mkdocs = repo / "mkdocs.yml"
    mkdocs.write_text("site_name: LegacyDocs\nnav:\n  - Home: index.md\n", encoding="utf-8")

    wf_dir = repo / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    existing_wf = wf_dir / "docs.yml"
    existing_wf.write_text(
        """name: Documentation
on:
  push:
    branches: [main]
concurrency:
  group: pages
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/deploy-pages@v4
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: add legacy docs"], cwd=repo, check=True, capture_output=True)


@when('"spec-ops adopt" or "spec-ops scaffold ci" inspects the repository')
def when_inspect_repository(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["adopt", "--github-pages", "--name", "brownfield-service"])
    repo_ctx["result"] = res


@then("it detects the duplicate or conflicting Pages deployment workflow")
def then_detects_duplicate_workflow(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    assert res.returncode == 0
    output = res.stdout + res.stderr
    assert "conflicting" in output.lower() or "mkdocs" in output.lower()


@then("provides actionable guidance to bridge the living visualizer into the existing site or retire the legacy workflow.")
def then_provides_actionable_guidance(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    output = res.stdout + res.stderr
    assert "guidance" in output.lower() or "visualizer" in output.lower()


# Scenario 3


@given('the GitHub Pages site built by "spec-ops docs build"')
def given_site_built_by_docs_build(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    run_spec_ops(repo, ["init", "--name", "brownfield-service"])
    # Create sample doc page
    sample_doc = repo / "docs" / "tutorials" / "intro.md"
    sample_doc.parent.mkdir(parents=True, exist_ok=True)
    sample_doc.write_text("# Introduction\n\nWelcome to brownfield service.\n", encoding="utf-8")

    res = run_spec_ops(repo, ["docs", "build", "--base-url", "/brownfield-service/"])
    assert res.returncode == 0
    repo_ctx["result"] = res


@when("deployed to GitHub Pages")
def when_deployed_to_pages(repo_ctx: dict[str, Any]):
    # In test context, verify the built static site artifact ready for deploy
    repo = repo_ctx["repo"]
    assert (repo / "site").is_dir()


@then("the documentation root serves the Diataxis documentation portal")
def then_root_serves_diataxis(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    index_file = repo / "site" / "index.html"
    assert index_file.is_file()
    content = index_file.read_text(encoding="utf-8")
    assert "Documentation" in content


@then('the interactive 2D graph visualizer is available at "/visualizer/" with relationship graphs and burndown telemetry')
def then_visualizer_available(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    vis_file = repo / "site" / "visualizer" / "index.html"
    assert vis_file.is_file()


@then('every documentation page includes a header navigation link to "/visualizer/".')
def then_every_page_includes_visualizer_link(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    site_dir = repo / "site"
    html_files = [p for p in site_dir.rglob("*.html") if "visualizer" not in p.relative_to(site_dir).parts]
    assert len(html_files) > 0
    for hf in html_files:
        content = hf.read_text(encoding="utf-8")
        assert "/visualizer/" in content
        assert "visualizer-header-link" in content or "doc-header" in content
