"""Executable BDD scenarios for US-0106 / TASK-0165: Living ADR Supersession Engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007; PRD-0005; US-0106.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.cli.adr_handler import handle_adr_command
from spec_ops.cli.parser import build_parser
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.parser import extract_frontmatter

scenarios("features/us_0106_adr_supersession.feature")


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    return {}


@given('an existing accepted ADR in "docs/project/adrs/accepted/"')
def step_given_accepted_adr(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    adrs_dir = tmp_path / "docs" / "project" / "adrs"
    accepted_dir = adrs_dir / "accepted"
    accepted_dir.mkdir(parents=True, exist_ok=True)

    adr1 = accepted_dir / "adr-0001-flat-json-storage.md"
    adr1.write_text(
        """---
id: ADR-0001
title: Flat JSON Storage
status: Accepted
date: 2026-01-01
---

# ADR-0001: Flat JSON Storage

## Status
Accepted

## Context
Initial flat file persistence.
""",
        encoding="utf-8",
    )

    registry = adrs_dir / "REGISTRY.md"
    registry.write_text(
        """# ADR Registry

| ID | Title | Status | Superseded By |
|---|---|---|---|
| [ADR-0001](file://accepted/adr-0001-flat-json-storage.md) | Flat JSON Storage | Accepted | - |
""",
        encoding="utf-8",
    )

    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)
    bdd_context["old_adr"] = adr1
    bdd_context["registry"] = registry


@when("the architect runs spec-ops adr supersede with the target ADR ID and new title")
def step_when_supersede_target(
    bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["adr", "supersede", "--old", "ADR-0001", "--title", "SQLite Storage Engine"]
    )
    ret = handle_adr_command(args, bdd_context["config"])
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out
    bdd_context["stderr"] = captured.err


@then("the old ADR is updated with status Superseded and superseded_by pointer")
def step_then_old_adr_superseded(bdd_context: dict[str, Any]) -> None:
    old_file: Path = bdd_context["old_adr"]
    meta, body = extract_frontmatter(old_file.read_text(encoding="utf-8"))
    assert meta["status"] == "Superseded"
    assert meta["superseded_by"] == "ADR-0002"
    assert "Superseded (by ADR-0002)" in body


@then("a new ADR is created with supersedes pointer")
def step_then_new_adr_created(bdd_context: dict[str, Any]) -> None:
    new_adr = (
        bdd_context["root_dir"]
        / "docs"
        / "project"
        / "adrs"
        / "accepted"
        / "adr-0002-sqlite-storage-engine.md"
    )
    assert new_adr.exists()
    meta, body = extract_frontmatter(new_adr.read_text(encoding="utf-8"))
    assert meta["id"] == "ADR-0002"
    assert meta["title"] == "SQLite Storage Engine"
    assert meta["status"] == "Accepted"
    assert meta["supersedes"] == "ADR-0001"
    assert "We supersede `ADR-0001` with `ADR-0002`" in body


@then("docs/project/adrs/REGISTRY.md reflects the updated statuses")
def step_then_registry_updated(bdd_context: dict[str, Any]) -> None:
    registry_file: Path = bdd_context["registry"]
    text = registry_file.read_text(encoding="utf-8")
    assert "Superseded" in text
    assert "ADR-0002" in text
    assert "SQLite Storage Engine" in text


@given("an ADR that already supersedes another decision")
def step_given_superseding_adr_pair(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    adrs_dir = tmp_path / "docs" / "project" / "adrs"
    accepted_dir = adrs_dir / "accepted"
    accepted_dir.mkdir(parents=True, exist_ok=True)

    adr1 = accepted_dir / "adr-0001-legacy.md"
    adr1.write_text(
        """---
id: ADR-0001
title: Legacy
status: Superseded
superseded_by: ADR-0002
---
# ADR-0001: Legacy
""",
        encoding="utf-8",
    )

    adr2 = accepted_dir / "adr-0002-modern.md"
    adr2.write_text(
        """---
id: ADR-0002
title: Modern
status: Accepted
supersedes: ADR-0001
---
# ADR-0002: Modern
""",
        encoding="utf-8",
    )

    registry = adrs_dir / "REGISTRY.md"
    registry.write_text("# Registry\n", encoding="utf-8")

    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)
    bdd_context["adr1"] = adr1
    bdd_context["adr2"] = adr2
    bdd_context["adr1_initial"] = adr1.read_text(encoding="utf-8")
    bdd_context["adr2_initial"] = adr2.read_text(encoding="utf-8")


@when("an attempt is made to create a circular supersession cycle")
def step_when_create_circular_cycle(
    bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    # Attempting to make ADR-0002 superseded by ADR-0001 -> cycle!
    parser = build_parser()
    args = parser.parse_args(["adr", "supersede", "ADR-0002", "--by", "ADR-0001"])
    ret = handle_adr_command(args, bdd_context["config"])
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out
    bdd_context["stderr"] = captured.err


@then("the operation is rejected with an error message")
def step_then_operation_rejected(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] != 0
    assert "circular" in bdd_context["stderr"].lower() or "circular" in bdd_context["stdout"].lower()


@then("the existing ADR files remain unmodified")
def step_then_files_unmodified(bdd_context: dict[str, Any]) -> None:
    adr1: Path = bdd_context["adr1"]
    adr2: Path = bdd_context["adr2"]
    assert adr1.read_text(encoding="utf-8") == bdd_context["adr1_initial"]
    assert adr2.read_text(encoding="utf-8") == bdd_context["adr2_initial"]
