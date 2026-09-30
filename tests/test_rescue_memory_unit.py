"""Comprehensive unit tests for rescue failure memory spike to maximize mutmut mutant kill rate."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from spec_ops.rescue.memory_spike import (
    DEFAULT_MANDATE,
    INVARIANT_MANDATES,
    FailureHistoryEntry,
    append_failure_record,
    benchmark_frontmatter_update,
    demote_task_to_proposed,
    extract_failed_invariants,
    parse_task_memory,
    reset_worktree_with_memory,
    serialize_task_with_memory,
    synthesize_negative_constraints,
)


def test_failure_history_entry_dataclass():
    entry = FailureHistoryEntry(
        attempt_date="2026-09-30",
        reason="Test failure",
        failed_invariants=["ADR-0003"],
    )
    d = entry.to_dict()
    assert d["attempt_date"] == "2026-09-30"
    assert d["reason"] == "Test failure"
    assert d["failed_invariants"] == ["ADR-0003"]

    default_entry = FailureHistoryEntry(attempt_date="2026-09-30", reason="Default")
    assert default_entry.failed_invariants == []
    assert default_entry.to_dict()["failed_invariants"] == []


def test_extract_failed_invariants_deduplication_and_case():
    reason = "Violated adr-0003 and ADR-0003 and then breached ADR-0002"
    extracted = extract_failed_invariants(reason)
    assert extracted == ["ADR-0003", "ADR-0002"]

    assert extract_failed_invariants("No invariants here") == []
    assert extract_failed_invariants("") == []


def test_parse_task_memory_edge_cases():
    # Not starting with ---
    m, b, h = parse_task_memory("# Just markdown")
    assert m == {}
    assert b == "# Just markdown"
    assert h == []

    # No newline after ---
    m, b, h = parse_task_memory("---")
    assert m == {}
    assert b == "---"
    assert h == []

    # No closing ---
    m, b, h = parse_task_memory("---\ntitle: Foo\n")
    assert m == {}
    assert b == "---\ntitle: Foo\n"
    assert h == []

    # Malformed YAML
    m, b, h = parse_task_memory("---\n: invalid yaml :\n---\nBody")
    assert m == {}
    assert b == "---\n: invalid yaml :\n---\nBody"
    assert h == []

    # Non-dictionary YAML (e.g. list)
    m, b, h = parse_task_memory("---\n- item 1\n- item 2\n---\nBody")
    assert m == {}
    assert b == "---\n- item 1\n- item 2\n---\nBody"
    assert h == []

    # Valid YAML with failure_history not a list
    m, b, h = parse_task_memory("---\ntitle: Task\nfailure_history: not-a-list\n---\nBody")
    assert m["title"] == "Task"
    assert b == "Body"
    assert h == []

    # Valid YAML with failure_history containing mixed items
    content = (
        "---\n"
        "title: Task\n"
        "failure_history:\n"
        "  - attempt_date: 2026-09-29\n"
        "    reason: valid\n"
        "  - 'string item'\n"
        "---\n"
        "Verbatim Body"
    )
    m, b, h = parse_task_memory(content)
    assert m["title"] == "Task"
    assert b == "Verbatim Body"
    assert len(h) == 1
    assert h[0]["reason"] == "valid"


def test_serialize_task_with_memory():
    meta = {"id": "0011", "title": "Test"}
    body = "\n# Heading\nContent\n"
    serialized = serialize_task_with_memory(meta, body)
    assert serialized.startswith("---\n")
    assert "id: '0011'\n" in serialized
    assert serialized.endswith(body)


def test_append_failure_record(tmp_path: Path):
    task_file = tmp_path / "0001-init.md"
    task_file.write_text("# No frontmatter\nBody only\n", encoding="utf-8")

    # Appends to file without initial frontmatter
    append_failure_record(task_file, reason="First failure violating ADR-0003", attempt_date="2026-09-25")
    meta, body, hist = parse_task_memory(task_file.read_text(encoding="utf-8"))
    assert meta["title"] == "0001-init"
    assert meta["status"] == "Refined"
    assert len(hist) == 1
    assert hist[0]["reason"] == "First failure violating ADR-0003"
    assert hist[0]["failed_invariants"] == ["ADR-0003"]
    assert hist[0]["attempt_date"] == "2026-09-25"

    # Appends second failure without explicit date or invariants
    append_failure_record(task_file, reason="Second failure")
    _, _, hist2 = parse_task_memory(task_file.read_text(encoding="utf-8"))
    assert len(hist2) == 2
    assert hist2[1]["reason"] == "Second failure"
    assert hist2[1]["failed_invariants"] == []
    assert len(hist2[1]["attempt_date"]) == 10  # YYYY-MM-DD


def test_demote_task_to_proposed(tmp_path: Path):
    backlog = tmp_path / "backlog"
    refined = backlog / "refined"
    proposed = backlog / "proposed"
    refined.mkdir(parents=True)
    proposed.mkdir(parents=True)

    # Task not found in refined
    ok, msg, path = demote_task_to_proposed(backlog, "TASK-0044")
    assert not ok
    assert "not found" in msg
    assert path is None

    # Task found in refined
    task_file = refined / "0044-demote-me.md"
    task_file.write_text(
        "---\nid: '0044'\ntitle: Demote Me\nstatus: Refined\n---\n# Task 44\n",
        encoding="utf-8",
    )
    priority_file = backlog / "PRIORITY.md"
    priority_file.write_text(
        "# Index\n\n- **TASK-0044 (Refined)**: [`0044-demote-me`](refined/0044-demote-me.md)\n",
        encoding="utf-8",
    )

    ok, msg, dest = demote_task_to_proposed(backlog, "TASK-0044")
    assert ok
    assert dest is not None
    assert dest.exists()
    assert dest.parent == proposed
    assert not task_file.exists()

    # Verify frontmatter status updated
    meta, _, _ = parse_task_memory(dest.read_text(encoding="utf-8"))
    assert meta["status"] == "Proposed"

    # Verify PRIORITY.md updated
    p_content = priority_file.read_text(encoding="utf-8")
    assert "**TASK-0044 (Proposed)**" in p_content
    assert "proposed/0044-demote-me.md" in p_content


def test_synthesize_negative_constraints_all_variants():
    # Empty history
    assert synthesize_negative_constraints([]) == ""

    # Punctuation handling: without period, with exclamation, with question
    h1 = [{"reason": "Missing period", "failed_invariants": ["ADR-0003"]}]
    s1 = synthesize_negative_constraints(h1)
    assert "- Previous failure: Missing period." in s1
    assert "- Mandate: You must strictly use public frontdoor entrypoints with zero mock backdoors." in s1

    h2 = [{"reason": "Already punctuated!", "failed_invariants": ["ADR-0002"]}]
    s2 = synthesize_negative_constraints(h2)
    assert "- Previous failure: Already punctuated!" in s2
    assert "- Mandate: You must decompose source files to stay strictly under 500 lines" in s2

    h3 = [{"reason": "Why did it fail?", "failed_invariants": ["ADR-0005"]}]
    s3 = synthesize_negative_constraints(h3)
    assert "- Previous failure: Why did it fail?" in s3
    assert "- Mandate: You must never modify shared backlog files on feature branches." in s3

    # Invariants as single string instead of list
    h4 = [{"reason": "Single invariant string", "failed_invariants": "ADR-0009"}]
    s4 = synthesize_negative_constraints(h4)
    assert "- Mandate: You must maintain generative property tests and >=80% mutation kill score under mutmut." in s4

    # Auto-extract from reason when failed_invariants omitted
    h5 = [{"reason": "Agent breached ADR-0019 in worktree"}]
    s5 = synthesize_negative_constraints(h5)
    assert "- Mandate: You must never hardcode credentials, secrets, or high-entropy tokens." in s5

    # Fallback to key in reason
    h6 = [{"reason": "Failed because ADR-0018 was ignored"}]
    s6 = synthesize_negative_constraints(h6)
    assert "- Mandate: You must not edit lockfiles or dependencies without explicit authorization." in s6

    # Completely unknown failure reason fallback
    h7 = [{"reason": "Bizarre non-ADR crash"}]
    s7 = synthesize_negative_constraints(h7)
    assert f"- Mandate: {DEFAULT_MANDATE}" in s7

    # FailureHistoryEntry objects directly
    h8 = [FailureHistoryEntry(attempt_date="2026-09-30", reason="Object test", failed_invariants=["ADR-0001"])]
    s8 = synthesize_negative_constraints(h8)
    assert "- Previous failure: Object test." in s8
    assert "- Mandate: You must maintain specification as code in docs/project/ with YAML frontmatter." in s8


def test_reset_worktree_with_memory_full_lifecycle(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    (repo / "file.txt").write_text("main", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    backlog = repo / "docs" / "project" / "backlog"
    refined = backlog / "refined"
    refined.mkdir(parents=True)
    task_file = refined / "0050-reset-task.md"
    task_file.write_text(
        "---\nid: '0050'\ntitle: Reset Task\nstatus: Refined\n---\n# Specification\n",
        encoding="utf-8",
    )

    # Missing task error
    ok, msg = reset_worktree_with_memory(repo, backlog, "TASK-9999", reason="Missing")
    assert not ok
    assert "specification not found" in msg

    # Create worktree
    wt_dir = repo / ".worktrees" / "task-0050"
    subprocess.run(
        ["git", "worktree", "add", "-b", "feat/TASK-0050", str(wt_dir), "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    assert wt_dir.exists()

    # Reset with memory (without demote)
    ok, msg = reset_worktree_with_memory(
        repo,
        backlog,
        "TASK-0050",
        reason="Failed test suite violating ADR-0003",
        demote=False,
    )
    assert ok
    assert not wt_dir.exists()
    assert task_file.exists()

    meta, _, hist = parse_task_memory(task_file.read_text(encoding="utf-8"))
    assert len(hist) == 1
    assert hist[0]["failed_invariants"] == ["ADR-0003"]

    # Re-create worktree and reset WITH demote
    subprocess.run(
        ["git", "worktree", "add", "-b", "feat/TASK-0050", str(wt_dir), "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    ok, msg = reset_worktree_with_memory(
        repo,
        backlog,
        "TASK-0050",
        reason="Specification ambiguity",
        demote=True,
    )
    assert ok
    assert not wt_dir.exists()
    assert not task_file.exists()

    proposed = backlog / "proposed" / "0050-reset-task.md"
    assert proposed.exists()
    meta_p, _, hist_p = parse_task_memory(proposed.read_text(encoding="utf-8"))
    assert meta_p["status"] == "Proposed"
    assert len(hist_p) == 2


def test_benchmark_frontmatter_update_runs(tmp_path: Path):
    t_file = tmp_path / "0010-bench.md"
    t_file.write_text(
        "---\nid: '0010'\ntitle: Bench\nstatus: Refined\n---\n# Body\n",
        encoding="utf-8",
    )
    ms = benchmark_frontmatter_update(t_file, iterations=10)
    assert isinstance(ms, float)
    assert ms > 0.0
