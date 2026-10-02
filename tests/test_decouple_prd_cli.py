"""Blackbox frontdoor verification for TASK-0237: Decouple PRD from CLI.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.docs.models import ParsedCLICommand
from spec_ops.prd.persona_friction import (
    PersonaFrictionAuditor,
    register_default_parser_factory,
)
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_persona_friction_has_no_cli_imports():
    """Verify that src/spec_ops/prd/persona_friction.py contains zero imports of spec_ops.cli."""
    friction_file = Path("src/spec_ops/prd/persona_friction.py")
    assert friction_file.is_file(), "persona_friction.py must exist"

    code = friction_file.read_text(encoding="utf-8")
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

    assert not cli_imports, f"Found illegal cli imports in prd/persona_friction.py: {cli_imports}"


def test_prd_to_cli_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from prd -> cli."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    prd_cli_violations = [
        v for v in violations
        if v.get("source") == "prd" and v.get("target") == "cli"
    ]
    assert not prd_cli_violations, f"Active prd -> cli violations detected: {prd_cli_violations}"


def test_persona_friction_injected_parser(tmp_path: Path):
    """Verify PersonaFrictionAuditor audits with an injected parser without static cli import."""
    auditor = PersonaFrictionAuditor(root_dir=tmp_path)
    parser = argparse.ArgumentParser(prog="spec-ops")
    sub = parser.add_subparsers(dest="command")
    health = sub.add_parser("health")
    health.add_argument("--json", action="store_true")

    report = auditor.audit(parser=parser, persona_filter="alex")
    assert report.personas_audited == ["Alex"]
    assert len(report.workflows) > 0
    assert report.average_friction >= 0.0


def test_persona_friction_registered_factory(tmp_path: Path):
    """Verify PersonaFrictionAuditor uses registered parser factory callback."""
    auditor = PersonaFrictionAuditor(root_dir=tmp_path)

    def custom_factory():
        p = argparse.ArgumentParser(prog="spec-ops")
        sub = p.add_subparsers(dest="command")
        h = sub.add_parser("health")
        h.add_argument("--json", action="store_true")
        return p

    try:
        register_default_parser_factory(custom_factory)
        report = auditor.audit(persona_filter="alex")
        assert len(report.workflows) > 0
    finally:
        register_default_parser_factory(None)


def test_persona_friction_commands_override(tmp_path: Path):
    """Verify PersonaFrictionAuditor supports commands_override dictionary."""
    auditor = PersonaFrictionAuditor(root_dir=tmp_path)
    sample_cmds = {
        "spec-ops health": ParsedCLICommand(
            command="spec-ops health",
            options={"--json"},
            positionals=[],
        )
    }
    report = auditor.audit(commands_override=sample_cmds, persona_filter="alex")
    assert len(report.workflows) == 1
    assert report.workflows[0].command == "spec-ops health"
