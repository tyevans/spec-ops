"""BDD step definitions for US-0117: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Coordination."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.cli.main import build_parser
from spec_ops.cli.worker_handler import handle_worker_orchestrate
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.worker.ast_analyzer import format_preflight_ast_feedback, generate_ast_decomposition_hint
from spec_ops.worker.consultation import (
    PeerConsultationReview,
    WorkerOrchestrator,
    conduct_peer_consultation,
    consult_specifications,
)

scenarios("features/us_0117_worker_orchestrate.feature")


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parent.parent
    cfg = load_config(repo_root)
    return {"repo_root": repo_root, "config": cfg}


@given(parsers.parse('an implementation subagent working in an isolated worktree on "{task_id}"'))
def setup_subagent_task(bdd_ctx: dict[str, Any], task_id: str, tmp_path: Path):
    bdd_ctx["task"] = Task(
        id=task_id,
        title="Multi-Agent In-Worktree Implementation, Peer Consultation, and Verification Loop",
        governing_adrs=["ADR-0001", "ADR-0002", "ADR-0003", "ADR-0005"],
        governing_prds=["PRD-0006"],
        governing_stories=["US-0117"],
        target_bc="worker",
    )
    bdd_ctx["worktree_dir"] = tmp_path


@when("the subagent defines an interface change touching another bounded context")
def subagent_touches_cross_bc(bdd_ctx: dict[str, Any]):
    wt_dir: Path = bdd_ctx["worktree_dir"]
    foreign_file = wt_dir / "src" / "spec_ops" / "prd" / "foreign_interface.py"
    foreign_file.parent.mkdir(parents=True, exist_ok=True)
    foreign_file.write_text("class ForeignInterface:\n    pass\n", encoding="utf-8")

    bdd_ctx["review"] = conduct_peer_consultation(
        bdd_ctx["task"],
        wt_dir,
        bdd_ctx["repo_root"],
        check_git=False,
        changed_files=["src/spec_ops/prd/foreign_interface.py"],
    )


@then("the orchestrator peer review inspects the interface against active ADRs")
def orchestrator_inspects_interface(bdd_ctx: dict[str, Any]):
    review: PeerConsultationReview = bdd_ctx["review"]
    assert len(review.seam_violations) > 0
    assert any("Boundary seam crossing" in s for s in review.seam_violations)


@then("provides actionable feedback to the implementation agent before commit staging.")
def orchestrator_provides_feedback(bdd_ctx: dict[str, Any]):
    review: PeerConsultationReview = bdd_ctx["review"]
    assert review.approved is False
    assert len(review.feedback) > 0
    assert any("contract between 'worker' and 'prd'" in fb for fb in review.feedback)


@given("an in-worktree file length invariant failure exceeding 500 lines")
def setup_file_length_failure(bdd_ctx: dict[str, Any], tmp_path: Path):
    wt_dir = tmp_path / "wt_large"
    wt_dir.mkdir()
    large_file = wt_dir / "src" / "spec_ops" / "worker" / "overflow.py"
    large_file.parent.mkdir(parents=True, exist_ok=True)
    lines = ["class MegaOrchestrator:"] + [f"    def step_{i}(self):\n        return {i}" for i in range(520)]
    large_file.write_text("\n".join(lines), encoding="utf-8")
    bdd_ctx["large_wt"] = wt_dir
    bdd_ctx["large_file"] = large_file


@when("preflight verification and AST self-healing analyzer executes")
def execute_ast_self_healing(bdd_ctx: dict[str, Any]):
    wt_dir: Path = bdd_ctx["large_wt"]
    preflight_log = "File Length Violation: src/spec_ops/worker/overflow.py has 521 lines > limit 500"
    bdd_ctx["ast_feedback"] = format_preflight_ast_feedback(preflight_log, attempt=1, worktree_dir=wt_dir)


@then("actionable AST decomposition hints are generated for iterative self-healing up to max attempts.")
def verify_ast_hints(bdd_ctx: dict[str, Any]):
    feedback: str = bdd_ctx["ast_feedback"]
    assert "AST Decomposition Hints (Attempt 1)" in feedback
    assert "src/spec_ops/worker/overflow.py" in feedback
    assert "Largest AST node: class MegaOrchestrator" in feedback
    assert "Suggested seam: extract MegaOrchestrator" in feedback


@given("a task ready for execution")
def setup_ready_task(bdd_ctx: dict[str, Any]):
    bdd_ctx["ready_task_id"] = "TASK-0114"


@when('running the CLI command "spec-ops worker orchestrate" with "--dry-run --json"')
def run_cli_orchestrate(bdd_ctx: dict[str, Any], capsys: pytest.CaptureFixture):
    parser = build_parser()
    args = parser.parse_args(["worker", "orchestrate", bdd_ctx["ready_task_id"], "--dry-run", "--json"])
    exit_code = handle_worker_orchestrate(args, bdd_ctx["config"])
    bdd_ctx["cli_exit_code"] = exit_code
    captured = capsys.readouterr()
    bdd_ctx["cli_json"] = json.loads(captured.out)


@then("the command exits cleanly with valid structured JSON")
def verify_cli_clean_exit(bdd_ctx: dict[str, Any]):
    assert bdd_ctx["cli_exit_code"] == 0
    assert bdd_ctx["cli_json"]["success"] is True
    assert bdd_ctx["cli_json"]["task_id"] == "TASK-0114"


@then("the output confirms active spec consultation and formatted git trailers.")
def verify_cli_specs_and_trailers(bdd_ctx: dict[str, Any]):
    data = bdd_ctx["cli_json"]
    assert data["specs_consulted"] is not None
    assert len(data["specs_consulted"]["adrs"]) > 0
    assert data["trailers"]["SpecOps-Task"] == "TASK-0114"
    assert data["trailers"]["SpecOps-Story"] == "US-0117"
    assert data["trailers"]["SpecOps-PRD"] == "PRD-0006"
    assert "ADR-0005" in data["trailers"]["SpecOps-ADR"]
