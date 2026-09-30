"""Executable BDD acceptance tests for US-0075 and TASK-0066: Proactive Backlog Health Diagnostics and Repair."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0075_backlog_doctor.feature")

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
def doctor_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "doctor_workspace"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Jordan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "jordan@example.com"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="DoctorWorkspace")
    backlog_dir = repo / "docs" / "project" / "backlog"
    for folder in ("complete", "refined", "proposed"):
        f_dir = backlog_dir / folder
        if f_dir.exists():
            for p in f_dir.glob("*.md"):
                p.unlink()
        else:
            f_dir.mkdir(parents=True, exist_ok=True)

    # Empty base PRIORITY.md
    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text(
        "# Backlog Priority Index\n\nStrict sequential order of execution for engineering tasks.\n\n",
        encoding="utf-8",
    )

    return {"repo": repo, "backlog_dir": backlog_dir, "res": None}


# --- Scenario 1: Broken and Dangling Dependency Pointers ---


@given(parsers.parse('task "{task_id}" in "{folder}" lists "{dep_str}"'))
def task_lists_dangling_dependency(doctor_ctx: dict[str, Any], task_id: str, folder: str, dep_str: str):
    repo = doctor_ctx["repo"]
    clean_id = task_id.upper().replace("TASK-", "")
    target_folder = repo / folder
    target_folder.mkdir(parents=True, exist_ok=True)
    task_file = target_folder / f"{clean_id}-task.md"

    # dep_str is e.g. "dependencies: [TASK-9999]"
    task_content = (
        "---\n"
        f"id: '{clean_id}'\n"
        f"title: Test Task {clean_id}\n"
        "status: Proposed\n"
        f"{dep_str}\n"
        "---\n\n"
        f"# TASK-{clean_id}: Test Task\n"
    )
    task_file.write_text(task_content, encoding="utf-8")
    priority_file = doctor_ctx["backlog_dir"] / "PRIORITY.md"
    folder_name = target_folder.name
    priority_file.write_text(
        priority_file.read_text(encoding="utf-8")
        + f"- **{task_id} (Proposed)**: [`{task_file.stem}`]({folder_name}/{task_file.name})\n",
        encoding="utf-8",
    )


@given(parsers.parse('"{dep_id}" does not exist in complete, refined, or proposed backlog folders'))
def dependency_does_not_exist(doctor_ctx: dict[str, Any], dep_id: str):
    clean = dep_id.upper().replace("TASK-", "")
    for f in (doctor_ctx["backlog_dir"] / "complete", doctor_ctx["backlog_dir"] / "refined", doctor_ctx["backlog_dir"] / "proposed"):
        matches = list(f.glob(f"*{clean}*.md"))
        assert len(matches) == 0, f"Found unexpected matches for {dep_id}"


@when('the lead executes "spec-ops backlog doctor"')
def lead_executes_backlog_doctor(doctor_ctx: dict[str, Any]):
    res = run_spec_ops(doctor_ctx["repo"], ["backlog", "doctor"])
    doctor_ctx["res"] = res


@then("the command exits with code 1")
def verify_exit_code_1(doctor_ctx: dict[str, Any]):
    res = doctor_ctx["res"]
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"


@then(parsers.parse('reports "{expected_msg}"'))
def verify_reports_message(doctor_ctx: dict[str, Any], expected_msg: str):
    res = doctor_ctx["res"]
    combined = res.stdout + res.stderr
    assert expected_msg in combined, f"Expected '{expected_msg}' in output:\n{combined}"


@then("suggests removing the dangling reference or authoring the missing task specification.")
def verify_suggests_remedy(doctor_ctx: dict[str, Any]):
    res = doctor_ctx["res"]
    combined = res.stdout + res.stderr
    assert "Suggest removing the dangling reference or authoring the missing task specification" in combined


# --- Scenario 2: Ghost Entries and Unindexed Files in PRIORITY.md ---


@given(parsers.parse('file "{filename}" exists in "{folder}" but is missing from "PRIORITY.md"'))
def file_exists_unindexed(doctor_ctx: dict[str, Any], filename: str, folder: str):
    target = doctor_ctx["repo"] / folder / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    m = re.match(r"^(\d+)", Path(filename).stem)
    cid = m.group(1) if m else "0099"
    content = (
        "---\n"
        f"id: '{cid}'\n"
        "title: Orphan Task\n"
        "status: Proposed\n"
        "---\n\n"
        "# Orphan Task\n"
    )
    target.write_text(content, encoding="utf-8")


@given(parsers.parse('"PRIORITY.md" lists a reference to "{ghost_id}" whose file has been deleted from disk'))
def priority_lists_ghost(doctor_ctx: dict[str, Any], ghost_id: str):
    priority_file = doctor_ctx["backlog_dir"] / "PRIORITY.md"
    clean_id = ghost_id.upper().replace("TASK-", "")
    entry = f"- **{ghost_id} (Proposed)**: [`{clean_id}-deleted`](proposed/{clean_id}-deleted.md)\n"
    priority_file.write_text(priority_file.read_text(encoding="utf-8") + entry, encoding="utf-8")


@when('the lead runs "spec-ops backlog doctor"')
def lead_runs_backlog_doctor(doctor_ctx: dict[str, Any]):
    res = run_spec_ops(doctor_ctx["repo"], ["backlog", "doctor"])
    doctor_ctx["res"] = res


@then("the diagnostic report highlights 1 unindexed task file and 1 ghost index reference")
def verify_highlights_unindexed_and_ghost(doctor_ctx: dict[str, Any]):
    res = doctor_ctx["res"]
    combined = res.stdout + res.stderr
    assert "1 unindexed task file" in combined
    assert "1 ghost index reference" in combined


@then("warns of backlog synchronization drift.")
def verify_warns_sync_drift(doctor_ctx: dict[str, Any]):
    res = doctor_ctx["res"]
    combined = res.stdout + res.stderr
    assert "backlog synchronization drift" in combined.lower()


# --- Scenario 3: Automated Self-Healing Repair ---


@given("backlog synchronization drift with 1 unindexed file and 1 ghost entry")
def setup_sync_drift(doctor_ctx: dict[str, Any]):
    # 1 unindexed file in proposed
    unindexed = doctor_ctx["backlog_dir"] / "proposed" / "0099-orphan-task.md"
    unindexed.write_text("---\nid: '0099'\ntitle: Orphan Task\nstatus: Proposed\n---\n\n# Orphan Task\n", encoding="utf-8")

    # 1 ghost entry in PRIORITY.md
    p_file = doctor_ctx["backlog_dir"] / "PRIORITY.md"
    entry = "- **TASK-0088 (Proposed)**: [`0088-deleted`](proposed/0088-deleted.md)\n"
    p_file.write_text(p_file.read_text(encoding="utf-8") + entry, encoding="utf-8")


@when('the lead runs "spec-ops backlog doctor --repair"')
def lead_runs_backlog_doctor_repair(doctor_ctx: dict[str, Any]):
    res = run_spec_ops(doctor_ctx["repo"], ["backlog", "doctor", "--repair"])
    doctor_ctx["res"] = res


@then(parsers.parse('"PRIORITY.md" is cleaned of the ghost reference to "{ghost_id}"'))
def verify_ghost_cleaned(doctor_ctx: dict[str, Any], ghost_id: str):
    p_content = (doctor_ctx["backlog_dir"] / "PRIORITY.md").read_text(encoding="utf-8")
    assert ghost_id not in p_content, f"Ghost entry {ghost_id} still present in PRIORITY.md:\n{p_content}"


@then(parsers.parse('"{filename}" is deterministically appended to "PRIORITY.md" under proposed status'))
def verify_file_appended(doctor_ctx: dict[str, Any], filename: str):
    p_content = (doctor_ctx["backlog_dir"] / "PRIORITY.md").read_text(encoding="utf-8")
    stem = Path(filename).stem
    assert stem in p_content, f"Expected {stem} in PRIORITY.md:\n{p_content}"
    assert "proposed/" in p_content


@then(parsers.re(r'the command exits with code 0 and reports "(?P<report_msg>[^"]+)"\.?'))
def verify_remediated_clean(doctor_ctx: dict[str, Any], report_msg: str):
    res = doctor_ctx["res"]
    assert res.returncode == 0, f"Expected 0, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"
    assert report_msg in res.stdout


# --- Scenario 4: Queue Doctor CLI Interface and Line Numbers ---


@given(parsers.parse('task "{task_id}" referencing dangling dependency "{dep_id}"'))
def setup_task_with_dangling_dep(doctor_ctx: dict[str, Any], task_id: str, dep_id: str):
    clean = task_id.upper().replace("TASK-", "")
    task_p = doctor_ctx["backlog_dir"] / "proposed" / f"{clean}-task.md"
    task_p.write_text(
        "---\n"
        f"id: '{clean}'\n"
        f"title: Task {clean}\n"
        "status: Proposed\n"
        f"dependencies:\n"
        f"  - {dep_id}\n"
        "---\n\n"
        f"# Task {clean}\n",
        encoding="utf-8",
    )
    p_file = doctor_ctx["backlog_dir"] / "PRIORITY.md"
    p_file.write_text(
        p_file.read_text(encoding="utf-8") + f"- **{task_id} (Proposed)**: [`{task_p.stem}`](proposed/{task_p.name})\n",
        encoding="utf-8",
    )


@when('the architect runs "spec-ops queue doctor"')
def architect_runs_queue_doctor(doctor_ctx: dict[str, Any]):
    res = run_spec_ops(doctor_ctx["repo"], ["queue", "doctor"])
    doctor_ctx["res"] = res


@then("dangling dependency IDs are reported with file line numbers and exit code 1.")
def verify_line_numbers_reported(doctor_ctx: dict[str, Any]):
    res = doctor_ctx["res"]
    assert res.returncode == 1
    combined = res.stdout + res.stderr
    assert "TASK-9999" in combined
    assert "line" in combined.lower()


# --- Scenario 5: Automated Repair via Queue Doctor ---


@given("detected ghost entries and unindexed task files")
def setup_ghost_and_unindexed_for_queue(doctor_ctx: dict[str, Any]):
    # Unindexed
    unindexed = doctor_ctx["backlog_dir"] / "proposed" / "0077-unindexed.md"
    unindexed.write_text(
        "---\nid: '0077'\ntitle: Unindexed\nstatus: Proposed\ndependencies:\n  - TASK-9999\n---\n\n# Unindexed\n",
        encoding="utf-8",
    )
    # Ghost
    p_file = doctor_ctx["backlog_dir"] / "PRIORITY.md"
    p_file.write_text(
        p_file.read_text(encoding="utf-8") + "- **TASK-0010 (Proposed)**: [`0010-ghost`](proposed/0010-ghost.md)\n",
        encoding="utf-8",
    )


@when('the architect runs "spec-ops queue doctor --fix"')
def architect_runs_queue_doctor_fix(doctor_ctx: dict[str, Any]):
    res = run_spec_ops(doctor_ctx["repo"], ["queue", "doctor", "--fix"])
    doctor_ctx["res"] = res


@then('"PRIORITY.md" is rebuilt atomically and dangling dependencies are cleaned up.')
def verify_rebuilt_and_cleaned(doctor_ctx: dict[str, Any]):
    res = doctor_ctx["res"]
    assert res.returncode == 0
    p_content = (doctor_ctx["backlog_dir"] / "PRIORITY.md").read_text(encoding="utf-8")
    assert "TASK-0010" not in p_content  # Ghost removed
    assert "0077-unindexed" in p_content  # Unindexed appended

    # Check task 0077 dependencies cleaned
    task_p = doctor_ctx["backlog_dir"] / "proposed" / "0077-unindexed.md"
    content = task_p.read_text(encoding="utf-8")
    assert "TASK-9999" not in content  # Dangling dep cleaned
