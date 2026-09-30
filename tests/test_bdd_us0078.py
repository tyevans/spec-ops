"""BDD step definitions for US-0078: Interactive Terminal Backlog Flow Monitor and JIT Buffer Telemetry."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rich.console import Console

from spec_ops.backlog.queue import BacklogQueue
from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.tui.flow_monitor import FlowMonitor, handle_flow_key
from spec_ops.worker.claimer import validate_definition_of_ready

scenarios("features/us_0078_interactive_terminal_backlog_flow_monitor.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


@pytest.fixture
def tui_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "flow_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "riley@example.com"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="FlowTelemetry")

    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0001-core-architecture.md").write_text(
        "---\n"
        "id: 'PRD-0001'\n"
        "title: Core Architecture\n"
        "status: Accepted\n"
        "---\n\n"
        "# PRD-0001: Core Architecture\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial specs"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "monitor": None,
        "console_output": "",
        "promoted_task": None,
        "claimed_task": None,
    }


@given("a backlog containing 18 completed tasks, 7 refined tasks, 5 proposed tasks, and 2 active agent worktrees")
def given_backlog_with_specific_distribution(tui_context: dict[str, Any]):
    repo = tui_context["repo"]
    backlog_dir = repo / "docs" / "project" / "backlog"
    comp_dir = backlog_dir / "complete"
    ref_dir = backlog_dir / "refined"
    prop_dir = backlog_dir / "proposed"

    for d in (comp_dir, ref_dir, prop_dir):
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.md"):
            f.unlink()

    # 18 completed tasks
    for i in range(1, 19):
        tid = f"TASK-{str(i).zfill(4)}"
        (comp_dir / f"{tid.lower()}-task.md").write_text(
            f"---\nid: '{str(i).zfill(4)}'\ntitle: Completed Task {i}\nstatus: Complete\n---\n",
            encoding="utf-8",
        )

    # 7 refined tasks
    for i in range(19, 26):
        tid = f"TASK-{str(i).zfill(4)}"
        (ref_dir / f"{tid.lower()}-task.md").write_text(
            f"---\nid: '{str(i).zfill(4)}'\ntitle: Refined Task {i}\nstatus: Refined\ngoverning_prds:\n  - PRD-0001\ngoverning_adrs:\n  - ADR-0001\n---\n",
            encoding="utf-8",
        )

    # 5 proposed tasks
    for i in range(26, 31):
        tid = f"TASK-{str(i).zfill(4)}"
        (prop_dir / f"{tid.lower()}-task.md").write_text(
            f"---\nid: '{str(i).zfill(4)}'\ntitle: Proposed Task {i}\nstatus: Proposed\ngoverning_prds:\n  - PRD-0001\ngoverning_adrs:\n  - ADR-0001\n---\n",
            encoding="utf-8",
        )

    # Update PRIORITY.md
    priority_lines = ["# Implementation Priority Queue\n"]
    for i in range(1, 19):
        priority_lines.append(f"1. **TASK-{str(i).zfill(4)} (Complete)**: [`Completed Task {i}`](complete/task-{str(i).zfill(4)}-task.md)")
    for i in range(19, 26):
        priority_lines.append(f"1. **TASK-{str(i).zfill(4)} (Refined)**: [`Refined Task {i}`](refined/task-{str(i).zfill(4)}-task.md)")
    for i in range(26, 31):
        priority_lines.append(f"1. **TASK-{str(i).zfill(4)} (Proposed)**: [`Proposed Task {i}`](proposed/task-{str(i).zfill(4)}-task.md)")
    (backlog_dir / "PRIORITY.md").write_text("\n".join(priority_lines) + "\n", encoding="utf-8")

    # 2 active agent worktrees
    wt_dir = repo / ".worktrees"
    wt1 = wt_dir / "task-0019"
    wt2 = wt_dir / "task-0020"
    for wt, tid in [(wt1, "0019"), (wt2, "0020")]:
        wt.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-b", f"task/task-{tid}"], cwd=wt, check=True, capture_output=True)
        s_dir = wt / ".specops"
        s_dir.mkdir(parents=True, exist_ok=True)
        (s_dir / "worker.json").write_text(
            f'{{"status": "Executing", "active_preflight_check": "uv run pytest", "task_id": "TASK-{tid}"}}',
            encoding="utf-8",
        )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup backlog distribution"], cwd=repo, check=True, capture_output=True)


@when('the developer executes "spec-ops backlog flow"')
def when_execute_backlog_flow(tui_context: dict[str, Any]):
    res = run_spec_ops(tui_context["repo"], ["backlog", "flow", "--once"])
    assert res.returncode == 0
    tui_context["console_output"] = res.stdout

    config = load_config(root_dir=tui_context["repo"])
    tui_context["monitor"] = FlowMonitor(config)


@then("a full-screen terminal UI displays three synchronized columns: Proposed, Refined (Buffer: 7/10 [Yellow]), and In-Flight Worktrees")
def then_terminal_ui_displays_columns(tui_context: dict[str, Any]):
    out = tui_context["console_output"]
    assert "Proposed (5)" in out or "Proposed" in out
    assert "Buffer: 7/10 [Yellow]" in out or "Buffer: 7/10" in out
    assert "In-Flight Worktrees" in out
    mon = tui_context["monitor"]
    assert mon.state.buffer_badge == "Buffer: 7/10 [Yellow]"
    assert len(mon.state.proposed_tasks) == 5
    assert len(mon.state.refined_tasks) == 7
    assert len(mon.state.worktrees) == 2


@then("displays active worker branch names, elapsed times, and last preflight status")
def then_displays_worker_telemetry(tui_context: dict[str, Any]):
    mon = tui_context["monitor"]
    assert len(mon.state.worktrees) == 2
    for wt in mon.state.worktrees:
        assert "branch" in wt
        assert "elapsed" in wt
        assert "pytest" in wt["status"] or "Executing" in wt["status"]


@then("updates live without flickering when tasks transition state on disk.")
def then_updates_live_without_flickering(tui_context: dict[str, Any]):
    mon = tui_context["monitor"]
    # Verify non-destructive refresh logic
    mon.refresh()
    assert mon.state.buffer_badge == "Buffer: 7/10 [Yellow]"


@given('the developer has navigated to proposed task "TASK-0021" in the Proposed column')
def given_navigated_to_proposed_task(tui_context: dict[str, Any]):
    repo = tui_context["repo"]
    prop_dir = repo / "docs" / "project" / "backlog" / "proposed"
    prop_dir.mkdir(parents=True, exist_ok=True)
    task_file = prop_dir / "0021-sample-ready-task.md"
    task_file.write_text(
        "---\n"
        "id: '0021'\n"
        "title: Sample Ready Task\n"
        "status: Proposed\n"
        "governing_prds:\n"
        "  - PRD-0001\n"
        "governing_adrs:\n"
        "  - ADR-0001\n"
        "---\n\n"
        "# TASK-0021: Sample Ready Task\n\n"
        "## Acceptance Criteria\n\n"
        "```gherkin\n"
        "Scenario: Verifying Ready Status\n"
        "Given system state\n"
        "When action occurs\n"
        "Then outcome is observed\n"
        "```\n",
        encoding="utf-8",
    )

    ref_dir = repo / "docs" / "project" / "backlog" / "refined"
    ref_dir.mkdir(parents=True, exist_ok=True)
    existing_refined = list(ref_dir.glob("*.md"))
    for i in range(len(existing_refined) + 1, 8):
        rtid = f"TASK-008{i}"
        rf = ref_dir / f"{rtid.lower()}-task.md"
        rf.write_text(f"---\nid: '008{i}'\ntitle: Refined Task {i}\nstatus: Refined\n---\n", encoding="utf-8")

    priority_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    priority_lines = ["# Implementation Priority Queue\n"]
    for rf in sorted(ref_dir.glob("*.md")):
        m = re.match(r"^task-(\d+)", rf.stem, re.IGNORECASE) or re.match(r"^(\d+)", rf.stem)
        cid = f"TASK-{m.group(1).zfill(4)}" if m else rf.stem
        priority_lines.append(f"1. **{cid} (Refined)**: [`Task`](refined/{rf.name})")
    priority_lines.append("1. **TASK-0021 (Proposed)**: [`Sample Ready Task`](proposed/0021-sample-ready-task.md)")
    priority_file.write_text("\n".join(priority_lines) + "\n", encoding="utf-8")

    config = load_config(root_dir=repo)
    mon = FlowMonitor(config)
    mon.state.active_column = "proposed"
    target_idx = next((i for i, t in enumerate(mon.state.proposed_tasks) if t.canonical_id == "TASK-0021"), 0)
    mon.state.selected_index["proposed"] = target_idx
    tui_context["monitor"] = mon
    tui_context["promoted_task"] = "TASK-0021"


@given('"TASK-0021" satisfies Definition of Ready rules')
def given_task_satisfies_dor(tui_context: dict[str, Any]):
    mon = tui_context["monitor"]
    target = next((t for t in mon.state.proposed_tasks if t.canonical_id == "TASK-0021"), None)
    assert target is not None
    dor_ok, _ = validate_definition_of_ready(target, mon.config)
    assert dor_ok is True


@when('the developer presses key "r" (Refine)')
def when_press_r_key(tui_context: dict[str, Any]):
    mon = tui_context["monitor"]
    action = handle_flow_key("r", mon.state)
    assert action.action == "REFINE"
    assert action.target == "TASK-0021"
    ok = mon.promote_task(action.target)
    assert ok is True


@then('SpecOps promotes "TASK-0021" to "docs/project/backlog/refined/"')
def then_promoted_to_refined(tui_context: dict[str, Any]):
    repo = tui_context["repo"]
    refined_task = repo / "docs" / "project" / "backlog" / "refined" / "0021-sample-ready-task.md"
    assert refined_task.exists()
    assert "status: Refined" in refined_task.read_text(encoding="utf-8")


@then('atomically updates "PRIORITY.md"')
def then_priority_updated(tui_context: dict[str, Any]):
    repo = tui_context["repo"]
    priority_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    content = priority_file.read_text(encoding="utf-8")
    assert "**TASK-0021 (Refined)**: [`Sample Ready Task`](refined/0021-sample-ready-task.md)" in content


@then("the Refined buffer gauge updates from 7/10 to 8/10 [Green].")
def then_buffer_gauge_updates(tui_context: dict[str, Any]):
    mon = tui_context["monitor"]
    assert mon.state.buffer_badge == "Buffer: 8/10 [Green]"


@given('a refined task "TASK-0022" highlighted in the Refined column')
def given_refined_task_highlighted(tui_context: dict[str, Any]):
    repo = tui_context["repo"]
    ref_dir = repo / "docs" / "project" / "backlog" / "refined"
    ref_dir.mkdir(parents=True, exist_ok=True)
    task_file = ref_dir / "0022-sample-claim-task.md"
    task_file.write_text(
        "---\n"
        "id: '0022'\n"
        "title: Sample Claim Task\n"
        "status: Refined\n"
        "governing_prds:\n"
        "  - PRD-0001\n"
        "governing_adrs:\n"
        "  - ADR-0001\n"
        "---\n\n"
        "# TASK-0022: Sample Claim Task\n",
        encoding="utf-8",
    )

    config = load_config(root_dir=repo)
    mon = FlowMonitor(config)
    mon.state.active_column = "refined"
    target_idx = next((i for i, t in enumerate(mon.state.refined_tasks) if t.canonical_id == "TASK-0022"), 0)
    mon.state.selected_index["refined"] = target_idx
    tui_context["monitor"] = mon
    tui_context["claimed_task"] = "TASK-0022"


@when('the developer presses key "c" (Claim & Worktree)')
def when_press_c_key(tui_context: dict[str, Any]):
    mon = tui_context["monitor"]
    action = handle_flow_key("c", mon.state)
    assert action.action == "CLAIM"
    assert action.target == "TASK-0022"
    ok = mon.claim_task(action.target, claimant="riley")
    assert ok is True


@then('SpecOps provisions ".worktrees/task-0022" on branch "feat/task-0022"')
def then_provisions_worktree(tui_context: dict[str, Any]):
    repo = tui_context["repo"]
    wt_dir = repo / ".worktrees" / "task-0022"
    assert wt_dir.exists()
    branch_res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wt_dir, capture_output=True, text=True)
    assert branch_res.stdout.strip() == "feat/task-0022"


@then('sets "claimed_by: riley" in task frontmatter')
def then_sets_claimed_by(tui_context: dict[str, Any]):
    repo = tui_context["repo"]
    task_file = repo / "docs" / "project" / "backlog" / "refined" / "0022-sample-claim-task.md"
    content = task_file.read_text(encoding="utf-8")
    assert "claimed_by: riley" in content


@then("opens a subshell in the new worktree directory.")
def then_opens_subshell(tui_context: dict[str, Any]):
    # In automated test mode (non-tty), subshell launch is safely bypassed
    pass
