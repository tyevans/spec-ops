"""Executable BDD scenarios for US-0130 / TASK-0253: ADR Amendment Workflow and Frontmatter Lineage Tracking.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007; PRD-0005; US-0130.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any
import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.adrs.amend import CircularAmendmentError, discover_amended_adrs
from spec_ops.adrs.amendment import ADRAmendmentEngine
from spec_ops.backlog.dor_gate import audit_task_health
from spec_ops.backlog.reconciler import ArchitecturalReconciler
from spec_ops.cli.adr_handler import handle_adr_command
from spec_ops.cli.parser import build_parser
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.core.parser import extract_frontmatter

scenarios("features/us_0130_adr_amendment.feature")


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    return {}


# --- Scenario 1: Amending an accepted ADR with a new incremental decision via CLI ---


@given('an accepted ADR "ADR-0101: Event Log Schema and Granularity" in "docs/project/adrs/accepted/"')
def step_given_accepted_adr_0101(bdd_ctx: dict[str, Any], tmp_path: Path) -> None:
    adrs_dir = tmp_path / "docs" / "project" / "adrs"
    accepted_dir = adrs_dir / "accepted"
    accepted_dir.mkdir(parents=True, exist_ok=True)

    adr101 = accepted_dir / "adr-0101-event-log-schema-and-granularity.md"
    adr101.write_text(
        """---
id: ADR-0101
title: Event Log Schema and Granularity
status: Accepted
date: 2026-02-01
---

# ADR-0101: Event Log Schema and Granularity

## Status
Accepted

## Context
Foundational event log schema.
""",
        encoding="utf-8",
    )

    registry = adrs_dir / "REGISTRY.md"
    registry.write_text(
        """# ADR Registry

| ID | Title | Status | Date |
|---|---|---|---|
| ADR-0101 | Event Log Schema and Granularity | Accepted | 2026-02-01 |
""",
        encoding="utf-8",
    )

    bdd_ctx["root_dir"] = tmp_path
    bdd_ctx["config"] = SpecOpsConfig(root_dir=tmp_path)
    bdd_ctx["adr101"] = adr101
    bdd_ctx["registry"] = registry


@when('the architect runs "spec-ops adr amend ADR-0101 --title \'Provenance Value Object Schema\'"')
def step_when_amend_adr_0101(bdd_ctx: dict[str, Any]) -> None:
    parser = build_parser()
    args = parser.parse_args(["adr", "amend", "ADR-0101", "--title", "Provenance Value Object Schema"])
    rc = handle_adr_command(args, bdd_ctx["config"])
    assert rc == 0


@then('a new ADR is scaffolded in "docs/project/adrs/accepted/" with frontmatter "amends: [ADR-0101]"')
def step_then_new_adr_scaffolded(bdd_ctx: dict[str, Any]) -> None:
    accepted_dir = bdd_ctx["root_dir"] / "docs" / "project" / "adrs" / "accepted"
    new_files = [p for p in accepted_dir.glob("*.md") if "provenance" in p.name.lower()]
    assert len(new_files) == 1
    new_adr_file = new_files[0]
    meta, _ = extract_frontmatter(new_adr_file.read_text(encoding="utf-8"))
    assert "ADR-0101" in [str(x).upper() for x in meta.get("amends", [])]
    assert meta.get("status") == "Accepted"
    bdd_ctx["new_adr_file"] = new_adr_file
    bdd_ctx["new_adr_id"] = str(meta.get("id"))


@then('the target ADR "ADR-0101" frontmatter appends the new ADR to its "amended_by" list')
def step_then_target_appends_amended_by(bdd_ctx: dict[str, Any]) -> None:
    meta, _ = extract_frontmatter(bdd_ctx["adr101"].read_text(encoding="utf-8"))
    amended_by = [str(x).upper() for x in meta.get("amended_by", [])]
    assert bdd_ctx["new_adr_id"] in amended_by


@then('the target ADR "ADR-0101" maintains status "Accepted"')
def step_then_target_maintains_status_accepted(bdd_ctx: dict[str, Any]) -> None:
    meta, _ = extract_frontmatter(bdd_ctx["adr101"].read_text(encoding="utf-8"))
    assert meta.get("status") in ("Accepted", "Accepted (Amended)")


@then('"docs/project/adrs/REGISTRY.md" is synchronized to reflect the amendment relationship without marking ADR-0101 as Superseded')
def step_then_registry_synchronized(bdd_ctx: dict[str, Any]) -> None:
    registry_text = bdd_ctx["registry"].read_text(encoding="utf-8")
    for line in registry_text.splitlines():
        if "ADR-0101" in line:
            assert "Superseded" not in line
            assert "Accepted" in line
        if bdd_ctx["new_adr_id"] in line:
            assert "Accepted" in line


# --- Scenario 2: Linking an amendment to an existing draft ADR ---


@given('an accepted ADR "ADR-0102: Two Store Ports"')
def step_given_accepted_adr_0102(bdd_ctx: dict[str, Any], tmp_path: Path) -> None:
    adrs_dir = tmp_path / "docs" / "project" / "adrs"
    accepted_dir = adrs_dir / "accepted"
    accepted_dir.mkdir(parents=True, exist_ok=True)

    adr102 = accepted_dir / "adr-0102-two-store-ports.md"
    adr102.write_text(
        """---
id: ADR-0102
title: Two Store Ports
status: Accepted
date: 2026-02-05
---

# ADR-0102: Two Store Ports
""",
        encoding="utf-8",
    )
    bdd_ctx["root_dir"] = tmp_path
    bdd_ctx["config"] = SpecOpsConfig(root_dir=tmp_path)
    bdd_ctx["adr102"] = adr102


@given('a drafted ADR "docs/project/adrs/proposed/adr-0116-graph-store-is-five-capabilities.md"')
def step_given_drafted_adr_0116(bdd_ctx: dict[str, Any]) -> None:
    proposed_dir = bdd_ctx["root_dir"] / "docs" / "project" / "adrs" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)

    adr116 = proposed_dir / "adr-0116-graph-store-is-five-capabilities.md"
    adr116.write_text(
        """---
id: ADR-0116
title: Graph Store Is Five Capabilities
status: Proposed
date: 2026-03-01
---

# ADR-0116: Graph Store Is Five Capabilities
""",
        encoding="utf-8",
    )
    bdd_ctx["adr116_proposed"] = adr116


@when('the architect runs "spec-ops adr amend ADR-0102 --by docs/project/adrs/proposed/adr-0116-graph-store-is-five-capabilities.md"')
def step_when_amend_by_proposed(bdd_ctx: dict[str, Any]) -> None:
    parser = build_parser()
    target_path = str(bdd_ctx["adr116_proposed"])
    args = parser.parse_args(["adr", "amend", "ADR-0102", "--by", target_path])
    rc = handle_adr_command(args, bdd_ctx["config"])
    assert rc == 0


@then('"ADR-0116" is promoted to "docs/project/adrs/accepted/" with frontmatter "amends: [ADR-0102]"')
def step_then_adr_promoted_to_accepted(bdd_ctx: dict[str, Any]) -> None:
    accepted_file = bdd_ctx["root_dir"] / "docs" / "project" / "adrs" / "accepted" / "adr-0116-graph-store-is-five-capabilities.md"
    assert accepted_file.exists()
    meta, _ = extract_frontmatter(accepted_file.read_text(encoding="utf-8"))
    assert meta.get("status") == "Accepted"
    assert "ADR-0102" in [str(x).upper() for x in meta.get("amends", [])]


@then('"ADR-0102" records "amended_by: [ADR-0116]" in its YAML frontmatter')
def step_then_adr102_records_amended_by(bdd_ctx: dict[str, Any]) -> None:
    meta, _ = extract_frontmatter(bdd_ctx["adr102"].read_text(encoding="utf-8"))
    assert "ADR-0116" in [str(x).upper() for x in meta.get("amended_by", [])]


@then("both decisions remain active architectural authorities")
def step_then_both_decisions_remain_active(bdd_ctx: dict[str, Any]) -> None:
    meta102, _ = extract_frontmatter(bdd_ctx["adr102"].read_text(encoding="utf-8"))
    accepted_116 = bdd_ctx["root_dir"] / "docs" / "project" / "adrs" / "accepted" / "adr-0116-graph-store-is-five-capabilities.md"
    meta116, _ = extract_frontmatter(accepted_116.read_text(encoding="utf-8"))
    assert meta102.get("status") in ("Accepted", "Accepted (Amended)")
    assert meta116.get("status") == "Accepted"


# --- Scenario 3: Preserving active status and backlog task validity for amended ADRs ---


@given('an accepted ADR "ADR-0101" that has been amended by "ADR-0135" and "ADR-0136"')
def step_given_amended_adr_0101_chain(bdd_ctx: dict[str, Any], tmp_path: Path) -> None:
    adrs_dir = tmp_path / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    stories_dir = tmp_path / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)

    # Scaffold ADRs
    (adrs_dir / "adr-0101.md").write_text(
        "---\nid: ADR-0101\ntitle: Event Log Schema\nstatus: Accepted\namended_by:\n  - ADR-0135\n  - ADR-0136\n---\n# ADR-0101\n",
        encoding="utf-8",
    )
    (adrs_dir / "adr-0135.md").write_text(
        "---\nid: ADR-0135\ntitle: Schema Delta A\nstatus: Accepted\namends:\n  - ADR-0101\n---\n# ADR-0135\n",
        encoding="utf-8",
    )
    (adrs_dir / "adr-0136.md").write_text(
        "---\nid: ADR-0136\ntitle: Schema Delta B\nstatus: Accepted\namends:\n  - ADR-0101\n---\n# ADR-0136\n",
        encoding="utf-8",
    )

    # PRD & User Story
    (prd_dir / "prd-0001-core.md").write_text(
        "---\nid: '0001'\ntitle: Core System\nstatus: Accepted\ntarget_persona: Alex\ncomponent: core\n---\n# PRD-0001\n",
        encoding="utf-8",
    )
    (stories_dir / "us-0001-core.md").write_text(
        "---\nid: '0001'\ntitle: Core Feature\nstatus: Accepted\npersona: Alex\ntarget_bc: core\ngoverning_prd: PRD-0001\n---\n# US-0001\n",
        encoding="utf-8",
    )

    bdd_ctx["root_dir"] = tmp_path
    bdd_ctx["config"] = SpecOpsConfig(root_dir=tmp_path)


@given('an active task "TASK-0042" in "docs/project/backlog/refined/" citing "governing_adrs: [ADR-0101]"')
def step_given_active_task_citing_adr101(bdd_ctx: dict[str, Any]) -> None:
    refined_dir = bdd_ctx["root_dir"] / "docs" / "project" / "backlog" / "refined"
    task_file = refined_dir / "0042-active-task.md"
    task_file.write_text(
        """---
id: '0042'
title: Active Event Task
status: Refined
target_bc: core
persona: Alex
governing_adrs:
  - ADR-0101
governing_prds:
  - PRD-0001
governing_stories:
  - US-0001
mutation_scope:
  - src/spec_ops/core
---

# TASK-0042: Active Event Task

```gherkin
Scenario: Basic execution
  Given state
  When action
  Then outcome
```
""",
        encoding="utf-8",
    )
    bdd_ctx["task_file"] = task_file
    bdd_ctx["task_model"] = Task(
        id="0042",
        title="Active Event Task",
        status="Refined",
        target_bc="core",
        persona="Alex",
        governing_adrs=["ADR-0101"],
        governing_prds=["PRD-0001"],
        governing_stories=["US-0001"],
        mutation_scope=["src/spec_ops/core"],
        file_path=task_file,
        body="```gherkin\nScenario: Basic execution\n```",
    )


@when('the architect runs "spec-ops health" or "spec-ops check"')
def step_when_health_or_check_runs(bdd_ctx: dict[str, Any]) -> None:
    report = audit_task_health(bdd_ctx["task_model"], bdd_ctx["config"])
    bdd_ctx["dor_report"] = report

    reconciler = ArchitecturalReconciler(bdd_ctx["root_dir"])
    rec_result = reconciler.reconcile_task(bdd_ctx["task_model"])
    bdd_ctx["rec_result"] = rec_result


@then("the task passes the Definition of Ready (DoR) governing ADR gate")
def step_then_task_passes_dor(bdd_ctx: dict[str, Any]) -> None:
    report = bdd_ctx["dor_report"]
    assert report.rules.get("Cited Governing ADRs") is True


@then('"spec-ops reconciler" does not replace ADR-0101 with ADR-0136')
def step_then_reconciler_does_not_replace(bdd_ctx: dict[str, Any]) -> None:
    rec_result = bdd_ctx["rec_result"]
    assert "ADR-0101" in rec_result.task.governing_adrs
    assert "ADR-0136" not in rec_result.task.governing_adrs


@then("the audit report notes that ADR-0101 has active amendments [ADR-0135, ADR-0136]")
def step_then_audit_report_notes_amendments(bdd_ctx: dict[str, Any]) -> None:
    rec_result = bdd_ctx["rec_result"]
    details_str = " ".join(c.details for c in rec_result.diff.changes)
    assert "ADR-0135" in details_str
    assert "ADR-0136" in details_str


# --- Scenario 4: Detecting and rejecting circular amendment chains ---


@given("ADR-0110 already amends ADR-0105")
def step_given_adr110_amends_adr105(bdd_ctx: dict[str, Any], tmp_path: Path) -> None:
    adrs_dir = tmp_path / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)

    f105 = adrs_dir / "adr-0105-foundation.md"
    f105.write_text(
        "---\nid: ADR-0105\ntitle: Foundation\nstatus: Accepted\namended_by:\n  - ADR-0110\n---\n# ADR-0105\n",
        encoding="utf-8",
    )
    f110 = adrs_dir / "adr-0110-amendment.md"
    f110.write_text(
        "---\nid: ADR-0110\ntitle: Amendment\nstatus: Accepted\namends:\n  - ADR-0105\n---\n# ADR-0110\n",
        encoding="utf-8",
    )
    bdd_ctx["root_dir"] = tmp_path
    bdd_ctx["config"] = SpecOpsConfig(root_dir=tmp_path)
    bdd_ctx["f105"] = f105
    bdd_ctx["f110"] = f110
    bdd_ctx["f105_content_before"] = f105.read_text(encoding="utf-8")
    bdd_ctx["f110_content_before"] = f110.read_text(encoding="utf-8")


@when('an attempt is made to execute "spec-ops adr amend ADR-0110 --by ADR-0105"')
def step_when_circular_amend_attempted(bdd_ctx: dict[str, Any]) -> None:
    engine = ADRAmendmentEngine(root_dir=bdd_ctx["root_dir"])
    with pytest.raises(CircularAmendmentError) as exc_info:
        engine.amend(old_target="ADR-0110", new_target="ADR-0105")
    bdd_ctx["captured_exception"] = exc_info.value


@then("the amendment operation is aborted with a CircularAmendmentError")
def step_then_aborted_with_circular_error(bdd_ctx: dict[str, Any]) -> None:
    assert isinstance(bdd_ctx["captured_exception"], CircularAmendmentError)


@then("all existing ADR frontmatters remain unmodified")
def step_then_existing_adr_frontmatters_unmodified(bdd_ctx: dict[str, Any]) -> None:
    assert bdd_ctx["f105"].read_text(encoding="utf-8") == bdd_ctx["f105_content_before"]
    assert bdd_ctx["f110"].read_text(encoding="utf-8") == bdd_ctx["f110_content_before"]
