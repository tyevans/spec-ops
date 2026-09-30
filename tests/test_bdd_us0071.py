"""Executable BDD acceptance tests for US-0071: Bounded-Context Diataxis Documentation Scaffolding."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/us_0071_bounded_context_diataxis_scaffolding.feature")

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
def repo_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sample_repo(repo)
    return {"repo": repo, "result": None, "original_content": {}}


def _init_sample_repo(repo: Path) -> None:
    (repo / "specops.toml").write_text(
        """[project]
name = "DemoSystem"

[architecture]
file_length_limit = 500

[architecture.bounded_contexts]
billing = {}
""",
        encoding="utf-8",
    )

    (repo / "AGENTS.md").write_text(
        """# SpecOps Agent Operating Manual
## Hard Invariants
1. File Length Limit (<500 lines)
""",
        encoding="utf-8",
    )

    docs_dir = repo / "docs"
    for q in ["tutorials", "how-to", "reference", "explanation"]:
        (docs_dir / q).mkdir(parents=True, exist_ok=True)
        (docs_dir / q / "overview.md").write_text(f"# {q.title()} Overview\n", encoding="utf-8")

    (docs_dir / "index.md").write_text(
        """# DemoSystem Documentation

Welcome to DemoSystem.

## Living 2D Graph Visualizer
👉 **[Launch Interactive 2D Graph Visualizer](visualizer/)**
""",
        encoding="utf-8",
    )

    (docs_dir / "reference" / "cli.md").write_text(
        """# CLI Reference
| Command | Arguments | Description |
|---|---|---|
| `spec-ops init` | None | Init |
""",
        encoding="utf-8",
    )

    stories_dir = docs_dir / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "project" / "user_stories" / "PERSONAS.md").write_text("# Personas\n", encoding="utf-8")
    (stories_dir / "us-0071-billing.md").write_text("# US-0071: Billing\n", encoding="utf-8")


@given("an active SpecOps repository with bounded contexts")
def given_active_repo(repo_context: dict[str, Any]):
    assert (repo_context["repo"] / "specops.toml").exists()


@when(parsers.parse('the developer executes "{cmd}"'))
def when_developer_executes(repo_context: dict[str, Any], cmd: str):
    import shlex
    tokens = shlex.split(cmd)
    args = tokens[1:]
    res = run_spec_ops(repo_context["repo"], args)
    repo_context["result"] = res


@then("documentation directories are created with boilerplate index files across all four Diataxis quadrants")
def then_quadrant_dirs_created(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    assert (repo / "docs" / "tutorials" / "billing" / "index.md").exists()
    assert (repo / "docs" / "how-to" / "billing" / "index.md").exists()
    assert (repo / "docs" / "reference" / "billing" / "index.md").exists()
    assert (repo / "docs" / "explanation" / "billing" / "index.md").exists()
    assert (repo / "docs" / "explanation" / "billing" / "architecture.md").exists()


@then("starter markdown templates are installed with metadata linking to governing PRDs and user stories")
def then_starter_templates_installed(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    ref_md = (repo / "docs" / "reference" / "billing" / "index.md").read_text(encoding="utf-8")
    assert "bounded_context: \"billing\"" in ref_md
    assert "governing_prd: \"PRD-0005\"" in ref_md
    assert "governing_story: \"US-0071\"" in ref_md
    assert "PRD Catalog" in ref_md
    assert "User Stories" in ref_md


@then('the main documentation index "docs/index.md" is updated with a section for the new bounded context.')
def then_index_md_updated(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    index_md = (repo / "docs" / "index.md").read_text(encoding="utf-8")
    assert "## Bounded Contexts" in index_md
    assert "billing" in index_md
    assert "tutorials/billing/index.md" in index_md
    assert "how-to/billing/index.md" in index_md
    assert "reference/billing/index.md" in index_md
    assert "explanation/billing/index.md" in index_md


@given("scaffolded bounded-context documentation")
def given_scaffolded_docs(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["scaffold", "docs", "--bc", "billing", "--title", "Billing Subsystem"])
    assert res.returncode == 0


@when("viewing the generated reference documents")
def when_viewing_reference(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    ref_md = (repo / "docs" / "reference" / "billing" / "index.md").read_text(encoding="utf-8")
    repo_context["ref_md"] = ref_md


@then("markdown files include URL hash deep links targeting the bounded context in the 2D visualizer")
def then_markdown_includes_hash_deep_links(repo_context: dict[str, Any]):
    ref_md = repo_context.get("ref_md")
    if not ref_md:
        repo = repo_context["repo"]
        ref_md = (repo / "docs" / "reference" / "billing" / "index.md").read_text(encoding="utf-8")
    assert "#tab=canvas&focus=billing" in ref_md


@when('the builder compiles documentation with "spec-ops docs build"')
def when_builder_compiles(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["docs", "build"])
    assert res.returncode == 0


@then(
    parsers.parse(
        'the rendered HTML page includes an embedded interactive link to the visualizer pre-filtered to the "{bc}" component ("{expected_link}")'
    )
)
def then_rendered_html_includes_deep_link(
    repo_context: dict[str, Any], bc: str, expected_link: str
):
    repo = repo_context["repo"]
    arch_html_path = repo / "site" / "explanation" / bc / "architecture.html"
    assert arch_html_path.exists()
    content = arch_html_path.read_text(encoding="utf-8")
    assert expected_link in content


@then('verifies that all internal cross-links to user stories in "docs/project/user_stories/" resolve cleanly.')
def then_verify_internal_cross_links(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    arch_md_path = repo / "docs" / "explanation" / "billing" / "architecture.md"
    assert arch_md_path.exists()
    content = arch_md_path.read_text(encoding="utf-8")

    # Extract all markdown links: [text](path)
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
    user_story_links = [url for _, url in links if "user_stories" in url]
    assert len(user_story_links) > 0

    for link in user_story_links:
        clean_target = link.split("#")[0]
        resolved = (arch_md_path.parent / clean_target).resolve()
        assert resolved.exists(), f"Cross-link target {resolved} does not exist on disk"


@given("an existing bounded context documentation tree")
def given_existing_docs_tree(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["scaffold", "docs", "--bc", "billing", "--title", "Billing Subsystem"])
    assert res.returncode == 0
    ref_file = repo / "docs" / "reference" / "billing" / "index.md"
    custom_content = ref_file.read_text(encoding="utf-8") + "\n<!-- CUSTOM CONTENT -->\n"
    ref_file.write_text(custom_content, encoding="utf-8")
    repo_context["original_content"]["ref"] = custom_content


@when('attempting to scaffold the same bounded context without "--force"')
def when_attempting_scaffold_without_force(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["scaffold", "docs", "--bc", "billing"])
    repo_context["result"] = res


@then("the command warns the user and preserves existing documentation intact")
def then_command_warns_and_preserves(repo_context: dict[str, Any]):
    res = repo_context["result"]
    assert res is not None
    assert res.returncode == 1
    assert "already exists" in res.stdout or "already exists" in res.stderr
    repo = repo_context["repo"]
    ref_file = repo / "docs" / "reference" / "billing" / "index.md"
    assert ref_file.read_text(encoding="utf-8") == repo_context["original_content"]["ref"]


@then("exits cleanly without overwriting existing files.")
def then_exits_cleanly(repo_context: dict[str, Any]):
    res = repo_context["result"]
    assert res.returncode == 1
