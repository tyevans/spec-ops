"""Executable BDD acceptance tests for US-0128: Brownfield Commit Provenance Baselining."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/us_0128_commit_provenance.feature")

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
    return {"repo": repo, "result": None, "baseline_sha": None}


# Scenario 1


@given('an existing git repository adopted into SpecOps at commit "adoption_commit_hash"')
def given_repo_with_legacy_and_adoption(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    # 1. Author legacy commits lacking SpecOps trailers
    for i in range(3):
        (repo / f"legacy_{i}.txt").write_text(f"legacy {i}", encoding="utf-8")
        subprocess.run(["git", "add", f"legacy_{i}.txt"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"chore: legacy commit {i}"], cwd=repo, check=True, capture_output=True)

    # 2. Run spec-ops init
    res_init = run_spec_ops(repo, ["init", "--name", "test-repo"])
    assert res_init.returncode == 0
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(pmac): adopt SpecOps"], cwd=repo, check=True, capture_output=True)
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    repo_ctx["baseline_sha"] = head_sha

    # 3. Add a completed task and anchored commit
    complete_dir = repo / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    task_file = complete_dir / "0001-setup-feature.md"
    task_file.write_text(
        """---
id: '0001'
title: Setup Feature
status: Complete
governing_stories:
  - US-0001
---
# TASK-0001
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", str(task_file)], cwd=repo, check=True, capture_output=True)
    msg = "feat(setup): add feature\n\nSpecOps-Task: TASK-0001"
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)


@given('"specops.toml" contains "[audit.provenance] baseline_commit = \'adoption_commit_hash\'"')
def given_specops_toml_with_baseline(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    toml_path = repo / "specops.toml"
    content = toml_path.read_text(encoding="utf-8")
    baseline_sha = repo_ctx["baseline_sha"]
    audit_section = f'\n[audit.provenance]\nbaseline_commit = "{baseline_sha}"\n'
    toml_path.write_text(content.rstrip() + "\n" + audit_section, encoding="utf-8")
    subprocess.run(["git", "add", "specops.toml"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: set baseline\n\nSpecOps-Task: TASK-0001"], cwd=repo, check=True, capture_output=True)


@when('running "spec-ops audit provenance --strict"')
def when_run_audit_provenance(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["audit", "provenance", "--strict"])
    repo_ctx["result"] = res


@then("commits preceding the baseline commit are marked as grandfathered legacy history")
def then_commits_preceding_are_grandfathered(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    output = res.stdout + res.stderr
    assert "legacy commit 0" not in output
    assert "legacy commit 1" not in output
    assert "legacy commit 2" not in output


@then('only commits from the baseline forward are audited for "SpecOps-Task" RFC-822 trailers')
def then_only_baseline_forward_audited(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    assert res.returncode == 0


@then("the provenance integrity report outputs 100% compliant lineage.")
def then_outputs_100_percent_lineage(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    assert "Traceability Integrity: 100%" in res.stdout


# Scenario 2


@given("a brownfield repository with unanchored historical commits")
def given_repo_unanchored_history(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    # 1. Unanchored historical commits
    for i in range(2):
        (repo / f"old_{i}.txt").write_text(f"old {i}", encoding="utf-8")
        subprocess.run(["git", "add", f"old_{i}.txt"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"chore: historical commit {i}"], cwd=repo, check=True, capture_output=True)

    run_spec_ops(repo, ["init", "--name", "test-repo"])
    complete_dir = repo / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    task_file = complete_dir / "0001-setup-feature.md"
    task_file.write_text(
        """---
id: '0001'
title: Setup Feature
status: Complete
governing_stories:
  - US-0001
---
# TASK-0001
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup\n\nSpecOps-Task: TASK-0001"], cwd=repo, check=True, capture_output=True)

    # 2. Create feature branch and anchored commit
    subprocess.run(["git", "checkout", "-b", "feat/my-feature"], cwd=repo, check=True, capture_output=True)
    (repo / "new_feature.txt").write_text("feature", encoding="utf-8")
    subprocess.run(["git", "add", "new_feature.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: anchored feature\n\nSpecOps-Task: TASK-0001"], cwd=repo, check=True, capture_output=True)


@when('running "spec-ops audit provenance --since main"')
def when_run_provenance_since_main(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["audit", "provenance", "--since", "main", "--strict"])
    repo_ctx["result"] = res


@then("the audit evaluates only commits in the specified range")
def then_evaluates_only_specified_range(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    assert res.returncode == 0


@then("ignores pre-existing unanchored history outside the range.")
def then_ignores_preexisting_unanchored(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    assert "historical commit" not in (res.stdout + res.stderr)
    assert "Traceability Integrity: 100%" in res.stdout
