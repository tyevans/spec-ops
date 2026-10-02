"""Blackbox frontdoor verification for TASK-0241: Decouple Security from Rescue.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess

from spec_ops.config.loader import load_config
from spec_ops.rescue.handover import assert_handover_excluded_from_git as rescue_assert_handover
from spec_ops.security.hygiene import assert_handover_excluded_from_git
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_dual_custody_has_no_rescue_imports():
    """Verify that src/spec_ops/security/dual_custody.py contains zero imports of spec_ops.rescue."""
    sec_file = Path("src/spec_ops/security/dual_custody.py")
    assert sec_file.is_file(), "dual_custody.py must exist"

    code = sec_file.read_text(encoding="utf-8")
    tree = ast.parse(code)
    rescue_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "rescue" in alias.name:
                    rescue_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "rescue" in mod:
                rescue_imports.append(mod)

    assert not rescue_imports, f"Found illegal rescue imports in security/dual_custody.py: {rescue_imports}"


def test_security_to_rescue_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from security -> rescue."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    sec_rescue_violations = [
        v for v in violations
        if v.get("source") == "security" and v.get("target") == "rescue"
    ]
    assert not sec_rescue_violations, f"Active security -> rescue violations detected: {sec_rescue_violations}"


def test_assert_handover_excluded_from_git_clean(tmp_path: Path):
    """Verify hygiene assert_handover_excluded_from_git returns True when HANDOVER.md is not committed."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)

    (tmp_path / "file.txt").write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "clean commit"], cwd=tmp_path, check=True)

    ok, msg = assert_handover_excluded_from_git(tmp_path)
    assert ok is True
    assert msg == ""


def test_assert_handover_excluded_from_git_detects_commit(tmp_path: Path):
    """Verify hygiene assert_handover_excluded_from_git detects committed HANDOVER.md."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)

    (tmp_path / "HANDOVER.md").write_text("ephemeral\n", encoding="utf-8")
    subprocess.run(["git", "add", "HANDOVER.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add handover"], cwd=tmp_path, check=True)

    ok, msg = assert_handover_excluded_from_git(tmp_path)
    assert ok is False
    assert "HANDOVER.md" in msg


def test_rescue_handover_reexports_security_hygiene():
    """Verify rescue.handover consumes security downward and re-exports assert_handover_excluded_from_git."""
    assert rescue_assert_handover is assert_handover_excluded_from_git
