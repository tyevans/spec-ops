"""Property-based generative tests using Hypothesis for SpecOps domain invariants."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from spec_ops.backlog.health import HealthChecker
from spec_ops.config.models import ArchitectureSettings, ProjectSettings, QualitySettings, SpecOpsConfig
from spec_ops.core.graph import compute_health_metrics
from spec_ops.core.models import ProjectData, Task
from spec_ops.core.parser import extract_frontmatter, parse_priority_ranks


@given(
    lines=st.integers(min_value=0, max_value=1500),
    threshold=st.integers(min_value=50, max_value=400),
    margin=st.integers(min_value=1, max_value=200),
)
def test_property_file_length_classification(lines: int, threshold: int, margin: int):
    """Invariant Boundary: Arbitrary line counts are deterministically classified.

    L > limit => Violation
    threshold <= L <= limit => Warning
    L < threshold => Compliant
    """
    limit = threshold + margin
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        src_file = tmp_dir / "sample.py"
        if lines == 0:
            src_file.write_text("", encoding="utf-8")
        else:
            src_file.write_text("\n".join(f"# line {i}" for i in range(lines)) + "\n", encoding="utf-8")

        cfg = SpecOpsConfig(
            root_dir=tmp_dir,
            project=ProjectSettings(name="PropTest"),
            architecture=ArchitectureSettings(file_length_limit=limit, file_warning_threshold=threshold),
            quality=QualitySettings(),
        )
        checker = HealthChecker(cfg)
        violations, warnings, _ = checker.scan_file_lengths()

        actual_lines = len(src_file.read_text(encoding="utf-8").splitlines())
        assert actual_lines == lines

        if lines > limit:
            assert len(violations) == 1
            assert violations[0].lines == lines
            assert violations[0].limit == limit
            assert len(warnings) == 0
        elif lines >= threshold:
            assert len(violations) == 0
            assert len(warnings) == 1
            assert warnings[0].lines == lines
            assert warnings[0].threshold == threshold
        else:
            assert len(violations) == 0
            assert len(warnings) == 0


@given(
    task_num=st.integers(min_value=1, max_value=9999),
    title=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")), min_size=1, max_size=40),
    status=st.sampled_from(["Refined", "Proposed", "Complete"]),
    body=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")), min_size=0, max_size=100),
)
def test_property_frontmatter_extraction_roundtrip(task_num: int, title: str, status: str, body: str):
    """Parser Round-Trip Invariant: Markdown specifications with YAML frontmatter parse without data loss."""
    clean_title = title.strip() or "DefaultTitle"
    tid = f"{task_num:04d}"
    content = f"""---
id: '{tid}'
title: '{clean_title}'
status: '{status}'
---
# {clean_title}

{body}
"""
    meta, extracted_body = extract_frontmatter(content)
    assert meta.get("id") == tid
    assert meta.get("title") == clean_title
    assert meta.get("status") == status
    assert f"# {clean_title}" in extracted_body
    if body:
        assert body in extracted_body


@given(
    refined_count=st.integers(min_value=0, max_value=80),
    target_buffer=st.integers(min_value=4, max_value=30),
)
def test_property_buffer_health_metrics_invariants(refined_count: int, target_buffer: int):
    """Buffer Health Invariant: Refined buffer status is strictly bounded by target buffer thresholds."""
    tasks = [
        Task(id=str(i), title=f"Task {i}", status="Refined")
        for i in range(1, refined_count + 1)
    ]
    data = ProjectData(tasks=tasks)
    metrics = compute_health_metrics(data, target_buffer=target_buffer)

    assert metrics["refined_tasks"] == refined_count
    assert metrics["total_tasks"] == refined_count

    lower_bound = target_buffer // 2
    upper_bound = target_buffer * 2

    if refined_count < lower_bound:
        assert metrics["ready_buffer_health"] == "UNDER_BUFFERED"
    elif refined_count > upper_bound:
        assert metrics["ready_buffer_health"] == "OVER_BUFFERED"
    else:
        assert metrics["ready_buffer_health"] == "OPTIMAL"


@given(task_num=st.integers(min_value=1, max_value=99999))
def test_property_task_canonical_id_formatting(task_num: int):
    """Task Canonical ID Invariant: Canonical task ID is deterministically prefixed with TASK- and 4-digit padded."""
    task = Task(id=str(task_num), title="Sample Task", status="Proposed")
    cid = task.canonical_id

    assert cid.startswith("TASK-")
    numeric_part = cid.replace("TASK-", "")
    assert int(numeric_part) == task_num
    if task_num < 10000:
        assert len(numeric_part) == 4


@given(task_ids=st.lists(st.integers(min_value=1, max_value=500), min_size=1, max_size=15, unique=True))
def test_property_priority_rank_parsing(task_ids: list[int]):
    """Priority Rank Ordering Invariant: Priority ranks strictly follow line sequence."""
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        priority_file = tmp_dir / "PRIORITY.md"

        lines = ["# Backlog Priority Index\n"]
        for tid in task_ids:
            lines.append(f"- **TASK-{tid:04d} (Refined)**: [task](refined/{tid:04d}-task.md)")
        priority_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        ranks = parse_priority_ranks(tmp_dir)
        assert len(ranks) == len(task_ids)

        for expected_rank, tid in enumerate(task_ids, start=1):
            cid = f"TASK-{tid:04d}"
            assert ranks[cid] == expected_rank


@given(
    agents=st.lists(
        st.sampled_from(["antigravity", "claude", "cursor", "ANTIGRAVITY", "Claude", "  cursor  "]),
        min_size=0,
        max_size=10,
    )
)
def test_property_target_agents_parsing(agents: list[str]):
    """Target Agent Parsing Invariant: Normalized agent list is always a deduplicated canonical subset."""
    from spec_ops.scaffold.adapters import SUPPORTED_AGENTS, parse_target_agents

    parsed = parse_target_agents(agents)
    # Output must be a subset of SUPPORTED_AGENTS
    assert all(a in SUPPORTED_AGENTS for a in parsed)
    # Output must have no duplicates
    assert len(parsed) == len(set(parsed))
    # Output must be sorted in canonical order
    indices = [SUPPORTED_AGENTS.index(a) for a in parsed]
    assert indices == sorted(indices)


@given(
    quadrant=st.sampled_from(["tutorials", "how-to", "reference", "explanation", "project", "misc", "random", "internal", "specs"]),
    filename=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=15),
)
def test_property_diataxis_quadrant_classification(quadrant: str, filename: str):
    """Diataxis Quadrant Invariant: Files outside the 5 approved quadrants are deterministically flagged."""
    from spec_ops.docs.auditor import check_diataxis_structure
    from spec_ops.docs.models import APPROVED_QUADRANTS

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        docs = Path(tmp_dir_str) / "docs"
        # Scaffold all 5 required quadrants with valid files
        for q in APPROVED_QUADRANTS:
            (docs / q).mkdir(parents=True, exist_ok=True)
            (docs / q / "base.md").write_text("# Base\n", encoding="utf-8")

        # Now place test file in target quadrant
        target_dir = docs / quadrant
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / f"{filename}.md").write_text("# Doc\n", encoding="utf-8")

        violations, checked = check_diataxis_structure(docs)
        is_approved = quadrant in APPROVED_QUADRANTS

        unapproved_violations = [v for v in violations if f"unapproved quadrant '{quadrant}'" in v.message]
        if is_approved:
            assert len(unapproved_violations) == 0
        else:
            assert len(unapproved_violations) == 1
            assert unapproved_violations[0].category == "structure"


@given(
    parser_flags=st.sets(
        st.sampled_from(["--verbose", "--dry-run", "--json", "--output", "--format", "--force"]),
        min_size=0,
        max_size=6,
    ),
    doc_flags=st.sets(
        st.sampled_from(["--verbose", "--dry-run", "--json", "--output", "--format", "--force"]),
        min_size=0,
        max_size=6,
    ),
)
def test_property_cli_doc_option_drift_roundtrip(parser_flags: set[str], doc_flags: set[str]):
    """CLI Drift Invariant: Option drift strictly detects the exact set difference between parser and docs."""
    import argparse
    from spec_ops.docs.cli_inspector import check_cli_drift

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        docs = Path(tmp_dir_str) / "docs"
        (docs / "reference").mkdir(parents=True, exist_ok=True)

        args_str = " ".join(f"[{f}]" for f in sorted(doc_flags)) if doc_flags else "None"
        cli_content = f"""# CLI Reference

| Command | Arguments | Description |
|---|---|---|
| `spec-ops testcmd` | `{args_str}` | Test command |
"""
        (docs / "reference" / "cli.md").write_text(cli_content, encoding="utf-8")

        parser = argparse.ArgumentParser(prog="spec-ops")
        subs = parser.add_subparsers(dest="command")
        p_cmd = subs.add_parser("testcmd")
        for flag in parser_flags:
            p_cmd.add_argument(flag, action="store_true")

        violations, _ = check_cli_drift(docs, parser)

        expected_missing = parser_flags - doc_flags
        expected_extra = doc_flags - parser_flags

        missing_violations = [v for v in violations if "missing option(s)" in v.message]
        extra_violations = [v for v in violations if "documents non-existent option(s)" in v.message]

        if expected_missing:
            assert len(missing_violations) == 1
            for f in expected_missing:
                assert f in missing_violations[0].message
        else:
            assert len(missing_violations) == 0

        if expected_extra:
            assert len(extra_violations) == 1
            for f in expected_extra:
                assert f in extra_violations[0].message
        else:
            assert len(extra_violations) == 0

