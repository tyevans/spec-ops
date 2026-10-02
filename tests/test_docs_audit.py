"""Tests for Diataxis documentation drift auditor and validator."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from spec_ops.cli.parser import build_parser
from spec_ops.docs.auditor import DocsAuditor, check_diataxis_structure
from spec_ops.docs.cli_inspector import check_cli_drift, extract_doc_commands, extract_parser_commands
from spec_ops.docs.models import APPROVED_QUADRANTS, AuditReport, AuditViolation
from spec_ops.docs.snippet_tester import check_code_snippets
from spec_ops.scaffold.init import init_project


def _create_minimal_docs_tree(base_dir: Path) -> Path:
    """Helper to create a valid minimal 4-quadrant docs tree with cli reference."""
    docs = base_dir / "docs"
    for quad in ["tutorials", "how-to", "reference", "explanation", "project"]:
        (docs / quad).mkdir(parents=True, exist_ok=True)
        (docs / quad / "sample.md").write_text("# Sample\n\nContent here.\n", encoding="utf-8")

    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    (docs / "operating-manual.md").write_text("# Manual\n", encoding="utf-8")

    cli_content = """# CLI Reference

| Command | Arguments | Description |
|---|---|---|
| `spec-ops init` | `[--dir PATH] [--name NAME]` | Initialize |
| `spec-ops health` | None | Check health |
"""
    (docs / "reference" / "cli.md").write_text(cli_content, encoding="utf-8")
    return docs


def test_structure_valid_docs(tmp_path: Path):
    docs = _create_minimal_docs_tree(tmp_path)
    violations, checked = check_diataxis_structure(docs)
    assert len(violations) == 0
    assert set(checked) == APPROVED_QUADRANTS


def test_structure_missing_and_empty_quadrant(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "tutorials").mkdir()  # empty quadrant
    # missing how-to, reference, explanation, project

    violations, _ = check_diataxis_structure(docs)
    msgs = [v.message for v in violations]
    assert any("empty: docs/tutorials" in m for m in msgs)
    assert any("Missing Diataxis quadrant directory: docs/how-to" in m for m in msgs)


def test_structure_unapproved_quadrant_and_root_files(tmp_path: Path):
    docs = _create_minimal_docs_tree(tmp_path)

    # Add unapproved quadrant directory
    (docs / "misc").mkdir()
    (docs / "misc" / "notes.md").write_text("# Random notes\n", encoding="utf-8")

    # Add unapproved root file
    (docs / "unapproved.txt").write_text("Hello\n", encoding="utf-8")

    violations, _ = check_diataxis_structure(docs)
    msgs = [v.message for v in violations]
    assert any("unapproved quadrant 'misc'" in m for m in msgs)
    assert any("resides in docs root outside approved quadrants" in m for m in msgs)


def test_cli_drift_detection(tmp_path: Path):
    docs = _create_minimal_docs_tree(tmp_path)

    dummy_parser = argparse.ArgumentParser(prog="spec-ops")
    subs = dummy_parser.add_subparsers(dest="command")
    p_init = subs.add_parser("init")
    p_init.add_argument("--name")
    p_init.add_argument("--dir")
    p_init.add_argument("--extra-opt")  # not in docs/reference/cli.md

    subs.add_parser("health")  # matches docs
    subs.add_parser("stats")   # in parser, missing in docs

    violations, count = check_cli_drift(docs, dummy_parser)
    assert count == 3
    msgs = [v.message for v in violations]

    # Command missing in docs
    assert any("Command 'spec-ops stats' is implemented in CLI but missing" in m for m in msgs)
    # Option missing in docs
    assert any("Command 'spec-ops init' in docs/reference/cli.md missing option(s): --extra-opt" in m for m in msgs)


def test_cli_drift_extra_command_in_docs(tmp_path: Path):
    docs = _create_minimal_docs_tree(tmp_path)

    # Parser only has init, but docs has init + health
    dummy_parser = argparse.ArgumentParser(prog="spec-ops")
    subs = dummy_parser.add_subparsers(dest="command")
    p_init = subs.add_parser("init")
    p_init.add_argument("--name")
    p_init.add_argument("--dir")

    violations, _ = check_cli_drift(docs, dummy_parser)
    msgs = [v.message for v in violations]
    assert any("Command 'spec-ops health' is documented in docs/reference/cli.md but does not exist in CLI" in m for m in msgs)


def test_snippet_tester_valid_and_invalid(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()

    # Valid python and bash snippets
    valid_md = """# Guide

```python
x = 10
y = x + 20
```

```bash
echo "Hello world"
spec-ops health
```
"""
    (docs / "valid.md").write_text(valid_md, encoding="utf-8")

    dummy_parser = argparse.ArgumentParser(prog="spec-ops")
    subs = dummy_parser.add_subparsers(dest="command")
    subs.add_parser("health")

    violations, count = check_code_snippets(docs, dummy_parser)
    assert count == 2
    assert len(violations) == 0

    # Add invalid python syntax
    invalid_py = """# Bad Python
```python
def broken(
```
"""
    (docs / "bad_py.md").write_text(invalid_py, encoding="utf-8")

    # Add invalid CLI option in bash snippet
    invalid_bash = """# Bad Bash
```bash
spec-ops health --invalid-flag-xyz
```
"""
    (docs / "bad_bash.md").write_text(invalid_bash, encoding="utf-8")

    violations, _ = check_code_snippets(docs, dummy_parser)
    msgs = [v.message for v in violations]
    assert any("Python syntax error" in m for m in msgs)
    assert any("Unrecognized CLI flag(s)" in m and "--invalid-flag-xyz" in m for m in msgs)


def test_docs_auditor_clean_suite(tmp_path: Path):
    target = tmp_path / "app"
    init_project(target, name="AuditedApp", diataxis=True)

    # Audit initialized scaffolded project with built-in parser
    parser = build_parser()
    auditor = DocsAuditor(docs_dir=target / "docs", parser=parser)
    report = auditor.run_audit()

    # Scaffold includes tutorials, how-to, reference, explanation, project
    assert len(report.quadrants_checked) == 5
    assert report.cli_commands_checked > 0
    assert report.snippets_checked > 0


def test_cli_docs_audit_clean():
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "docs", "audit"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "=== SpecOps Documentation Drift Audit ===" in res.stdout
    assert "Status: ✅ CLEAN" in res.stdout


def test_cli_docs_audit_drift_fails(tmp_path: Path):
    target = tmp_path / "drift_app"
    init_project(target, name="DriftApp", diataxis=True)

    # Introduce drift: invalid quadrant
    (target / "docs" / "unknown_quadrant").mkdir()
    (target / "docs" / "unknown_quadrant" / "drift.md").write_text("# Drift\n", encoding="utf-8")

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "docs", "audit", "--dir", str(target / "docs")],
        cwd=str(target),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1
    assert "Status: ❌ DRIFT DETECTED" in res.stdout
    assert "unknown_quadrant" in res.stdout


def test_structure_ignored_and_allowed_directories_in_specops_toml(tmp_path: Path):
    docs = _create_minimal_docs_tree(tmp_path)
    (docs / "adr").mkdir()
    (docs / "adr" / "ADR-0001.md").write_text("# ADR 1\n", encoding="utf-8")
    (docs / "plans").mkdir()
    (docs / "plans" / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (docs / "custom_root.txt").write_text("Custom root\n", encoding="utf-8")

    # Before adding specops.toml, these are violations
    violations, _ = check_diataxis_structure(docs)
    assert len(violations) >= 3

    # Add specops.toml with ignored/allowed directories and root files
    (tmp_path / "specops.toml").write_text(
        """[documentation]
ignored_directories = ["adr"]
allowed_directories = ["plans"]
ignored_root_files = ["custom_root.txt"]
""",
        encoding="utf-8",
    )

    violations_after, _ = check_diataxis_structure(docs)
    assert len(violations_after) == 0


def test_snippet_tester_with_angle_bracket_and_brace_placeholders(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()

    md_content = """# Placeholders
```bash
spec-ops queue claim <task id>
spec-ops commit -m <message file>
spec-ops review {task_id}
```
"""
    (docs / "placeholders.md").write_text(md_content, encoding="utf-8")

    dummy_parser = argparse.ArgumentParser(prog="spec-ops")
    subs = dummy_parser.add_subparsers(dest="command")
    q = subs.add_parser("queue")
    q_sub = q.add_subparsers(dest="subcommand")
    q_claim = q_sub.add_parser("claim")
    q_claim.add_argument("task_id")

    c = subs.add_parser("commit")
    c.add_argument("-m", "--message-file")

    r = subs.add_parser("review")
    r.add_argument("task_id")

    violations, count = check_code_snippets(docs, dummy_parser)
    assert count == 1
    assert len(violations) == 0


def test_cli_docs_audit_respects_configured_docs_dir(tmp_path: Path):
    import os
    import shutil

    target = tmp_path / "custom_app"
    init_project(target, name="CustomApp", diataxis=True)

    # Rename docs to documentation
    shutil.move(str(target / "docs"), str(target / "documentation"))

    # Update specops.toml
    specops_toml = target / "specops.toml"
    current_content = specops_toml.read_text(encoding="utf-8")
    specops_toml.write_text(
        current_content + "\n[documentation]\ndocs_dir = \"documentation\"\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "docs", "audit"],
        cwd=str(target),
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 0
    assert "Documentation Directory: " in res.stdout
    assert "documentation" in res.stdout
    assert "Status: ✅ CLEAN" in res.stdout


