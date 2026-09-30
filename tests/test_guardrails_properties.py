"""Generative property-based testing for backlog protection guardrails (ADR-0009)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

from hypothesis import given, settings, strategies as st

from spec_ops.worker.guardrails import (
    detect_backlog_modifications,
    prepare_guardrailed_commit,
    sanitize_backlog_modifications,
    stage_legitimate_files,
)

FileMutation = tuple[str, Literal["unstaged", "staged", "untracked", "new_staged", "deleted"]]


@st.composite
def backlog_mutation_scenarios(draw) -> tuple[list[FileMutation], bool]:
    """Generates arbitrary git staging states and backlog tree mutations."""
    possible_backlog_paths = [
        "docs/project/backlog/PRIORITY.md",
        "docs/project/backlog/refined/0010-sample.md",
        "docs/project/backlog/proposed/0020-draft.md",
        "docs/project/backlog/untracked_agent_notes.md",
        "docs/project/backlog/accidental_output.json",
        "docs/project/backlog/complete/0001-done.md",
    ]
    mutation_types = ["unstaged", "staged", "untracked", "new_staged", "deleted"]

    selected_paths = draw(st.lists(st.sampled_from(possible_backlog_paths), min_size=1, max_size=4, unique=True))
    mutations: list[FileMutation] = [
        (path, draw(st.sampled_from(mutation_types)))
        for path in selected_paths
    ]
    has_legitimate_code = draw(st.booleans())
    return mutations, has_legitimate_code


@settings(max_examples=25, deadline=None)
@given(scenario=backlog_mutation_scenarios())
def test_hypothesis_backlog_guardrails_invariant(tmp_path_factory, scenario):
    """Property Invariant: sanitize_backlog_modifications deterministically resets backlog mutations."""
    mutations, has_legitimate_code = scenario
    repo = tmp_path_factory.mktemp("guardrail_repo")

    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)

    # Initial structure
    backlog_dir = repo / "docs" / "project" / "backlog"
    (backlog_dir / "refined").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "proposed").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "complete").mkdir(parents=True, exist_ok=True)

    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "app.py").write_text("def base(): return 0\n", encoding="utf-8")

    (backlog_dir / "PRIORITY.md").write_text("# Initial Priority\n", encoding="utf-8")
    (backlog_dir / "refined" / "0010-sample.md").write_text("---\nid: '0010'\n---\n", encoding="utf-8")
    (backlog_dir / "proposed" / "0020-draft.md").write_text("---\nid: '0020'\n---\n", encoding="utf-8")
    (backlog_dir / "complete" / "0001-done.md").write_text("---\nid: '0001'\n---\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: baseline commit"], cwd=repo, check=True, capture_output=True)

    # Apply generated mutations
    for path_rel, mtype in mutations:
        file_path = repo / path_rel
        if mtype == "unstaged":
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("corrupted content\n", encoding="utf-8")
        elif mtype == "staged":
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("staged corrupted content\n", encoding="utf-8")
            subprocess.run(["git", "add", str(file_path)], cwd=repo, check=True, capture_output=True)
        elif mtype == "untracked":
            if file_path.exists():
                subprocess.run(["git", "rm", "-f", str(file_path)], cwd=repo, capture_output=True)
                subprocess.run(["git", "commit", "-m", "rm for untracked"], cwd=repo, capture_output=True)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("rogue untracked file\n", encoding="utf-8")
        elif mtype == "new_staged":
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("rogue staged new file\n", encoding="utf-8")
            subprocess.run(["git", "add", str(file_path)], cwd=repo, check=True, capture_output=True)
        elif mtype == "deleted":
            if not file_path.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("temporary to delete\n", encoding="utf-8")
                subprocess.run(["git", "add", str(file_path)], cwd=repo, check=True, capture_output=True)
                subprocess.run(["git", "commit", "-m", "init temp"], cwd=repo, check=True, capture_output=True)
            file_path.unlink()

    if has_legitimate_code:
        (src_dir / "app.py").write_text("def base(): return 42\n", encoding="utf-8")

    # Invariant 1: detect_backlog_modifications deterministically discovers dirty files
    detected = detect_backlog_modifications(repo)
    assert len(detected) > 0, "Expected dirty files under docs/project/backlog"

    # Invariant 2: sanitize_backlog_modifications cleanly reverts all backlog edits
    reverted = sanitize_backlog_modifications(repo, stage_legitimate=True)
    assert len(reverted) > 0

    st_res = subprocess.run(
        ["git", "status", "--porcelain", "docs/project/backlog"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert st_res.stdout.strip() == "", f"Backlog was not clean after sanitize: {st_res.stdout}"

    # Invariant 3: commit payloads contain exactly 0 modifications to shared backlog
    if has_legitimate_code:
        ok, msg = prepare_guardrailed_commit(repo, "feat: test legitimate commit")
        assert ok, f"Expected successful commit: {msg}"

        diff_res = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        committed_files = [f.strip() for f in diff_res.stdout.splitlines() if f.strip()]
        assert not any("docs/project/backlog" in f for f in committed_files), (
            f"Commit payload contained backlog modifications: {committed_files}"
        )
        assert any("src/app.py" in f for f in committed_files)
