"""Unit tests for layer contracts and import-linter contract loader."""

from __future__ import annotations

from pathlib import Path
import pytest

from spec_ops.core.layer_contracts import (
    ArchitecturalContract,
    load_architectural_contract,
    load_architectural_layers_and_rules,
)


def test_architectural_contract_helper_methods():
    contract = ArchitecturalContract(
        context_layers={"cli": 3, "worker": 2, "core": 1, "config": 0},
        independent_pairs={("visualizer", "tui"), ("tui", "visualizer")},
        forbidden_rules={"core": ["visualizer.*", "cli"]},
        ordered_layers=[["config"], ["core"], ["worker"], ["cli"]],
    )

    assert contract.get_layer("cli") == 3
    assert contract.get_layer("unknown") is None

    assert contract.is_independent("visualizer", "tui") is True
    assert contract.is_independent("cli", "core") is False

    assert contract.is_forbidden("core", "visualizer.template") is True
    assert contract.is_forbidden("core", "cli") is True
    assert contract.is_forbidden("core", "config") is False


def test_load_architectural_contract_from_pyproject(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.importlinter]
root_package = "test_pkg"

[[tool.importlinter.contracts]]
name = "Test Layers"
type = "layers"
layers = [
    "test_pkg.cli",
    "test_pkg.alpha | test_pkg.beta",
    "test_pkg.delta : test_pkg.gamma",
    "test_pkg.core",
]
ignore_imports = [
    "test_pkg.core -> test_pkg.cli"
]

[[tool.importlinter.contracts]]
name = "Independence Contract"
type = "independence"
modules = [
    "test_pkg.sec",
    "test_pkg.docs"
]

[[tool.importlinter.contracts]]
name = "Forbidden Contract"
type = "forbidden"
source_modules = ["test_pkg.core"]
forbidden_modules = ["test_pkg.cli"]
""",
        encoding="utf-8",
    )

    contract = load_architectural_contract(tmp_path)
    assert contract.context_layers["cli"] == 3
    assert contract.context_layers["alpha"] == 2
    assert contract.context_layers["beta"] == 2
    assert contract.context_layers["delta"] == 1
    assert contract.context_layers["gamma"] == 1
    assert contract.context_layers["core"] == 0

    # Alpha and beta are independent
    assert ("alpha", "beta") in contract.independent_pairs
    assert ("beta", "alpha") in contract.independent_pairs

    # Delta and gamma are non-independent (colon separator)
    assert ("delta", "gamma") not in contract.independent_pairs

    # Independence contract modules
    assert ("sec", "docs") in contract.independent_pairs
    assert ("docs", "sec") in contract.independent_pairs

    # Forbidden contract modules
    assert "cli" in contract.forbidden_rules["core"]

    # Tuple wrapper
    layers, indep, forb, ordered = load_architectural_layers_and_rules(tmp_path)
    assert layers["cli"] == 3
    assert ("alpha", "beta") in indep
    assert "cli" in forb["core"]
    assert len(ordered) == 4


def test_load_architectural_contract_from_specops_toml(tmp_path: Path):
    specops = tmp_path / "specops.toml"
    specops.write_text(
        """
[architecture.layers]
cli = 2
worker = 1
core = 0

[architecture.independent_contexts]
pairs = [
  ["worker", "rescue"]
]
""",
        encoding="utf-8",
    )

    contract = load_architectural_contract(tmp_path)
    assert contract.context_layers["cli"] == 2
    assert contract.context_layers["worker"] == 1
    assert contract.context_layers["core"] == 0
    assert ("worker", "rescue") in contract.independent_pairs
    assert ("rescue", "worker") in contract.independent_pairs


def test_load_architectural_contract_empty_fallback(tmp_path: Path):
    contract = load_architectural_contract(tmp_path)
    # Should fall back to review_radar.CONTEXT_LAYERS
    assert "core" in contract.context_layers
    assert "cli" in contract.context_layers
    assert len(contract.ordered_layers) > 0
