"""Executable BDD scenarios for documentation drift guard user story US-0041."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.cli.parser import build_parser
from spec_ops.config.loader import load_config
from spec_ops.docs.builder import build_docs_site
from spec_ops.docs.checker import check_docs_drift

scenarios("features/us_0041_living_diataxis_documentation_drift_guard.feature")


@pytest.fixture
def drift_context(tmp_path: Path) -> dict[str, Any]:
    # Set up isolated docs tree copied from real docs
    docs_dir = tmp_path / "docs"
    real_docs = Path.cwd() / "docs"

    shutil.copytree(real_docs / "how-to", docs_dir / "how-to")
    shutil.copytree(real_docs / "reference", docs_dir / "reference")

    # Base parser
    parser = build_parser()

    return {
        "tmp_path": tmp_path,
        "docs_dir": docs_dir,
        "parser": parser,
        "new_cmd": "spec-ops task archive",
        "exit_code": 0,
        "messages": [],
    }


@given(parsers.parse('a developer has added a new CLI subcommand "{new_cmd}" in "src/spec_ops/cli/main.py"'))
def given_new_subcommand_added(drift_context: dict[str, Any], new_cmd: str):
    drift_context["new_cmd"] = new_cmd
    # Add subcommand to parser
    parser = build_parser()
    task_subparsers = None
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction) and "task" in action.choices:
            task_parser = action.choices["task"]
            for subact in task_parser._actions:
                if isinstance(subact, argparse._SubParsersAction):
                    task_subparsers = subact
                    break
    assert task_subparsers is not None
    p_arch = task_subparsers.add_parser("archive", help="Archive completed tasks")
    p_arch.add_argument("--older-than", default="30d")
    drift_context["parser"] = parser


@given(parsers.parse('no matching reference spec exists in "docs/reference/" or how-to guide in "docs/how-to/"'))
def given_no_matching_docs(drift_context: dict[str, Any]):
    new_cmd = drift_context["new_cmd"]
    docs_dir = drift_context["docs_dir"]
    for q in ("how-to", "reference"):
        for f in (docs_dir / q).glob("*.md"):
            assert new_cmd not in f.read_text(encoding="utf-8")


@when(parsers.parse('the engineer runs "spec-ops docs check"'))
def when_runs_docs_check(drift_context: dict[str, Any]):
    docs_dir = drift_context["docs_dir"]
    parser = drift_context["parser"]
    code, msgs = check_docs_drift(docs_dir, parser=parser)
    drift_context["exit_code"] = code
    drift_context["messages"] = msgs


@then("the command fails with a documentation drift alert:")
def then_fails_with_drift_alert(drift_context: dict[str, Any], docstring: str):
    expected_alert = docstring.strip()
    messages = drift_context["messages"]
    assert any(expected_alert in m for m in messages), f"Expected '{expected_alert}' in {messages}"


@then("the exit code is non-zero.")
def then_exit_code_non_zero(drift_context: dict[str, Any]):
    assert drift_context["exit_code"] != 0


@given(parsers.parse('the developer has added "{doc_path}" documenting the new command'))
def given_developer_added_doc(drift_context: dict[str, Any], doc_path: str):
    tmp_path = drift_context["tmp_path"]
    full_path = tmp_path / doc_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    new_cmd = drift_context["new_cmd"]
    full_path.write_text(
        f"# How-To: Archive Completed Tasks\n\nRun `{new_cmd} --older-than 30d` to archive.\n",
        encoding="utf-8",
    )


@then(parsers.parse('the command passes with "{expected_msg}"'))
def then_command_passes_with_msg(drift_context: dict[str, Any], expected_msg: str):
    assert drift_context["exit_code"] == 0
    assert any(expected_msg in m for m in drift_context["messages"])


@then(parsers.parse('"{cmd}" completes with {warnings:d} warnings.'))
def then_docs_build_completes(drift_context: dict[str, Any], cmd: str, warnings: int):
    config = load_config(root_dir=Path.cwd())
    out_dir = drift_context["tmp_path"] / "site"
    site_dir = build_docs_site(config, out_dir=out_dir)
    assert site_dir.exists()
