"""Executable BDD acceptance tests for US-0125: Documentation Bridging and Deconfliction."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/us_0125_docs_deconfliction.feature")

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


@given('an existing brownfield repository containing "mkdocs.yml" or "docs/conf.py"')
def given_repo_with_mkdocs(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    (repo / "mkdocs.yml").write_text("site_name: TestSite\n", encoding="utf-8")
    subprocess.run(["git", "add", "mkdocs.yml"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add mkdocs"], cwd=repo, check=True, capture_output=True)


@when('the migration engineer runs "spec-ops adopt"')
def when_run_adopt(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["adopt", "--name", "test-project"])
    repo_ctx["result"] = res


@then("the command detects the existing documentation framework")
def then_detects_doc_framework(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    assert res.returncode == 0
    output = res.stdout + res.stderr
    assert "mkdocs" in output.lower() or "sphinx" in output.lower()


@then("prints informational warnings outlining bridging and co-existence options.")
def then_prints_bridging_options(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    output = res.stdout + res.stderr
    assert "bridging" in output.lower() or "visualizer" in output.lower()


# Scenario 2


@given('a target repository with an existing workflow deploying to GitHub Pages under concurrency group "pages"')
def given_existing_pages_wf(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    wf_dir = repo / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "docs.yml").write_text(
        """name: LegacyDocs
concurrency:
  group: "pages"
jobs:
  deploy:
    runs-on: ubuntu-latest
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: add workflow"], cwd=repo, check=True, capture_output=True)


@when('running "spec-ops adopt --github-pages"')
def when_run_adopt_pages(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["adopt", "--github-pages", "--name", "test-project"])
    repo_ctx["result"] = res


@then("it detects the duplicate Pages deployment configuration")
def then_detects_dup_pages(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    output = res.stdout + res.stderr
    assert "conflicting" in output.lower() or "pages" in output.lower()


@then("warns the user of the conflicting concurrency group")
def then_warns_concurrency(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    output = res.stdout + res.stderr
    assert "concurrency" in output.lower() or "collision" in output.lower()


@then('with "--deconflict-workflow" safely updates or namespaces the deployment workflow.')
def then_deconflict_workflow(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["adopt", "--github-pages", "--deconflict-workflow", "--name", "test-project"])
    assert res.returncode == 0
    # Verify the legacy workflow concurrency group was renamed
    legacy_wf = repo / ".github" / "workflows" / "docs.yml"
    content = legacy_wf.read_text(encoding="utf-8")
    assert "legacy-pages" in content


# Scenario 3


@given("a repository retaining an existing MkDocs documentation site")
def given_retaining_mkdocs(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    (repo / "mkdocs.yml").write_text("site_name: ExistingMkDocs\n", encoding="utf-8")
    subprocess.run(["git", "add", "mkdocs.yml"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: retain mkdocs"], cwd=repo, check=True, capture_output=True)


@when('running "spec-ops adopt --bridge-docs"')
def when_run_adopt_bridge(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["adopt", "--bridge-docs", "--name", "test-project"])
    repo_ctx["result"] = res


@then('SpecOps outputs configuration recommendations to link the "/visualizer/" route from the existing navigation')
def then_outputs_recommendations(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    output = res.stdout + res.stderr
    assert "/visualizer/" in output


@then("provides artifact co-location directives without pipeline conflicts.")
def then_provides_colocation_directives(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    output = res.stdout + res.stderr
    assert "co-locate" in output.lower() or "site/visualizer" in output.lower()
