"""Unit tests for Multi-Agent Task Dependency Graph Deadlock Resolver."""

from __future__ import annotations

from pathlib import Path
import pytest

from spec_ops.core.deadlock_breaker import (
    DeadlockCycle,
    DeadlockReport,
    TaskDeadlockResolver,
    compute_minimum_feedback_arc_set,
    find_elementary_cycle,
    tarjan_scc,
)


def test_tarjan_scc_acyclic() -> None:
    """Assert acyclic graph produces trivial 1-node SCCs."""
    graph = {
        "TASK-0001": ["TASK-0002"],
        "TASK-0002": ["TASK-0003"],
        "TASK-0003": [],
    }
    sccs = tarjan_scc(graph)
    assert len(sccs) == 3
    assert all(len(scc) == 1 for scc in sccs)


def test_tarjan_scc_and_cycle_detection() -> None:
    """Assert cyclic dependencies form non-trivial SCCs."""
    graph = {
        "TASK-0001": ["TASK-0002"],
        "TASK-0002": ["TASK-0003"],
        "TASK-0003": ["TASK-0001"],
        "TASK-0004": ["TASK-0003"],
    }
    sccs = tarjan_scc(graph)
    cyclic = [scc for scc in sccs if len(scc) > 1]
    assert len(cyclic) == 1
    assert set(cyclic[0]) == {"TASK-0001", "TASK-0002", "TASK-0003"}

    cycle = find_elementary_cycle(cyclic[0], graph)
    assert cycle[0] == cycle[-1]
    assert len(cycle) == 4


def test_self_loop_cycle() -> None:
    """Assert self-loop is detected as a cycle."""
    graph = {"TASK-0001": ["TASK-0001"]}
    sccs = tarjan_scc(graph)
    assert sccs == [["TASK-0001"]]
    cycle = find_elementary_cycle(["TASK-0001"], graph)
    assert cycle == ["TASK-0001", "TASK-0001"]


def test_compute_minimum_feedback_arc_set() -> None:
    """Assert minimum feedback arc set eliminates cycles."""
    graph = {
        "A": ["B"],
        "B": ["C"],
        "C": ["A"],
    }
    cuts = compute_minimum_feedback_arc_set(graph)
    assert len(cuts) == 1
    cut = cuts[0]
    assert cut in {("A", "B"), ("B", "C"), ("C", "A")}

    # Verify removing cut produces an acyclic graph
    pruned = {u: [v for v in neighbors if (u, v) != cut] for u, neighbors in graph.items()}
    pruned_sccs = [scc for scc in tarjan_scc(pruned) if len(scc) > 1]
    assert len(pruned_sccs) == 0


def test_task_deadlock_resolver_analyze_override() -> None:
    """Assert TaskDeadlockResolver analyzes graph override."""
    resolver = TaskDeadlockResolver()

    # Acyclic
    clean_report = resolver.analyze(graph_override={"T1": ["T2"], "T2": []})
    assert clean_report.is_acyclic is True
    assert clean_report.cycles == []
    assert "Zero dependency deadlocks" in clean_report.format_text()

    # Cyclic
    cyclic_report = resolver.analyze(graph_override={"T1": ["T2"], "T2": ["T1"]})
    assert cyclic_report.is_acyclic is False
    assert len(cyclic_report.cycles) == 1
    assert len(cyclic_report.recommended_cuts) == 1
    assert "Dependency Deadlocks Detected" in cyclic_report.format_text()

    d = cyclic_report.to_dict()
    assert d["is_acyclic"] is False
    assert d["cycle_count"] == 1


def test_resolve_deadlocks_on_disk(tmp_path: Path) -> None:
    """Assert resolve_deadlocks updates task frontmatter files."""
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)

    t1 = backlog_dir / "0001-t1.md"
    t1.write_text(
        """---
id: TASK-0001
dependencies:
  - TASK-0002
---
# Task 1
""",
        encoding="utf-8",
    )

    t2 = backlog_dir / "0002-t2.md"
    t2.write_text(
        """---
id: TASK-0002
dependencies:
  - TASK-0001
---
# Task 2
""",
        encoding="utf-8",
    )

    resolver = TaskDeadlockResolver(root_dir=tmp_path)
    report = resolver.analyze()
    assert report.is_acyclic is False

    # Dry run
    dry_actions = resolver.resolve_deadlocks(report, dry_run=True)
    assert len(dry_actions) == 1
    assert resolver.analyze().is_acyclic is False

    # Live resolution
    live_actions = resolver.resolve_deadlocks(report, dry_run=False)
    assert len(live_actions) == 1

    post_report = resolver.analyze()
    assert post_report.is_acyclic is True
