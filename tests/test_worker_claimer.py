"""Unit and edge-case tests for autonomous task claimer and contract hydration."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from spec_ops.backlog.queue import write_task_file
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.worker.claimer import (
    TaskClaimer,
    hydrate_task_prompt,
    initialize_worktree,
    validate_definition_of_ready,
)


@pytest.fixture
def claimer_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="ClaimerTestApp", target_dir=repo)

    for d in ["refined", "proposed", "complete"]:
        p = repo / "docs" / "project" / "backlog" / d
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)

    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0004-fleet.md").write_text("---\nid: '0004'\nstatus: Accepted\n---\n# PRD-0004\n", encoding="utf-8")

    shaped_dir = repo / "docs" / "project" / "product" / "shaped"
    shaped_dir.mkdir(parents=True, exist_ok=True)
    (shaped_dir / "prd-0005-draft.md").write_text("---\nid: '0005'\nstatus: Shaped\n---\n# PRD-0005\n", encoding="utf-8")

    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "0002-modular-limits.md").write_text("---\nid: '0002'\nstatus: Accepted\n---\n# ADR-0002\n", encoding="utf-8")

    stories_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0002-evaluator.md").write_text(
        "---\nid: '0002'\nstatus: Accepted\n---\n# US-0002\n```gherkin\nScenario: Public\nGiven x\nWhen y\nThen z\n```\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    return repo


def test_validate_definition_of_ready_failures(claimer_repo: Path):
    cfg = load_config(claimer_repo)

    # 1. Missing PRDs
    t1 = Task(id="0010", title="No PRD", governing_adrs=["ADR-0002"], body="Scenario: A\nGiven B\nWhen C\nThen D\n")
    ok, errs = validate_definition_of_ready(t1, cfg)
    assert not ok
    assert errs == ["Task must link to at least one accepted PRD."]

    # 2. PRD not found
    t2 = Task(id="0010", title="Unknown PRD", governing_prds=["PRD-9999"], governing_adrs=["ADR-0002"], body="Scenario: A\n")
    ok, errs = validate_definition_of_ready(t2, cfg)
    assert not ok
    assert errs == [f"Governing PRD 'PRD-9999' could not be located under {cfg.prd_dir}."]

    # 3. PRD not accepted (in shaped)
    t3 = Task(id="0010", title="Shaped PRD", governing_prds=["PRD-0005"], governing_adrs=["ADR-0002"], body="Scenario: A\n")
    ok, errs = validate_definition_of_ready(t3, cfg)
    assert not ok
    assert errs == ["Governing PRD 'PRD-0005' is in 'shaped' stage; must be accepted."]

    # 4. Missing ADRs
    t4 = Task(id="0010", title="No ADR", governing_prds=["PRD-0004"], body="Scenario: A\n")
    ok, errs = validate_definition_of_ready(t4, cfg)
    assert not ok
    assert errs == ["Task must cite governing ADRs."]

    # 5. ADR not found
    t5 = Task(id="0010", title="Missing ADR", governing_prds=["PRD-0004"], governing_adrs=["ADR-9999"], body="Scenario: A\n")
    ok, errs = validate_definition_of_ready(t5, cfg)
    assert not ok
    adrs_dir = claimer_repo / "docs" / "project" / "adrs"
    assert errs == [f"Governing ADR 'ADR-9999' could not be located under {adrs_dir}."]

    # 6. Missing Gherkin
    t6 = Task(id="0010", title="No Gherkin", governing_prds=["PRD-0004"], governing_adrs=["ADR-0002"], body="Simple body with no tests")
    ok, errs = validate_definition_of_ready(t6, cfg)
    assert not ok
    assert errs == ["Task must link to executable Gherkin scenarios or specify acceptance criteria."]


def test_validate_definition_of_ready_success(claimer_repo: Path):
    cfg = load_config(claimer_repo)

    t1 = Task(
        id="0010",
        title="Ready Task",
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0002"],
        governing_stories=["US-0002"],
    )
    ok, errs = validate_definition_of_ready(t1, cfg)
    assert ok
    assert errs == []

    t2 = Task(
        id="0011",
        title="Inline Gherkin Task",
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0002"],
        body="## Criteria\nScenario: Verify something\nGiven state\nWhen event\nThen pass\n",
    )
    ok, errs = validate_definition_of_ready(t2, cfg)
    assert ok
    assert errs == []


def test_hydrate_task_prompt_exact_content(claimer_repo: Path):
    cfg = load_config(claimer_repo)
    task = Task(
        id="0012",
        title="Test Invariants",
        target_bc="worker",
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0002"],
        governing_stories=["US-0002"],
        body="Task details here",
    )

    prompt = hydrate_task_prompt(task, cfg)
    expected = (
        "# Task: TASK-0012 — Test Invariants\n\n"
        "## Architectural Context\n"
        "- Target Bounded Context: worker\n"
        "- Governing ADRs: ADR-0002\n"
        "- Governing PRDs: PRD-0004\n"
        "- Governing Stories: US-0002\n"
        "- File Length Invariant: Every new or edited source file must contain fewer than 500 lines "
        "(500-line file length limit invariant governed by ADR-0002).\n"
        "- Testing Invariant: Features must be verified blackbox style through public entry points without "
        "private backdoors (blackbox frontdoor verification rules with zero private mocks governed by ADR-0003).\n"
        "- Backlog Isolation: Files under docs/project/backlog/ must not be modified on feature branches. "
        "Accidental edits will be intercepted and discarded (ADR-0005).\n\n"
        "## Task Specification\n"
        "Task details here\n\n"
        "## Acceptance Criteria & Preflight\n"
        "Your modifications must pass the exact preflight command chain: `uv lock --check && uv run pytest && uv run spec-ops health`\n"
        "Ensure all tests pass cleanly before completing.\n"
    )
    assert prompt == expected

    # Default / empty fields
    empty_task = Task(
        id="0013",
        title="Empty Fields",
        body="Body only",
    )
    empty_prompt = hydrate_task_prompt(empty_task, cfg)
    assert "- Target Bounded Context: core" in empty_prompt
    assert "- Governing ADRs: None" in empty_prompt
    assert "- Governing PRDs: None" in empty_prompt
    assert "- Governing Stories: None" in empty_prompt


def test_initialize_worktree_provisions_and_hydrates(claimer_repo: Path):
    cfg = load_config(claimer_repo)
    task = Task(
        id="0016",
        title="Provisioning test",
        target_bc="core",
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0002"],
        governing_stories=["US-0002"],
    )

    wt = initialize_worktree(claimer_repo, task, cfg, branch="task/TASK-0016")
    assert wt == claimer_repo / ".worktrees" / "task-0016"
    assert wt.is_dir()
    prompt_file = wt / ".task-prompt.md"
    assert prompt_file.is_file()
    assert prompt_file.read_text(encoding="utf-8") == hydrate_task_prompt(task, cfg)


def test_claim_auto_missing_priority_file(claimer_repo: Path, capsys):
    cfg = load_config(claimer_repo)
    p_file = claimer_repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    if p_file.exists():
        p_file.unlink()

    claimer = TaskClaimer(cfg)
    res = claimer.claim_auto()
    assert res is None
    out, err = capsys.readouterr()
    assert err.strip() == "PRIORITY.md not found in backlog."


def test_claim_auto_dependency_and_dor_gates(claimer_repo: Path, capsys):
    cfg = load_config(claimer_repo)
    backlog = claimer_repo / "docs" / "project" / "backlog"

    # Task 1: Blocked by dep
    t1 = Task(
        id="0021",
        title="Blocked Task",
        status="Refined",
        dependencies=["TASK-0099"],
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0002"],
        governing_stories=["US-0002"],
        file_path=backlog / "refined" / "0021-blocked.md",
    )
    write_task_file(t1)

    # Task 2: Blocked by DoR (missing PRD)
    t2 = Task(
        id="0022",
        title="DoR Failure Task",
        status="Refined",
        dependencies=[],
        governing_adrs=["ADR-0002"],
        governing_stories=["US-0002"],
        file_path=backlog / "refined" / "0022-no-prd.md",
    )
    write_task_file(t2)

    # Task 3: Ready and unblocked!
    t3 = Task(
        id="0023",
        title="Ready Task",
        status="Refined",
        dependencies=[],
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0002"],
        governing_stories=["US-0002"],
        file_path=backlog / "refined" / "0023-ready.md",
    )
    write_task_file(t3)

    (backlog / "PRIORITY.md").write_text(
        "- **TASK-0021 (Refined)**: [`0021-blocked`](refined/0021-blocked.md)\n"
        "- **TASK-0022 (Refined)**: [`0022-no-prd`](refined/0022-no-prd.md)\n"
        "- **TASK-0023 (Refined)**: [`0023-ready`](refined/0023-ready.md)\n",
        encoding="utf-8",
    )

    claimer = TaskClaimer(cfg)
    res = claimer.claim_auto()
    assert res is not None
    assert res["task_id"] == "TASK-0023"
    assert res["title"] == "Ready Task"
    assert res["status"] == "Refined"
    assert res["target_bc"] == "core"
    assert res["branch"] == "task/TASK-0023"
    assert res["worktree_dir"] == str(claimer_repo / ".worktrees" / "task-0023")
    assert res["dependencies"] == []
    assert res["governing_adrs"] == ["ADR-0002"]
    assert res["governing_prds"] == ["PRD-0004"]
    assert res["governing_stories"] == ["US-0002"]

    out, err = capsys.readouterr()
    assert "Task TASK-0021 skipped: unsatisfied dependencies (TASK-0099)" in err
    assert "Task TASK-0022 skipped: failed Definition of Ready (Task must link to at least one accepted PRD.)" in err


def test_claim_auto_skips_proposed_and_already_claimed(claimer_repo: Path):
    cfg = load_config(claimer_repo)
    backlog = claimer_repo / "docs" / "project" / "backlog"

    t1 = Task(
        id="0025",
        title="Proposed Task",
        status="Proposed",
        file_path=backlog / "proposed" / "0025-prop.md",
    )
    write_task_file(t1)

    t2 = Task(
        id="0026",
        title="Claimed Task",
        status="Refined",
        claimed_by="worker-1",
        file_path=backlog / "refined" / "0026-claimed.md",
    )
    write_task_file(t2)

    (backlog / "PRIORITY.md").write_text(
        "- **TASK-0025 (Proposed)**: [`0025-prop`](proposed/0025-prop.md)\n"
        "- **TASK-0026 (Refined)**: [`0026-claimed`](refined/0026-claimed.md)\n",
        encoding="utf-8",
    )

    claimer = TaskClaimer(cfg)
    res = claimer.claim_auto()
    assert res is None


def test_claim_task_by_id(claimer_repo: Path, capsys):
    cfg = load_config(claimer_repo)
    backlog = claimer_repo / "docs" / "project" / "backlog"

    t = Task(
        id="0024",
        title="Specific Task",
        status="Refined",
        dependencies=[],
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0002"],
        governing_stories=["US-0002"],
        file_path=backlog / "refined" / "0024-specific.md",
    )
    write_task_file(t)

    claimer = TaskClaimer(cfg)
    res = claimer.claim_task("TASK-0024")
    assert res is not None
    assert res["task_id"] == "TASK-0024"

    # Non-existent task
    assert claimer.claim_task("TASK-9999") is None
    out, err = capsys.readouterr()
    assert "Task TASK-9999 not found in backlog." in err

    # Blocked task
    t_blocked = Task(
        id="0027",
        title="Blocked Specific",
        status="Refined",
        dependencies=["TASK-9999"],
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0002"],
        governing_stories=["US-0002"],
        file_path=backlog / "refined" / "0027-blocked.md",
    )
    write_task_file(t_blocked)
    assert claimer.claim_task("TASK-0027") is None
    out, err = capsys.readouterr()
    assert "Task TASK-0027 skipped: unsatisfied dependencies (TASK-9999)" in err

    # DoR failure task
    t_dor = Task(
        id="0028",
        title="DoR Specific",
        status="Refined",
        dependencies=[],
        file_path=backlog / "refined" / "0028-dor.md",
    )
    write_task_file(t_dor)
    assert claimer.claim_task("TASK-0028") is None
    out, err = capsys.readouterr()
    assert "Task TASK-0028 skipped: failed Definition of Ready" in err
