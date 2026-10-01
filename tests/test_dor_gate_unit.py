"""Unit tests for Definition of Ready (DoR) gatekeeper and ticket health auditor."""

from __future__ import annotations

import argparse
from pathlib import Path
import pytest

from spec_ops.backlog.dor_gate import (
    ALL_DOR_RULES,
    RULE_BOUNDED_CONTEXT,
    RULE_FILE_LIMIT_SCOPE,
    RULE_GHERKIN_SCENARIOS,
    RULE_GOVERNING_ADRS,
    RULE_MUTATION_SCOPE,
    RULE_PERSONA_PRD,
    RULE_YAML_FRONTMATTER,
    DoRAuditReport,
    audit_task_health,
    validate_task_dor,
)
from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.cli.parser import build_parser
from spec_ops.cli.queue_handler import handle_queue_command, handle_verify_dor_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project


@pytest.fixture
def dor_env(tmp_path: Path) -> tuple[Path, SpecOpsConfig]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="DoRUnitTest", target_dir=repo)
    cfg = SpecOpsConfig(root_dir=repo)

    # Scaffold accepted ADR
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "0001-adr.md").write_text("---\nid: '0001'\nstatus: Accepted\n---\n", encoding="utf-8")

    # Scaffold accepted PRD
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "0001-prd.md").write_text("---\nid: '0001'\nstatus: Accepted\ntarget_persona: Jordan\n---\n", encoding="utf-8")

    # Scaffold accepted User Story
    stories_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0001-story.md").write_text(
        """---
id: '0001'
status: Accepted
persona: Jordan
---
Scenario: Primary journey
Given a ready system
When action happens
Then result occurs
""",
        encoding="utf-8",
    )

    return repo, cfg


def test_dor_rule_yaml_frontmatter(dor_env: tuple[Path, SpecOpsConfig]):
    _, cfg = dor_env
    task_missing_id = Task(id="", title="Title", status="Proposed", target_bc="core")
    rep = audit_task_health(task_missing_id, cfg)
    assert not rep.rules[RULE_YAML_FRONTMATTER]
    assert any("YAML frontmatter" in err for err in rep.errors)

    task_missing_title = Task(id="0001", title="  ", status="Proposed", target_bc="core")
    rep2 = audit_task_health(task_missing_title, cfg)
    assert not rep2.rules[RULE_YAML_FRONTMATTER]

    task_missing_status = Task(id="0001", title="Title", status="", target_bc="core")
    rep3 = audit_task_health(task_missing_status, cfg)
    assert not rep3.rules[RULE_YAML_FRONTMATTER]


def test_dor_rule_bounded_context(dor_env: tuple[Path, SpecOpsConfig]):
    _, cfg = dor_env
    task_no_bc = Task(id="0001", title="Title", status="Proposed", target_bc="")
    rep = audit_task_health(task_no_bc, cfg)
    assert not rep.rules[RULE_BOUNDED_CONTEXT]
    assert any("target bounded context" in err for err in rep.errors)

    task_with_bc = Task(id="0001", title="Title", status="Proposed", target_bc="core")
    rep2 = audit_task_health(task_with_bc, cfg)
    assert rep2.rules[RULE_BOUNDED_CONTEXT]


def test_dor_rule_scope_and_file_limits(dor_env: tuple[Path, SpecOpsConfig]):
    _, cfg = dor_env
    # Multi-BC text mention
    task_multi_bc_text = Task(
        id="0001",
        title="Oversized",
        status="Proposed",
        target_bc="core",
        body="Proposes modifying 4 different bounded contexts.",
    )
    rep = audit_task_health(task_multi_bc_text, cfg)
    assert not rep.rules[RULE_FILE_LIMIT_SCOPE]
    assert any("violates single-responsibility scope" in err for err in rep.errors)
    assert any("Decompose into thin vertical slices" in rec for rec in rep.recommendations)

    # Multi-BC via target_bcs
    task_multi_bcs = {
        "id": "0001",
        "title": "Oversized",
        "status": "Proposed",
        "target_bc": "core",
        "target_bcs": ["core", "backlog", "security"],
    }
    rep_bcs = audit_task_health(task_multi_bcs, cfg)
    assert not rep_bcs.rules[RULE_FILE_LIMIT_SCOPE]

    # Exceeding 500 expected lines
    task_long_lines = Task(
        id="0001",
        title="Long",
        status="Proposed",
        target_bc="core",
        expected_lines=600,
    )
    rep_lines = audit_task_health(task_long_lines, cfg)
    assert not rep_lines.rules[RULE_FILE_LIMIT_SCOPE]

    # Text mention spanning >500 expected lines
    task_long_text = Task(
        id="0001",
        title="Long Text",
        status="Proposed",
        target_bc="core",
        body="spanning >500 expected lines of implementation",
    )
    rep_text = audit_task_health(task_long_text, cfg)
    assert not rep_text.rules[RULE_FILE_LIMIT_SCOPE]


def test_dor_rule_governing_adrs(dor_env: tuple[Path, SpecOpsConfig]):
    repo, cfg = dor_env
    # Missing ADRs
    t_no_adr = Task(id="0001", title="Title", status="Proposed", target_bc="core", governing_adrs=[])
    rep = audit_task_health(t_no_adr, cfg)
    assert not rep.rules[RULE_GOVERNING_ADRS]

    # Non-existent ADR
    t_missing_adr = Task(id="0001", title="Title", status="Proposed", target_bc="core", governing_adrs=["ADR-9999"])
    rep2 = audit_task_health(t_missing_adr, cfg)
    assert not rep2.rules[RULE_GOVERNING_ADRS]
    assert any("ADR-9999 not found" in err for err in rep2.errors)

    # Proposed ADR (not accepted)
    draft_dir = repo / "docs" / "project" / "adrs" / "proposed"
    draft_dir.mkdir(parents=True, exist_ok=True)
    (draft_dir / "0088-draft.md").write_text("---\nid: '0088'\nstatus: Proposed\n---\n", encoding="utf-8")
    t_draft_adr = Task(id="0001", title="Title", status="Proposed", target_bc="core", governing_adrs=["ADR-0088"])
    rep3 = audit_task_health(t_draft_adr, cfg)
    assert not rep3.rules[RULE_GOVERNING_ADRS]

    # Valid accepted ADR
    t_valid_adr = Task(id="0001", title="Title", status="Proposed", target_bc="core", governing_adrs=["ADR-0001"])
    rep4 = audit_task_health(t_valid_adr, cfg)
    assert rep4.rules[RULE_GOVERNING_ADRS]


def test_dor_rule_persona_and_prd(dor_env: tuple[Path, SpecOpsConfig]):
    repo, cfg = dor_env
    # Missing PRD
    t_no_prd = Task(id="0001", title="Title", status="Proposed", target_bc="core", governing_prds=[])
    rep = audit_task_health(t_no_prd, cfg)
    assert not rep.rules[RULE_PERSONA_PRD]

    # Non-existent PRD
    t_missing_prd = Task(id="0001", title="Title", status="Proposed", target_bc="core", governing_prds=["PRD-9999"])
    rep2 = audit_task_health(t_missing_prd, cfg)
    assert not rep2.rules[RULE_PERSONA_PRD]

    # PRD valid but no persona anywhere
    empty_prd = repo / "docs" / "project" / "product" / "accepted" / "0002-empty.md"
    empty_prd.write_text("---\nid: '0002'\nstatus: Accepted\n---\n", encoding="utf-8")
    t_no_persona = Task(id="0001", title="Title", status="Proposed", target_bc="core", governing_prds=["PRD-0002"])
    rep3 = audit_task_health(t_no_persona, cfg)
    assert not rep3.rules[RULE_PERSONA_PRD]
    assert any("Missing linked persona" in err for err in rep3.errors)

    # Persona via task frontmatter
    t_persona_task = Task(id="0001", title="Title", status="Proposed", target_bc="core", governing_prds=["PRD-0002"], persona="Jordan")
    rep4 = audit_task_health(t_persona_task, cfg)
    assert rep4.rules[RULE_PERSONA_PRD]

    # Persona via known persona in text
    t_persona_text = Task(id="0001", title="Title", status="Proposed", target_bc="core", governing_prds=["PRD-0002"], body="As Morgan, I want to code")
    rep5 = audit_task_health(t_persona_text, cfg)
    assert rep5.rules[RULE_PERSONA_PRD]

    # Persona via PRD frontmatter
    t_persona_prd = Task(id="0001", title="Title", status="Proposed", target_bc="core", governing_prds=["PRD-0001"])
    rep6 = audit_task_health(t_persona_prd, cfg)
    assert rep6.rules[RULE_PERSONA_PRD]


def test_dor_rule_executable_gherkin_scenarios(dor_env: tuple[Path, SpecOpsConfig]):
    _, cfg = dor_env
    # Missing Gherkin
    t_no_gherkin = Task(id="0001", title="Title", status="Proposed", target_bc="core", body="Just some notes without keywords")
    rep = audit_task_health(t_no_gherkin, cfg)
    assert not rep.rules[RULE_GHERKIN_SCENARIOS]
    assert any("Missing executable Gherkin acceptance criteria (ADR-0006)" in err for err in rep.errors)

    # Gherkin in task body
    t_gherkin = Task(
        id="0001",
        title="Title",
        status="Proposed",
        target_bc="core",
        body="Given a system\nWhen an action runs\nThen output matches",
    )
    rep2 = audit_task_health(t_gherkin, cfg)
    assert rep2.rules[RULE_GHERKIN_SCENARIOS]

    # Gherkin in linked story
    t_gherkin_story = Task(
        id="0001",
        title="Title",
        status="Proposed",
        target_bc="core",
        governing_stories=["US-0001"],
        body="No gherkin in task body",
    )
    rep3 = audit_task_health(t_gherkin_story, cfg)
    assert rep3.rules[RULE_GHERKIN_SCENARIOS]


def test_dor_rule_mutation_scope(dor_env: tuple[Path, SpecOpsConfig]):
    _, cfg = dor_env
    # Missing mutation scope
    t_no_mut = Task(id="0001", title="Title", status="Proposed", target_bc="core", body="No mutation info")
    rep = audit_task_health(t_no_mut, cfg)
    assert not rep.rules[RULE_MUTATION_SCOPE]
    assert any("Missing mutation testing scope" in err for err in rep.errors)

    # Mutation scope in frontmatter
    t_mut_fm = Task(id="0001", title="Title", status="Proposed", target_bc="core", mutation_scope="src/spec_ops/core")
    rep2 = audit_task_health(t_mut_fm, cfg)
    assert rep2.rules[RULE_MUTATION_SCOPE]

    # Mutation scope in text
    t_mut_text = Task(id="0001", title="Title", status="Proposed", target_bc="core", body="Run mutmut for mutation testing scope")
    rep3 = audit_task_health(t_mut_text, cfg)
    assert rep3.rules[RULE_MUTATION_SCOPE]


def test_dorauditreport_format_report():
    report = DoRAuditReport(
        task_id="TASK-0042",
        is_ready=False,
        rules={r: True for r in ALL_DOR_RULES},
        errors=["Missing something"],
        recommendations=["Decompose the task"],
    )
    report.rules[RULE_GHERKIN_SCENARIOS] = False
    text = report.format_report()
    assert "=== Definition of Ready (DoR) Audit: TASK-0042 ===" in text
    assert "Rule Check                         | Status" in text
    assert "Executable Gherkin Scenarios       | Fail" in text
    assert "Complete YAML frontmatter          | Pass" in text
    assert "Violations:" in text
    assert "❌ Missing something" in text
    assert "Recommendations:" in text
    assert "💡 Decompose the task" in text


def test_validate_task_dor_helper(dor_env: tuple[Path, SpecOpsConfig]):
    _, cfg = dor_env
    task_valid = Task(
        id="0001",
        title="Compliant",
        status="Proposed",
        target_bc="core",
        governing_adrs=["ADR-0001"],
        governing_prds=["PRD-0001"],
        governing_stories=["US-0001"],
        mutation_scope="src/core",
        body="Given a precondition\nWhen an action executes\nThen output is valid",
    )
    ok, errors = validate_task_dor(task_valid, cfg)
    assert ok is True
    assert len(errors) == 0


def test_cli_queue_refine_and_verify_dor(dor_env: tuple[Path, SpecOpsConfig], capsys: pytest.CaptureFixture[str]):
    repo, cfg = dor_env
    queue = BacklogQueue(cfg.backlog_dir)
    parser = build_parser()

    # Create invalid proposed task
    invalid_file = cfg.backlog_dir / "proposed" / "0010-invalid.md"
    invalid_task = Task(id="0010", title="Invalid", status="Proposed", target_bc="core", file_path=invalid_file)
    write_task_file(invalid_task)

    # Run queue refine on invalid task
    args_fail = argparse.Namespace(queue_action="refine", task_id="TASK-0010", strict=False)
    ret_fail = handle_queue_command(args_fail, cfg, parser)
    out_fail, _ = capsys.readouterr()
    assert ret_fail == 1
    assert "=== Definition of Ready (DoR) Audit: TASK-0010 ===" in out_fail
    assert (cfg.backlog_dir / "proposed" / "0010-invalid.md").is_file()

    # Run backlog verify-dor on invalid task
    args_verify = argparse.Namespace(task_id="TASK-0010", strict=False)
    ret_verify = handle_verify_dor_command(args_verify, cfg)
    out_verify, _ = capsys.readouterr()
    assert ret_verify == 1
    assert "=== Definition of Ready (DoR) Audit: TASK-0010 ===" in out_verify

    # Create valid proposed task
    valid_file = cfg.backlog_dir / "proposed" / "0020-valid.md"
    valid_task = Task(
        id="0020",
        title="Valid Task",
        status="Proposed",
        target_bc="core",
        governing_adrs=["ADR-0001"],
        governing_prds=["PRD-0001"],
        governing_stories=["US-0001"],
        mutation_scope="src/core",
        body="Given valid inputs\nWhen executed\nThen success",
        file_path=valid_file,
    )
    write_task_file(valid_task)

    # Run queue refine on valid task
    args_ok = argparse.Namespace(queue_action="refine", task_id="TASK-0020", strict=False)
    ret_ok = handle_queue_command(args_ok, cfg, parser)
    out_ok, _ = capsys.readouterr()
    assert ret_ok == 0
    assert "Promoted task TASK-0020 to refined/" in out_ok
    assert (cfg.backlog_dir / "refined" / "0020-valid.md").is_file()
    assert not (cfg.backlog_dir / "proposed" / "0020-valid.md").is_file()
