"""Blackbox frontdoor verification for TASK-0234: Decouple Docs from CLI.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.docs.checker import check_docs_drift, register_default_parser_factory
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_docs_checker_has_no_cli_imports():
    """Verify that src/spec_ops/docs/checker.py contains zero imports of spec_ops.cli."""
    checker_file = Path("src/spec_ops/docs/checker.py")
    assert checker_file.is_file(), "checker.py must exist"

    code = checker_file.read_text(encoding="utf-8")
    tree = ast.parse(code)
    cli_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "cli" in alias.name:
                    cli_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "cli" in mod and not mod.endswith("cli_inspector"):
                cli_imports.append(mod)

    assert not cli_imports, f"Found illegal cli imports in docs/checker.py: {cli_imports}"


def test_docs_to_cli_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from docs -> cli."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    docs_cli_violations = [
        v for v in violations
        if v.get("source") == "docs" and v.get("target") == "cli"
    ]
    assert not docs_cli_violations, f"Active docs -> cli violations detected: {docs_cli_violations}"


def test_check_docs_drift_dependency_injection(tmp_path: Path):
    """Verify check_docs_drift accepts an explicitly injected parser without requiring cli imports."""
    docs_dir = tmp_path / "docs"
    how_to = docs_dir / "how-to"
    how_to.mkdir(parents=True)
    (how_to / "test.md").write_text("spec-ops test-cmd\nspec-ops other-cmd", encoding="utf-8")

    parser = argparse.ArgumentParser(prog="spec-ops")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("test-cmd")
    sub.add_parser("other-cmd")

    exit_code, messages = check_docs_drift(docs_dir, parser=parser)
    assert exit_code == 0
    assert "All public interfaces and CLI commands are documented." in messages[0]


def test_check_docs_drift_registered_factory(tmp_path: Path):
    """Verify check_docs_drift utilizes registered parser factory via dependency inversion."""
    docs_dir = tmp_path / "docs"
    how_to = docs_dir / "how-to"
    how_to.mkdir(parents=True)
    (how_to / "test.md").write_text("spec-ops factory-cmd", encoding="utf-8")

    def custom_factory():
        p = argparse.ArgumentParser(prog="spec-ops")
        s = p.add_subparsers(dest="command")
        s.add_parser("factory-cmd")
        return p

    try:
        register_default_parser_factory(custom_factory)
        exit_code, messages = check_docs_drift(docs_dir)
        assert exit_code == 0
    finally:
        register_default_parser_factory(None)
