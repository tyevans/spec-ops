"""Executable BDD scenarios for US-0101 / TASK-0161: Mermaid Subgraph Exporter.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0011, ADR-0015; PRD-0005; US-0101.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.config.models import ArchitectureSettings, SpecOpsConfig
from spec_ops.graph.mermaid_export import export_diagram, handle_mermaid_command

scenarios("features/us_0101_mermaid_export.feature")


def _scaffold_minimal_graph_repo(root: Path) -> None:
    # 1. PRD
    prd_dir = root / "docs" / "project" / "product"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "0001-engine.md").write_text(
        """---
id: PRD-0001
title: Autonomous Engine
status: Accepted
target_persona: Alex
---
# PRD-0001: Autonomous Engine
""",
        encoding="utf-8",
    )

    # 2. Story
    story_dir = root / "docs" / "project" / "user_stories"
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / "0001-story.md").write_text(
        """---
id: US-0001
title: Core Story
status: Accepted
governing_prd: PRD-0001
---
# US-0001: Core Story
""",
        encoding="utf-8",
    )

    # 3. Tasks
    task_dir = root / "docs" / "project" / "backlog" / "complete"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "0001-base-task.md").write_text(
        """---
id: TASK-0001
title: Base Task
status: Complete
dependencies: []
governing_stories: [US-0001]
---
# TASK-0001: Base Task
""",
        encoding="utf-8",
    )

    (task_dir / "0002-dependent-task.md").write_text(
        """---
id: TASK-0002
title: Dependent Task
status: Complete
dependencies: [TASK-0001]
governing_stories: [US-0001]
---
# TASK-0002: Dependent Task
""",
        encoding="utf-8",
    )

    (task_dir / "0003-far-task.md").write_text(
        """---
id: TASK-0003
title: Far Task
status: Complete
dependencies: [TASK-0002]
governing_stories: [US-0001]
---
# TASK-0003: Far Task
""",
        encoding="utf-8",
    )


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    _scaffold_minimal_graph_repo(tmp_path)
    config = SpecOpsConfig(
        root_dir=tmp_path,
        architecture=ArchitectureSettings(),
    )
    return {
        "root_dir": tmp_path,
        "config": config,
        "output": None,
    }


# --- Scenario 1: Generating Mermaid flowchart for a task lineage ---


@given("a relational knowledge graph with linked tasks and stories")
def graph_with_linked_tasks_and_stories(bdd_context: dict[str, Any]) -> None:
    assert (bdd_context["root_dir"] / "docs" / "project").exists()


@when("the developer exports a Mermaid diagram rooted at a specific task")
def export_mermaid_rooted_at_task(bdd_context: dict[str, Any]) -> None:
    output = export_diagram(
        root_dir=bdd_context["root_dir"],
        root_entity="TASK-0002",
        depth=2,
        format_type="mermaid",
    )
    bdd_context["output"] = output


@then("valid Mermaid flowchart syntax is generated")
def verify_valid_mermaid_syntax(bdd_context: dict[str, Any]) -> None:
    output = bdd_context["output"]
    assert output.startswith("flowchart TD")
    assert "classDef" in output


@then("the output contains the task node, its governing story, and dependencies")
def verify_output_contains_task_and_dependencies(bdd_context: dict[str, Any]) -> None:
    output = bdd_context["output"]
    assert "TASK_0002" in output
    assert "TASK_0001" in output
    assert "US_0001" in output
    assert "TASK_0002 -->|depends_on| TASK_0001" in output


# --- Scenario 2: Traversal depth limiting ---


@given("a deep dependency graph across PRDs and tasks")
def deep_dependency_graph(bdd_context: dict[str, Any]) -> None:
    assert (bdd_context["root_dir"] / "docs" / "project").exists()


@when("the developer exports diagram with depth limit of 1")
def export_diagram_with_depth_1(bdd_context: dict[str, Any]) -> None:
    output = export_diagram(
        root_dir=bdd_context["root_dir"],
        root_entity="TASK-0003",
        depth=1,
        format_type="mermaid",
    )
    bdd_context["output"] = output


@then("only immediate adjacent neighbors are included in the emitted diagram")
def verify_only_immediate_neighbors(bdd_context: dict[str, Any]) -> None:
    output = bdd_context["output"]
    # TASK-0003 has immediate dependency TASK-0002 and story US-0001
    assert "TASK_0003" in output
    assert "TASK_0002" in output
    # TASK-0001 is distance 2 from TASK-0003 (TASK-0003 -> TASK-0002 -> TASK-0001), so at depth 1 it must NOT be present
    assert "TASK_0001" not in output
