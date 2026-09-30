"""Focused unit and edge-case tests for spike sandboxing, graduation, and ADR synthesis."""

from __future__ import annotations

import datetime
import subprocess
import tempfile
from pathlib import Path

import pytest

from spec_ops.backlog.queue import write_task_file
from spec_ops.core.models import Task
from spec_ops.core.parser import parse_task
from spec_ops.scaffold.init import init_project
from spec_ops.spike.graduate import (
    _sync_priority_for_graduated,
    extract_benchmark_findings,
    find_next_adr_id,
    format_adr_content,
    slugify,
    transition_spike_task,
    update_adr_registry,
    update_dependent_tasks,
)
from spec_ops.spike.sandbox import (
    SpikeSandbox,
    normalize_spike_id,
    parse_timebox_duration,
    start_spike,
)


def test_normalize_spike_id():
    assert normalize_spike_id("SPIKE-0002") == ("SPIKE-0002", "0002")
    assert normalize_spike_id("0003") == ("SPIKE-0003", "0003")
    assert normalize_spike_id("TASK-0042") == ("SPIKE-0042", "0042")
    assert normalize_spike_id("spike-99") == ("SPIKE-0099", "0099")
    assert normalize_spike_id("custom") == ("SPIKE-0001", "0001")


def test_parse_timebox_duration():
    assert parse_timebox_duration("2h") == 7200.0
    assert parse_timebox_duration("1hr") == 3600.0
    assert parse_timebox_duration("3 hours") == 10800.0
    assert parse_timebox_duration("30m") == 1800.0
    assert parse_timebox_duration("45 mins") == 2700.0
    assert parse_timebox_duration("1d") == 86400.0
    assert parse_timebox_duration("2 days") == 172800.0
    assert parse_timebox_duration("120s") == 120.0
    assert parse_timebox_duration("100 seconds") == 100.0
    assert parse_timebox_duration("invalid") == 7200.0
    assert parse_timebox_duration("5x") == 18000.0


def test_slugify():
    assert slugify("Adopt DuckDB for Graph Query Acceleration") == "adopt-duckdb-for-graph-query-acceleration"
    assert slugify("Special @#$ Characters & Title!") == "special-characters-title"
    assert slugify("Multiple   Spaces --- And Dashes") == "multiple-spaces-and-dashes"
    assert slugify("--leading-and-trailing--") == "leading-and-trailing"
    assert slugify("___under___scores___") == "under-scores"


def test_find_next_adr_id(tmp_path: Path):
    # Nonexistent dir
    assert find_next_adr_id(tmp_path / "nonexistent") == ("ADR-0001", 1)

    adrs_dir = tmp_path / "adrs"
    adrs_dir.mkdir()
    # Empty
    assert find_next_adr_id(adrs_dir) == ("ADR-0001", 1)

    # Some ADRs, including uppercase stem and non-matching files
    (adrs_dir / "adr-0005-test.md").write_text("content", encoding="utf-8")
    (adrs_dir / "ADR-0009-ANOTHER.md").write_text("content", encoding="utf-8")
    (adrs_dir / "README.md").write_text("not an adr", encoding="utf-8")
    assert find_next_adr_id(adrs_dir) == ("ADR-0010", 10)


def test_extract_benchmark_findings(tmp_path: Path):
    harness = tmp_path / "harness"
    harness.mkdir()

    # Explicit findings takes precedence
    assert extract_benchmark_findings(harness, explicit_findings="  explicit 10ms  ") == "explicit 10ms"

    # From benchmark.txt
    (harness / "benchmark.txt").write_text("p95 latency = 45ms", encoding="utf-8")
    assert extract_benchmark_findings(harness) == "p95 latency = 45ms"

    # Empty benchmark.txt is skipped for benchmark.json
    (harness / "benchmark.txt").write_text("   ", encoding="utf-8")
    (harness / "benchmark.json").write_text('{"latency": 32}', encoding="utf-8")
    assert extract_benchmark_findings(harness) == '{"latency": 32}'

    # findings.txt
    (harness / "benchmark.json").unlink()
    (harness / "findings.txt").write_text("findings output 12ms", encoding="utf-8")
    assert extract_benchmark_findings(harness) == "findings output 12ms"

    # results.txt
    (harness / "findings.txt").unlink()
    (harness / "results.txt").write_text("results output 99ms", encoding="utf-8")
    assert extract_benchmark_findings(harness) == "results output 99ms"

    # From test_spike.py with benchmark output
    (harness / "results.txt").unlink()
    (harness / "test_spike.py").write_text('# benchmark output: "p95 = 55ms"\ndef test_ok(): pass\n', encoding="utf-8")
    assert "p95 = 55ms" in extract_benchmark_findings(harness)

    # From test_spike.py with p95 latency =
    (harness / "test_spike.py").write_text('# p95 latency = 88ms\ndef test_ok(): pass\n', encoding="utf-8")
    assert extract_benchmark_findings(harness) == "p95 latency = 88ms"

    # Fallback to notes or default
    (harness / "test_spike.py").unlink()
    assert extract_benchmark_findings(harness, notes="custom note") == "custom note"
    assert extract_benchmark_findings(tmp_path / "nonexistent") == "p95 latency = 142ms"


def test_format_adr_content_proven():
    content = format_adr_content(
        adr_id="ADR-0010",
        title="Adopt DuckDB",
        spike_id="SPIKE-0002",
        hypothesis="DuckDB is faster",
        findings="p95 latency = 142ms",
        result="proven",
        notes="Extra notes",
    )
    expected = (
        "# ADR-0010: Adopt DuckDB\n\n"
        "## Status\nProposed\n\n"
        "## Context\n"
        "Exploratory architectural spike SPIKE-0002 investigated the hypothesis:\n"
        '"DuckDB is faster".\n\n'
        "Empirical benchmark findings from SPIKE-0002:\n"
        "- p95 latency = 142ms\n"
        "- Extra notes\n\n"
        "## Decision\n"
        "We adopt Adopt DuckDB based on empirical benchmark findings from SPIKE-0002:\n"
        "- Findings: p95 latency = 142ms.\n\n"
        "## Consequences\n"
        "- **Positive**: Validated by empirical benchmark findings from SPIKE-0002 (p95 latency = 142ms).\n"
        "- **Negative**: Incurs implementation and ongoing maintenance responsibilities.\n"
    )
    assert content == expected

    # Proven without notes
    content_no_notes = format_adr_content(
        adr_id="ADR-0010",
        title="Adopt DuckDB",
        spike_id="SPIKE-0002",
        hypothesis="DuckDB is faster",
        findings="p95 latency = 142ms",
        result="proven",
    )
    assert "- Extra notes" not in content_no_notes
    assert "We adopt Adopt DuckDB based on empirical benchmark findings" in content_no_notes


def test_format_adr_content_disproven():
    content = format_adr_content(
        adr_id="ADR-0011",
        title="Reject SQLite",
        spike_id="SPIKE-0003",
        hypothesis="SQLite meets sync req",
        findings="p95 latency is 85ms",
        result="disproven",
        notes="Contention detected",
    )
    expected = (
        "# ADR-0011: Reject SQLite\n\n"
        "## Status\nProposed\n\n"
        "## Context\n"
        "Exploratory architectural spike SPIKE-0003 investigated the hypothesis:\n"
        '"SQLite meets sync req".\n\n'
        "Empirical benchmark testing revealed failing performance (p95 latency is 85ms).\n"
        "Notes: Contention detected.\n\n"
        "## Decision\n"
        "We reject Reject SQLite based on failing empirical benchmark findings from SPIKE-0003 (p95 latency is 85ms).\n"
        "Rationale: Contention detected.\n\n"
        "## Consequences\n"
        "- **Negative**: Dependent implementation slices for SPIKE-0003 are blocked.\n"
        "- **Action**: Alternative architectural approaches must be explored.\n"
    )
    assert content == expected

    # Disproven without notes
    content_no_notes = format_adr_content(
        adr_id="ADR-0011",
        title="Reject SQLite",
        spike_id="SPIKE-0003",
        hypothesis="SQLite meets sync req",
        findings="p95 latency is 85ms",
        result="disproven",
    )
    assert "Notes:" not in content_no_notes
    assert "Rationale:" not in content_no_notes
    assert "We reject Reject SQLite based on failing empirical benchmark findings" in content_no_notes


def test_update_adr_registry(tmp_path: Path):
    reg = tmp_path / "REGISTRY.md"
    reg.write_text("# Registry\n\n| ID | Title | Status | Date |\n|---|---|---|---|\n", encoding="utf-8")
    update_adr_registry(reg, "ADR-0010", "Adopt DuckDB", "2026-09-29")
    content = reg.read_text(encoding="utf-8")
    assert "| ADR-0010 | Adopt DuckDB | Proposed | 2026-09-29 |" in content

    # Calling again does not duplicate
    update_adr_registry(reg, "ADR-0010", "Adopt DuckDB", "2026-09-29")
    assert content.count("ADR-0010") == 1

    # Non-existent registry file handled cleanly
    update_adr_registry(tmp_path / "missing.md", "ADR-0011", "Title", "2026-09-29")


def test_transition_spike_task_and_priority_sync(tmp_path: Path):
    backlog = tmp_path / "backlog"
    # Nonexistent backlog folders returns None
    assert transition_spike_task(backlog, "SPIKE-0099", "0099") is None

    proposed = backlog / "proposed"
    proposed.mkdir(parents=True)
    task_file = proposed / "0002-test-spike.md"
    task = Task(id="0002", title="Test Spike", status="Proposed", file_path=task_file, claimed_by="worker-1", branch="task/0002")
    write_task_file(task)

    # Dotfile ignored
    (proposed / ".hidden.md").write_text("# Hidden", encoding="utf-8")

    # Priority sync without priority file handles cleanly
    _sync_priority_for_graduated(backlog, task)

    p_file = backlog / "PRIORITY.md"
    p_file.write_text("1. **TASK-0002 (Proposed)**: [`0002-test-spike`](proposed/0002-test-spike.md)\n", encoding="utf-8")

    dest = transition_spike_task(backlog, "SPIKE-0002", "0002")
    assert dest is not None
    assert dest.exists()
    assert dest.parent.name == "complete"
    updated_task = parse_task(dest)
    assert updated_task.status == "Graduated"
    assert updated_task.claimed_by == ""
    assert updated_task.branch == ""

    # Verify PRIORITY.md updated
    p_content = p_file.read_text(encoding="utf-8")
    assert "**TASK-0002 (Graduated)**: [`0002-test-spike`](complete/0002-test-spike.md)" in p_content

    # Transitioning from refined folder
    refined = backlog / "refined"
    refined.mkdir(parents=True)
    task_file_refined = refined / "0003-refined-spike.md"
    task3 = Task(id="0003", title="Refined Spike", status="Refined", file_path=task_file_refined)
    write_task_file(task3)
    dest3 = transition_spike_task(backlog, "SPIKE-0003", "0003")
    assert dest3 is not None
    assert dest3.parent.name == "complete"

    # Transitioning when task is already in complete folder
    dest3_again = transition_spike_task(backlog, "SPIKE-0003", "0003")
    assert dest3_again is not None
    assert dest3_again.parent.name == "complete"


def test_update_dependent_tasks(tmp_path: Path):
    backlog = tmp_path / "backlog"
    # Nonexistent folder handled cleanly
    assert update_dependent_tasks(backlog, "SPIKE-0002", "0002", "proven") == []

    proposed = backlog / "proposed"
    proposed.mkdir(parents=True)

    # Dotfile ignored
    (proposed / ".hidden.md").write_text("# Hidden", encoding="utf-8")

    # Self-dependency is skipped
    self_f = proposed / "0002-self.md"
    write_task_file(Task(id="0002", title="Self", dependencies=["0002"], file_path=self_f))

    t1_file = proposed / "0010-t1.md"
    t1 = Task(id="0010", title="Task 1", dependencies=["SPIKE-0002", "TASK-0001"], file_path=t1_file)
    write_task_file(t1)

    # Task in refined folder with TASK-0002 alias
    refined = backlog / "refined"
    refined.mkdir(parents=True)
    t2_file = refined / "0011-t2.md"
    t2 = Task(id="0011", title="Task 2", dependencies=["TASK-0002"], file_path=t2_file)
    write_task_file(t2)

    # Proven: removes SPIKE-0002 / TASK-0002
    updated = update_dependent_tasks(backlog, "SPIKE-0002", "0002", "proven")
    assert len(updated) == 2
    assert parse_task(t1_file).dependencies == ["TASK-0001"]
    assert parse_task(t2_file).dependencies == []

    # Disproven: marks blocked
    t3_file = proposed / "0012-t3.md"
    t3 = Task(id="0012", title="Task 3", dependencies=["SPIKE-0003"], file_path=t3_file)
    write_task_file(t3)

    updated_dis = update_dependent_tasks(backlog, "SPIKE-0003", "0003", "disproven")
    assert len(updated_dis) == 1
    assert parse_task(t3_file).status == "Blocked: Spike hypothesis failed"


def test_spike_sandbox_methods(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="SandboxApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    sandbox = start_spike(repo, "SPIKE-0005", hypothesis="Cache speed", timebox="2h")
    # Clean state
    ok, msg = sandbox.check_write_isolation()
    assert ok is True
    assert msg == ""

    # Modify src file
    src_file = sandbox.worktree_dir / "src" / "polluted.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("# bad", encoding="utf-8")
    ok, msg = sandbox.check_write_isolation()
    assert ok is False
    assert "Spike Sandbox Violation" in msg

    # Revert modification
    src_file.unlink()
    ok, msg = sandbox.check_write_isolation()
    assert ok is True

    # Timebox check - within limit
    tb_ok, tb_msg = sandbox.check_timebox(simulated_elapsed=100.0)
    assert tb_ok is True

    # Timebox check - expired without findings
    tb_ok, tb_msg = sandbox.check_timebox(simulated_elapsed=10000.0)
    assert tb_ok is False
    assert "timebox expired" in tb_msg

    # Record findings and check timebox again
    bench_txt = sandbox.harness_dir / "benchmark.txt"
    bench_txt.write_text("done", encoding="utf-8")
    tb_ok, tb_msg = sandbox.check_timebox(simulated_elapsed=10000.0)
    assert tb_ok is True
