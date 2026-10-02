"""Comprehensive regression test suite enforcing zero boundary violations across all bounded contexts.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
Verifies that all architectural import waivers have been retired and zero prohibited
dependencies exist across the entire repository.
"""

from __future__ import annotations

from pathlib import Path
import tomllib

from spec_ops.config.loader import load_config
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_zero_prohibited_boundary_violations_in_radar():
    """Verify that harvest_architecture_radar reports exactly zero violations across all bounded contexts."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    assert len(violations) == 0, (
        f"Expected zero prohibited boundary violations, but found {len(violations)}:\n"
        + "\n".join(f"  - {v['source']} -> {v['target']}: {v['message']} ({v['file_path']})" for v in violations)
    )


def test_zero_importlinter_waivers_in_pyproject():
    """Verify that all ignore_imports waivers in pyproject.toml have been retired."""
    pyproject_path = Path("pyproject.toml")
    assert pyproject_path.is_file(), "pyproject.toml must exist"

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    contracts = data.get("tool", {}).get("importlinter", {}).get("contracts", [])
    assert len(contracts) > 0, "Expected at least one importlinter contract"

    for contract in contracts:
        ignore_imports = contract.get("ignore_imports", [])
        assert len(ignore_imports) == 0, (
            f"Contract '{contract.get('name')}' must have zero ignore_imports waivers, "
            f"but found {len(ignore_imports)}: {ignore_imports}"
        )


def test_acyclic_bounded_context_layers():
    """Verify that harvest_architecture_radar constructs valid layered partition without cycles."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    layers = radar.get("layers", [])

    assert len(layers) > 0, "Architectural layers must not be empty"
    all_contexts = [bc for layer in layers for bc in layer]
    assert len(all_contexts) == len(set(all_contexts)), "Contexts must not appear in multiple layers"
    assert "core" in all_contexts, "core bounded context must be present"
    assert "app" in all_contexts, "app bounded context must be present"
    assert "cli" in all_contexts, "cli bounded context must be present"
