"""Tests for universal documentation parser and relational graph builder."""

from pathlib import Path

from spec_ops.core.graph import build_graph_data, process_project_graph
from spec_ops.core.parser import SpecOpsParser
from spec_ops.scaffold.init import init_project


def test_parser_and_graph_on_scaffolded_project(tmp_path: Path):
    init_project(tmp_path, name="GraphDemo")
    docs_dir = tmp_path / "docs" / "project"

    parser = SpecOpsParser(docs_dir)
    data = parser.parse_all()

    assert len(data.personas) >= 2
    assert len(data.tasks) == 1
    assert data.tasks[0].canonical_id == "TASK-0001"
    assert len(data.adrs) == 7  # Baseline ADRs from profiles
    assert data.adrs[0].id == "ADR-0001"

    # Process graph
    processed = process_project_graph(data, target_buffer=10)
    assert processed.health_metrics["total_tasks"] == 1
    assert processed.health_metrics["refined_tasks"] == 1
    assert len(processed.edges) >= 1  # Task governed_by ADR-0001

    graph_data = build_graph_data(processed)
    assert len(graph_data.nodes) >= 4  # 2 personas, 1 task, 1 adr
    assert any(n.id == "TASK-0001" for n in graph_data.nodes)
    assert any(n.id == "ADR-0001" for n in graph_data.nodes)
