"""Executable BDD scenarios for US-0089 / TASK-0164: Task Dependency Deadlock Resolver.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0017; PRD-0005, PRD-0006; US-0089.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.cli.graph_handler import handle_graph_command
from spec_ops.cli.parser import build_parser
from spec_ops.config.models import SpecOpsConfig

scenarios("features/us_0089_deadlock_breaker.feature")


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    return {}


@given("a backlog task graph containing a cyclic dependency between Task A and Task B")
def step_cyclic_task_graph(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)

    t1 = backlog_dir / "0001-task-a.md"
    t1.write_text(
        """---
id: TASK-0001
title: Task A
status: Refined
dependencies:
  - TASK-0002
---
# Task A
""",
        encoding="utf-8",
    )

    t2 = backlog_dir / "0002-task-b.md"
    t2.write_text(
        """---
id: TASK-0002
title: Task B
status: Refined
dependencies:
  - TASK-0001
---
# Task B
""",
        encoding="utf-8",
    )

    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)


@when("the deadlock breaker analyzes the graph")
def step_run_deadlock_analyzer(bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    args = parser.parse_args(["graph", "deadlock"])
    ret = handle_graph_command(args, bdd_context["config"])
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out


@then("the circular dependency cycle is identified")
def step_assert_cycle_identified(bdd_context: dict[str, Any]) -> None:
    out = bdd_context["stdout"]
    assert "Dependency Deadlocks Detected" in out
    assert "TASK-0001" in out
    assert "TASK-0002" in out


@then("a minimal edge removal recommendation is generated")
def step_assert_minimal_edge_recommendation(bdd_context: dict[str, Any]) -> None:
    out = bdd_context["stdout"]
    assert "Recommended Minimal Cut Set" in out
    assert "Prune" in out or "Recommended Break" in out


@then("the command terminates with exit code 1")
def step_assert_exit_code_one(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] == 1


@given("a backlog task graph with valid topological ordering and zero cycles")
def step_acyclic_task_graph(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)

    t1 = backlog_dir / "0001-task-a.md"
    t1.write_text(
        """---
id: TASK-0001
title: Task A
status: Refined
dependencies:
  - TASK-0002
---
# Task A
""",
        encoding="utf-8",
    )

    t2 = backlog_dir / "0002-task-b.md"
    t2.write_text(
        """---
id: TASK-0002
title: Task B
status: Refined
dependencies: []
---
# Task B
""",
        encoding="utf-8",
    )

    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)


@then("the graph is confirmed acyclic")
def step_assert_graph_acyclic(bdd_context: dict[str, Any]) -> None:
    out = bdd_context["stdout"]
    assert "Zero dependency deadlocks or circular cycles detected" in out


@then("exits with code 0")
def step_assert_exit_code_zero(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] == 0
