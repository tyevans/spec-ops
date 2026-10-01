"""BDD step definitions for US-0117: Continuous Orchestration Retrospective and Self-Healing Engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_bdd import given, scenarios, then, when

from spec_ops.cli.main import build_parser
from spec_ops.cli.orchestrate_handler import handle_orchestrate_command
from spec_ops.config.models import SpecOpsConfig

scenarios("features/us_0117_orchestration_retrospective.feature")


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    return {}


@given("recent worktree failure logs containing secret scanner leak alerts or mock backdoor errors")
def setup_worktree_failure_logs(bdd_ctx: dict[str, Any], tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    backlog_dir = repo_root / "docs" / "project" / "backlog"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    (backlog_dir / "PRIORITY.md").write_text("# Backlog Priority Queue\n\n- **TASK-0114**: Active 114\n")

    worktrees_dir = repo_root / ".worktrees"
    wt1 = worktrees_dir / "task-0114"
    wt1.mkdir(parents=True, exist_ok=True)
    (wt1 / ".security-audit.log").write_text(
        "Security Violation (ADR-0019): Exposed secrets or credentials detected in staged diff: AWS API Key leak\n",
        encoding="utf-8",
    )

    wt2 = worktrees_dir / "task-0115"
    wt2.mkdir(parents=True, exist_ok=True)
    (wt2 / ".failure.log").write_text(
        "Prohibited invocation of mock backdoor 'mocker.patch()' (ADR-0003 violation).\n",
        encoding="utf-8",
    )

    cfg = SpecOpsConfig(root_dir=repo_root)
    bdd_ctx["repo_root"] = repo_root
    bdd_ctx["backlog_dir"] = backlog_dir
    bdd_ctx["worktrees_dir"] = worktrees_dir
    bdd_ctx["config"] = cfg


@when('the engineer runs "spec-ops orchestrate retrospect"')
def run_orchestrate_retrospect(bdd_ctx: dict[str, Any]):
    parser = build_parser()
    args = parser.parse_args([
        "orchestrate",
        "retrospect",
        "--log-dir",
        str(bdd_ctx["worktrees_dir"]),
        "--json",
    ])
    exit_code = handle_orchestrate_command(args, bdd_ctx["config"], parser)
    assert exit_code == 0
    bdd_ctx["exit_code"] = exit_code


@then("the failure patterns are categorized by invariant ID")
def verify_failure_patterns_categorized(bdd_ctx: dict[str, Any]):
    proposed_dir = bdd_ctx["backlog_dir"] / "proposed"
    assert proposed_dir.exists()
    tasks = list(proposed_dir.glob("*.md"))
    assert len(tasks) >= 2

    invariant_ids: set[str] = set()
    for t_file in tasks:
        content = t_file.read_text(encoding="utf-8")
        if "ADR-0019" in content:
            invariant_ids.add("ADR-0019")
        if "ADR-0003" in content:
            invariant_ids.add("ADR-0003")

    assert "ADR-0019" in invariant_ids
    assert "ADR-0003" in invariant_ids
    bdd_ctx["scaffolded_tasks"] = tasks


@then('high-priority remediation tasks are scaffolded in "docs/project/backlog/proposed/"')
def verify_proposed_tasks_scaffolded(bdd_ctx: dict[str, Any]):
    tasks = bdd_ctx["scaffolded_tasks"]
    assert len(tasks) >= 2
    for t_file in tasks:
        content = t_file.read_text(encoding="utf-8")
        assert "status: Proposed" in content
        assert "target_bc: worker" in content
        assert "Remediate" in content


@given("a proposed remediation task scaffolded by the retrospective engine")
def setup_scaffolded_task_for_inspection(bdd_ctx: dict[str, Any], tmp_path: Path):
    if "scaffolded_tasks" not in bdd_ctx:
        setup_worktree_failure_logs(bdd_ctx, tmp_path)
        run_orchestrate_retrospect(bdd_ctx)
        verify_failure_patterns_categorized(bdd_ctx)

    bdd_ctx["task_to_inspect"] = bdd_ctx["scaffolded_tasks"][0]


@when("the task frontmatter is inspected")
def inspect_task_frontmatter(bdd_ctx: dict[str, Any]):
    task_file: Path = bdd_ctx["task_to_inspect"]
    content = task_file.read_text(encoding="utf-8")
    assert content.startswith("---")
    parts = content.split("---", 2)
    frontmatter = yaml.safe_load(parts[1])
    bdd_ctx["frontmatter"] = frontmatter


@then("the failure history records the breached invariant and negative prompt guidance")
def verify_failure_history_and_guidance(bdd_ctx: dict[str, Any]):
    fm = bdd_ctx["frontmatter"]
    assert "failure_history" in fm
    history = fm["failure_history"]
    assert isinstance(history, list)
    assert len(history) > 0

    entry = history[0]
    assert "failed_invariants" in entry
    assert len(entry["failed_invariants"]) > 0
    assert any(inv.startswith("ADR-") for inv in entry["failed_invariants"])

    assert "negative_prompt_guidance" in entry
    guidance = entry["negative_prompt_guidance"]
    assert isinstance(guidance, str)
    assert len(guidance) > 10
    assert "You must" in guidance
