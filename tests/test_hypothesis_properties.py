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
            assert len(violations) == 1 and violations[0].lines == lines and violations[0].limit == limit
            assert len(warnings) == 0
        elif lines >= threshold:
            assert len(violations) == 0
            assert len(warnings) == 1 and warnings[0].lines == lines and warnings[0].threshold == threshold
        else:
            assert len(violations) == 0 and len(warnings) == 0


@given(
    task_num=st.integers(min_value=1, max_value=9999),
    title=st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters=("\x00", "\n", "\r")), min_size=1, max_size=40),
    emoji=st.sampled_from(["🚀", "💡", "🔥", "✨", "🎯", ""]),
    status=st.sampled_from(["Refined", "Proposed", "Complete"]),
    tags=st.lists(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8), min_size=0, max_size=4),
    line_break=st.sampled_from(["\n", "\r\n"]),
    body=st.text(min_size=0, max_size=100),
)
def test_property_frontmatter_extraction_roundtrip(
    task_num: int, title: str, emoji: str, status: str, tags: list[str], line_break: str, body: str
):
    """Parser Round-Trip Invariant: Markdown specifications with YAML frontmatter parse without data loss."""
    from spec_ops.core.parser import serialize_frontmatter

    clean_title = f"{emoji} {title.strip()}".strip() or "DefaultTitle"
    tid = f"{task_num:04d}"
    meta_in = {
        "id": tid,
        "title": clean_title,
        "status": status,
        "dependencies": [f"TASK-{i:04d}" for i in range(1, len(tags) + 1)],
        "tags": tags,
    }
    clean_body = body.replace("\r", "")
    content = serialize_frontmatter(meta_in, body=f"# {clean_title}{line_break}{clean_body}")
    if line_break == "\r\n":
        content = content.replace("\n", "\r\n")

    meta, extracted_body = extract_frontmatter(content)
    assert meta.get("id") == tid
    assert meta.get("title") == clean_title
    assert meta.get("status") == status
    assert meta.get("dependencies") == meta_in["dependencies"]
    assert meta.get("tags") == tags
    assert f"# {clean_title}" in extracted_body

    re_serialized = serialize_frontmatter(meta, body=extracted_body)
    re_meta, re_body = extract_frontmatter(re_serialized)
    assert re_meta == meta
    assert re_body == extracted_body


@given(num_nodes=st.integers(min_value=2, max_value=12))
def test_property_graph_acyclicity(num_nodes: int):
    """Graph Acyclicity Invariant: Task dependency graphs remain Directed Acyclic Graphs (DAGs); circular dependencies are detected deterministically."""
    from spec_ops.core.topology import DirectedGraph, tarjan_scc

    g = DirectedGraph()
    for i in range(num_nodes):
        g.add_node(f"TASK-{i:04d}")
    for i in range(num_nodes - 1):
        g.add_edge(f"TASK-{i:04d}", f"TASK-{i+1:04d}")

    # Pure DAG: every SCC has exactly 1 node (0 cycles)
    sccs = tarjan_scc(g)
    assert len([c for c in sccs if len(c) > 1]) == 0

    # Introduce a back-edge to create a cycle
    g.add_edge(f"TASK-{num_nodes-1:04d}", "TASK-0000")
    cycled_sccs = [c for c in tarjan_scc(g) if len(c) > 1]
    assert len(cycled_sccs) >= 1
    assert "TASK-0000" in cycled_sccs[0]


@given(seed=st.integers(min_value=0, max_value=10000))
def test_property_graph_permutation_invariance(seed: int):
    """Graph Permutation Invariance: GraphData contains identical node IDs, edge sets, and computed health metrics regardless of file ingestion sequence."""
    import random
    from spec_ops.core.graph import build_graph_data, process_project_graph
    from spec_ops.core.models import ADR, PRD, Persona, ProjectData, Task, UserStory

    personas = [Persona(id=f"p{i}", name=f"Persona {i}") for i in range(5)]
    stories = [UserStory(id=f"US-{i:04d}", title=f"Story {i}", persona=f"p{i % 5}") for i in range(10)]
    prds = [PRD(id=f"PRD-{i:04d}", title=f"PRD {i}", linked_stories=[f"US-{i:04d}"]) for i in range(5)]
    adrs = [ADR(id=f"ADR-{i:04d}", title=f"ADR {i}") for i in range(5)]
    tasks = [
        Task(
            id=str(i),
            title=f"Task {i}",
            status="Refined" if i % 2 == 0 else "Proposed",
            governing_stories=[f"US-{(i % 10):04d}"],
            governing_adrs=[f"ADR-{(i % 5):04d}"],
            governing_prds=[f"PRD-{(i % 5):04d}"],
            dependencies=[f"TASK-{max(1, i-1):04d}"] if i > 1 else [],
        )
        for i in range(1, 26)
    ]

    base_data = ProjectData(personas=list(personas), stories=list(stories), prds=list(prds), tasks=list(tasks), adrs=list(adrs))
    process_project_graph(base_data)
    base_graph = build_graph_data(base_data)
    base_nodes = {n.id for n in base_graph.nodes}
    base_edges = {(e.source, e.target, e.relation) for e in base_graph.edges}
    base_metrics = dict(base_data.health_metrics)

    rng = random.Random(seed)
    p_tasks, p_stories, p_prds, p_adrs, p_personas = list(tasks), list(stories), list(prds), list(adrs), list(personas)
    rng.shuffle(p_tasks)
    rng.shuffle(p_stories)
    rng.shuffle(p_prds)
    rng.shuffle(p_adrs)
    rng.shuffle(p_personas)

    perm_data = ProjectData(personas=p_personas, stories=p_stories, prds=p_prds, tasks=p_tasks, adrs=p_adrs)
    process_project_graph(perm_data)
    perm_graph = build_graph_data(perm_data)

    assert {n.id for n in perm_graph.nodes} == base_nodes
    assert {(e.source, e.target, e.relation) for e in perm_graph.edges} == base_edges
    assert perm_data.health_metrics == base_metrics


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
    assert cid.startswith("TASK-") and int(cid.replace("TASK-", "")) == task_num
    if task_num < 10000:
        assert len(cid.replace("TASK-", "")) == 4


@given(task_ids=st.lists(st.integers(min_value=1, max_value=500), min_size=1, max_size=15, unique=True))
def test_property_priority_rank_parsing(task_ids: list[int]):
    """Priority Rank Ordering Invariant: Priority ranks strictly follow line sequence."""
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        lines = ["# Backlog Priority Index\n"] + [f"- **TASK-{t:04d} (Refined)**: [task](refined/{t:04d}-task.md)" for t in task_ids]
        (tmp_dir / "PRIORITY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        ranks = parse_priority_ranks(tmp_dir)
        assert len(ranks) == len(task_ids)
        for expected_rank, tid in enumerate(task_ids, start=1):
            assert ranks[f"TASK-{tid:04d}"] == expected_rank


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

        violations, _ = check_diataxis_structure(docs)
        unapproved_v = [v for v in violations if f"unapproved quadrant '{quadrant}'" in v.message]
        if quadrant in APPROVED_QUADRANTS:
            assert len(unapproved_v) == 0
        else:
            assert len(unapproved_v) == 1 and unapproved_v[0].category == "structure"


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

        assert len(missing_violations) == (1 if expected_missing else 0)
        for f in expected_missing:
            assert f in missing_violations[0].message

        assert len(extra_violations) == (1 if expected_extra else 0)
        for f in expected_extra:
            assert f in extra_violations[0].message


@given(
    selected_profiles=st.sets(
        st.sampled_from(["core", "bdd", "ddd", "security"]),
        min_size=1,
        max_size=4,
    ).map(list)
)
def test_property_profile_permutations_generation(selected_profiles: list[str]):
    """Profile Composition Invariant: Arbitrary profile permutations generate valid, non-overlapping sections without syntax corruption."""
    import sys
    tomllib = __import__("tomllib" if sys.version_info >= (3, 11) else "tomli")

    from spec_ops.scaffold.init import init_project

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        init_project(tmp_dir, name="PermutationTest", profiles=selected_profiles, diataxis=False, github_pages=False, pre_commit=False)

        parsed_toml = tomllib.loads((tmp_dir / "specops.toml").read_text(encoding="utf-8"))
        assert "project" in parsed_toml and "architecture" in parsed_toml

        if "security" in selected_profiles:
            assert parsed_toml.get("security", {}).get("secret_scanning") is True
            assert (tmp_dir / "docs" / "project" / "SECURITY.md").is_file()

        agents_content = (tmp_dir / "AGENTS.md").read_text(encoding="utf-8")
        assert "# PermutationTest Agent Operating Manual" in agents_content
        for sec in ["## Hard Invariants", "## Design Principles", "## Project Structure & Navigation", "## Definition of Ready (DoR)", "## Definition of Done (DoD)"]:
            assert agents_content.count(sec) == 1

        sec_keys = {"security": "## Security & Supply-Chain Hard Invariants", "bdd": "Executable BDD User Stories", "ddd": "Domain-Driven Design (DDD)"}
        for prof, kw in sec_keys.items():
            assert (prof in selected_profiles) == (kw in agents_content)


@given(summary=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")), min_size=0, max_size=100))
def test_property_review_output_approval_invariant(summary: str):
    """Review Approval Invariant: Outputs containing STATUS: APPROVED without rejection markers evaluate to approved."""
    from spec_ops.backlog.reviewer import parse_review_output

    res = parse_review_output(f"Summary: {summary}\nSTATUS: APPROVED\nAll good.")
    assert res.approved is True and res.feedback == ""


@given(feedback_items=st.lists(st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")), min_size=1, max_size=50), min_size=1, max_size=5))
def test_property_review_output_changes_requested_invariant(feedback_items: list[str]):
    """Review Rejection Invariant: Outputs requesting changes extract feedback and evaluate to unapproved."""
    from spec_ops.backlog.reviewer import parse_review_output

    body = "\n".join(f"- {item.strip() or 'Issue'}" for item in feedback_items)
    res = parse_review_output(f"STATUS: CHANGES_REQUESTED\n\n## Review Feedback\n{body}")
    assert res.approved is False and len(res.feedback) > 0


@given(arbitrary_text=st.text(min_size=0, max_size=500))
def test_property_review_output_robustness(arbitrary_text: str):
    """Review Robustness Invariant: Any arbitrary input parses deterministically into a valid ReviewResult."""
    from spec_ops.backlog.reviewer import parse_review_output

    res = parse_review_output(arbitrary_text)
    assert isinstance(res.approved, bool) and isinstance(res.feedback, str) and isinstance(res.raw_output, str)

