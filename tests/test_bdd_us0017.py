"""Executable BDD step definitions for US-0017: Specification Frontmatter Schema Validation and Migration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.migration import parse_frontmatter_and_body
from spec_ops.scaffold.init import init_project

scenarios("features/us_0017_schema_validation_and_migration.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="SpecOpsSchemaBDD")
    return {
        "root": tmp_path,
        "res": None,
        "sample_file": None,
        "original_content": None,
        "original_body": None,
    }


def _run_cli(root: Path, cmd_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *cmd_args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@given('specification documents in "docs/project/" containing valid YAML frontmatter matching current models')
def valid_spec_documents(bdd_context: dict[str, Any]):
    root: Path = bdd_context["root"]
    task_dir = root / "docs" / "project" / "backlog" / "refined"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_file = task_dir / "0001-initial-task.md"
    task_file.write_text(
        "---\n"
        "id: '0001'\n"
        "title: Initial Task\n"
        "status: Refined\n"
        "dependencies: []\n"
        "governing_adrs:\n"
        "- ADR-0001\n"
        "governing_prds:\n"
        "- PRD-0001\n"
        "governing_stories:\n"
        "- US-0001\n"
        "target_bc: core\n"
        "---\n\n"
        "# Initial Task\n"
        "Description of initial task.\n",
        encoding="utf-8",
    )


@given('an older task document using legacy field "governing_adr: 0001" instead of "governing_adrs: [\'ADR-0001\']"')
def older_task_with_legacy_adr(bdd_context: dict[str, Any]):
    root: Path = bdd_context["root"]
    task_dir = root / "docs" / "project" / "backlog" / "refined"
    task_dir.mkdir(parents=True, exist_ok=True)
    legacy_file = task_dir / "0010-legacy-adr-task.md"
    content = (
        "---\n"
        "id: '0010'\n"
        "title: Legacy Task\n"
        "status: Refined\n"
        "target_bc: core\n"
        "governing_adr: 0001\n"
        "---\n\n"
        "# Technical Specification\n"
        "Important specifications.\n"
    )
    legacy_file.write_text(content, encoding="utf-8")
    bdd_context["sample_file"] = legacy_file
    bdd_context["original_content"] = content


@given("an older task document with legacy frontmatter fields and a 100-line Markdown technical specification")
def older_task_with_100_line_spec(bdd_context: dict[str, Any]):
    root: Path = bdd_context["root"]
    task_dir = root / "docs" / "project" / "backlog" / "refined"
    task_dir.mkdir(parents=True, exist_ok=True)
    legacy_file = task_dir / "0020-hundred-line-task.md"

    body_lines = [
        "",
        "# Technical Architecture & Delivery Specification",
        "",
        "## Overview",
        "This specification contains exactly 100 lines of detailed technical requirements.",
        "",
        "| Component | Layer | Protocol | Invariant |",
        "|---|---|---|---|",
        "| Core Engine | Substrate | In-Memory | Zero-Loss |",
        "| Visualizer | Presentation | Canvas 2D | Sub-50ms |",
        "",
        "```python",
        "def execute_in_place_verification(payload: bytes) -> bool:",
        "    \"\"\"Guarantees byte-for-byte fidelity.\"\"\"",
        "    hash_val = sha256(payload).hexdigest()",
        "    return len(hash_val) == 64",
        "```",
        "",
        "<!-- Custom Architectural Marker: DO_NOT_REMOVE_THIS_ANCHOR -->",
        "",
    ]
    # Pad out to exactly 100 lines
    while len(body_lines) < 100:
        body_lines.append(f"- Invariant Clause #{len(body_lines)}: Verification rule active.")

    body_text = "\n".join(body_lines) + "\n"

    frontmatter = (
        "---\n"
        "id: '0020'\n"
        "title: Hundred Line Specification Task\n"
        "status: Refined\n"
        "target_bc: core\n"
        "governing_adr: 0001\n"
        "governing_prd: 0002\n"
        "story: 0003\n"
        "dependency: TASK-0004\n"
        "---\n"
    )
    full_content = frontmatter + body_text
    legacy_file.write_text(full_content, encoding="utf-8")
    bdd_context["sample_file"] = legacy_file
    bdd_context["original_content"] = full_content
    bdd_context["original_body"] = body_text


@when(parsers.parse('the architect runs "{command}"'))
def architect_runs_cli(bdd_context: dict[str, Any], command: str):
    root: Path = bdd_context["root"]
    args = command.split()[1:]
    res = _run_cli(root, args)
    bdd_context["res"] = res


@then(parsers.parse("the command exits with code {expected_code:d}"))
def command_exits_with_code(bdd_context: dict[str, Any], expected_code: int):
    res: subprocess.CompletedProcess[str] = bdd_context["res"]
    assert res.returncode == expected_code, f"Expected code {expected_code}, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"


@then(parsers.re(r'reports "(?P<expected_msg>[^"]+)"\.?'))
def command_reports_message(bdd_context: dict[str, Any], expected_msg: str):
    res: subprocess.CompletedProcess[str] = bdd_context["res"]
    combined = res.stdout + res.stderr
    assert expected_msg in combined, f"Expected {expected_msg!r} not in output:\n{combined}"


@then("the command outputs a unified diff showing projected frontmatter transformations")
def outputs_unified_diff(bdd_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = bdd_context["res"]
    output = res.stdout
    assert "-governing_adr: 0001" in output or "- governing_adr: 0001" in output
    assert "+governing_adrs:" in output
    assert "+- ADR-0001" in output or "+  - ADR-0001" in output


@then("leaves files on disk unmodified.")
def leaves_files_unmodified(bdd_context: dict[str, Any]):
    sample_file: Path = bdd_context["sample_file"]
    disk_content = sample_file.read_text(encoding="utf-8")
    assert disk_content == bdd_context["original_content"]


@then("the YAML frontmatter is rewritten to the new schema format")
def frontmatter_rewritten(bdd_context: dict[str, Any]):
    sample_file: Path = bdd_context["sample_file"]
    content = sample_file.read_text(encoding="utf-8")
    meta, _, _ = parse_frontmatter_and_body(content)
    assert "governing_adr" not in meta
    assert "governing_adrs" in meta
    assert "ADR-0001" in meta["governing_adrs"]
    assert "PRD-0002" in meta.get("governing_prds", [])
    assert "US-0003" in meta.get("governing_stories", [])
    assert "TASK-0004" in meta.get("dependencies", [])


@then("the exact Markdown body, headings, and code blocks below the frontmatter are preserved byte-for-byte.")
def markdown_body_preserved_byte_for_byte(bdd_context: dict[str, Any]):
    sample_file: Path = bdd_context["sample_file"]
    content = sample_file.read_text(encoding="utf-8")
    _, _, body = parse_frontmatter_and_body(content)
    expected_body = bdd_context["original_body"]
    assert body == expected_body, f"Body not preserved byte-for-byte.\nExpected:\n{expected_body!r}\nGot:\n{body!r}"
