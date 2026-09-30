"""Unit tests for review brief generator and commit provenance audit."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.worker.commits import format_task_commit_message
from spec_ops.worker.review import (
    ChangedFileInfo,
    CommitProvenanceInfo,
    ReviewBrief,
    generate_review_brief,
    render_review_brief,
)


@pytest.fixture
def repo_for_review(tmp_path: Path) -> Path:
    repo = tmp_path / "review_repo"
    repo.mkdir()
    init_project(repo, name="ReviewUnitTest")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.dev"], cwd=repo, check=True, capture_output=True)

    # Initial commit
    (repo / "README.md").write_text("# Review Test\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: init"], cwd=repo, check=True, capture_output=True)

    return repo


def test_render_review_brief_structure():
    brief = ReviewBrief(
        task_id="TASK-0099",
        task_title="Test Feature",
        governing_prd="PRD-0001 (Test Engine)",
        governing_adrs="ADR-0002 (<500 lines limit), ADR-0003 (Frontdoor TDD)",
        acceptance_scenarios=["Scenario: Doing something useful"],
        lineage_path="Persona -> PRD -> User Story -> Task",
        lineage_detail="Alex -> PRD-0001 -> US-0001 -> TASK-0099",
        changed_files=[
            ChangedFileInfo(path="src/feature.py", added=10, deleted=2, total_lines=50, headroom=450),
        ],
        verification_report="0 private internal mocks flagged. Observable contracts verified via public frontdoors (ADR-0003 compliant).",
        commits=[
            CommitProvenanceInfo(commit_hash="12345678", author="Agent <agent@bot>", subject="feat: ok", author_type="Autonomous Worker", has_task_trailer=True),
            CommitProvenanceInfo(commit_hash="87654321", author="Human <human@co>", subject="fix: tweak", author_type="Human Contributor", has_task_trailer=False, missing_trailer_warning='Commit 87654321 is missing "SpecOps-Task: TASK-0099" git trailer.'),
        ],
    )

    out = render_review_brief(brief, provenance=False)
    assert "PRD-0001 (Test Engine)" in out
    assert "ADR-0002 (<500 lines limit)" in out
    assert "Persona -> PRD -> User Story -> Task" in out
    assert "headroom: 450 lines remaining until 500-line limit" in out
    assert "0 private internal mocks flagged" in out
    assert "Commit Provenance" not in out

    out_prov = render_review_brief(brief, provenance=True)
    assert "Commit Provenance & Author Distinction" in out_prov
    assert "Autonomous Worker" in out_prov
    assert "Human Contributor" in out_prov
    assert 'missing "SpecOps-Task: TASK-0099"' in out_prov


def test_generate_review_brief_mock_detection(repo_for_review: Path):
    repo = repo_for_review
    branch = "task/TASK-0077"
    subprocess.run(["git", "checkout", "-b", branch], cwd=repo, check=True, capture_output=True)

    bad_file = repo / "bad_mock.py"
    bad_file.write_text("import unittest.mock\nm = unittest.mock.MagicMock()\n", encoding="utf-8")
    subprocess.run(["git", "add", "bad_mock.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: added mock"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(root_dir=repo)
    brief = generate_review_brief("TASK-0077", cfg, repo_dir=repo)

    assert len(brief.private_mock_violations) > 0
    assert "ADR-0003 violation" in brief.verification_report
