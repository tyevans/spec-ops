"""Blackbox frontdoor verification for TASK-0240: Decouple Security from PRD.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess

from spec_ops.config.loader import load_config
from spec_ops.prd.manifest import compute_git_tree_digest as prd_compute_git_tree_digest
from spec_ops.security.digest import compute_git_tree_digest
from spec_ops.security.release_verifier import verify_release_manifest_data
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_release_verifier_has_no_prd_imports():
    """Verify that src/spec_ops/security/release_verifier.py contains zero imports of spec_ops.prd."""
    rv_file = Path("src/spec_ops/security/release_verifier.py")
    assert rv_file.is_file(), "release_verifier.py must exist"

    code = rv_file.read_text(encoding="utf-8")
    tree = ast.parse(code)
    prd_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "prd" in alias.name:
                    prd_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "prd" in mod:
                prd_imports.append(mod)

    assert not prd_imports, f"Found illegal prd imports in security/release_verifier.py: {prd_imports}"


def test_security_to_prd_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from security -> prd."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    sec_prd_violations = [
        v for v in violations
        if v.get("source") == "security" and v.get("target") == "prd"
    ]
    assert not sec_prd_violations, f"Active security -> prd violations detected: {sec_prd_violations}"


def test_compute_git_tree_digest_pure_foundation(tmp_path: Path):
    """Verify compute_git_tree_digest in security.digest calculates SHA-256 tree digest cleanly."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)

    test_file = tmp_path / "hello.txt"
    test_file.write_text("world\n", encoding="utf-8")
    subprocess.run(["git", "add", "hello.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    digest, clean, errs = compute_git_tree_digest(tmp_path)
    assert clean is True
    assert not errs
    assert len(digest) == 64


def test_prd_manifest_reexports_security_digest():
    """Verify prd.manifest consumes security downward and re-exports compute_git_tree_digest."""
    assert prd_compute_git_tree_digest is compute_git_tree_digest
