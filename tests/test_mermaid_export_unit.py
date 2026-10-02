"""Unit tests for relational knowledge graph Mermaid and Graphviz diagram exporter.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0011, ADR-0015, and PRD-0005.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from uuid import UUID
from datetime import datetime, timezone
import pytest
from redstring import Entity, ExtractionMethod, Provenance, Relationship

from spec_ops.config.models import ArchitectureSettings, SpecOpsConfig
from spec_ops.graph.mermaid_export import (
    export_diagram,
    generate_dot,
    generate_mermaid,
    handle_mermaid_command,
    sanitize_label,
    sanitize_node_id,
)


def _make_dummy_entity(name: str, etype: str, title: str = "") -> Entity:
    prov = Provenance(
        source_id="test",
        extraction_method=ExtractionMethod.PATTERN,
        confidence=1.0,
        observed_at=datetime.now(timezone.utc),
    )
    props = {"title": title} if title else {}
    return Entity(
        id=UUID(int=hash(name) % (2**128)),
        tenant_id=UUID(int=0),
        name=name,
        normalized_name=name.lower(),
        entity_type=etype,
        description=title,
        properties=props,
        provenance=prov,
    )


def _make_dummy_rel(src: Entity, tgt: Entity, rtype: str) -> Relationship:
    return Relationship(
        id=UUID(int=hash(f"{src.name}->{tgt.name}") % (2**128)),
        tenant_id=UUID(int=0),
        source_entity_id=src.id,
        target_entity_id=tgt.id,
        relationship_type=rtype,
        confidence=1.0,
        source_id="test",
    )


def test_sanitize_node_id() -> None:
    assert sanitize_node_id("TASK-0001") == "TASK_0001"
    assert sanitize_node_id("0001-task") == "node_0001_task"
    assert sanitize_node_id("US 0042") == "US_0042"
    assert sanitize_node_id("Alex (Architect)") == "Alex__Architect_"


def test_sanitize_label() -> None:
    assert sanitize_label('Title with "quotes" and [brackets]') == "Title with 'quotes' and (brackets)"
    assert sanitize_label("Title with {braces}") == "Title with (braces)"


def test_generate_mermaid_syntax() -> None:
    task = _make_dummy_entity("TASK-0001", "Task", title="First Task")
    story = _make_dummy_entity("US-0001", "UserStory", title="First Story")
    rel = _make_dummy_rel(task, story, "implements")

    output = generate_mermaid([task, story], [rel], direction="TD")
    assert output.startswith("flowchart TD\n")
    assert 'TASK_0001["TASK-0001: First Task"]' in output
    assert 'US_0001["US-0001: First Story"]' in output
    assert "TASK_0001 -->|implements| US_0001" in output
    assert "class TASK_0001 task;" in output
    assert "class US_0001 userstory;" in output


def test_generate_dot_syntax() -> None:
    task = _make_dummy_entity("TASK-0001", "Task", title="First Task")
    story = _make_dummy_entity("US-0001", "UserStory", title="First Story")
    rel = _make_dummy_rel(task, story, "implements")

    output = generate_dot([task, story], [rel], direction="LR")
    assert output.startswith("digraph G {\n")
    assert 'rankdir="LR";' in output
    assert 'TASK_0001 [label="TASK-0001: First Task"];' in output
    assert 'US_0001 [label="US-0001: First Story"];' in output
    assert 'TASK_0001 -> US_0001 [label="implements"];' in output
    assert output.strip().endswith("}")


def test_cli_mermaid_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = SpecOpsConfig(
        root_dir=tmp_path,
        architecture=ArchitectureSettings(),
    )
    # Empty docs dir returns empty diagram gracefully
    args = argparse.Namespace(
        root=None,
        depth=1,
        format="mermaid",
        direction="TD",
        output=None,
    )
    code = handle_mermaid_command(args, config)
    assert code == 0
    captured = capsys.readouterr()
    assert "flowchart TD" in captured.out


def test_cli_mermaid_file_export(tmp_path: Path) -> None:
    config = SpecOpsConfig(
        root_dir=tmp_path,
        architecture=ArchitectureSettings(),
    )
    out_file = tmp_path / "diagram.mmd"
    args = argparse.Namespace(
        root=None,
        depth=1,
        format="mermaid",
        direction="LR",
        output=str(out_file),
    )
    code = handle_mermaid_command(args, config)
    assert code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "flowchart LR" in content
