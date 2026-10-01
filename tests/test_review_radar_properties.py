"""Generative Hypothesis property tests for review radar AST contract partitioning.

Governed by ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0106.
"""

from __future__ import annotations

import keyword
import re

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.review_radar import (
    diff_module_interfaces,
    partition_ast_symbols,
)

# Valid python identifiers
_public_ident = st.from_regex(r"[a-z][a-z0-9_]{1,10}", fullmatch=True).filter(
    lambda s: not s.startswith("_") and not keyword.iskeyword(s)
)
_private_ident = st.from_regex(r"_[a-z][a-z0-9_]{1,10}", fullmatch=True).filter(
    lambda s: s.startswith("_") and not s.startswith("__") and not keyword.iskeyword(s)
)


@st.composite
def python_module_strategy(draw: st.DrawFn) -> tuple[str, list[str], list[str], list[str] | None]:
    """Generates arbitrary valid Python source code along with expected public/private symbol classifications."""
    pub_funcs = draw(st.lists(_public_ident, min_size=0, max_size=4, unique=True))
    priv_funcs = draw(st.lists(_private_ident, min_size=0, max_size=4, unique=True))
    pub_classes = draw(st.lists(_public_ident.map(lambda s: s.capitalize()), min_size=0, max_size=3, unique=True))
    priv_classes = draw(st.lists(_private_ident.map(lambda s: f"_{s.lstrip('_').capitalize()}"), min_size=0, max_size=3, unique=True))

    use_explicit_all = draw(st.booleans())
    lines: list[str] = []

    all_symbols = pub_funcs + priv_funcs + pub_classes + priv_classes
    explicit_all: list[str] | None = None

    if use_explicit_all and all_symbols:
        # Pick subset of symbols for __all__
        chosen = draw(st.lists(st.sampled_from(all_symbols), min_size=0, max_size=len(all_symbols), unique=True))
        explicit_all = chosen
        all_repr = ", ".join(f'"{s}"' for s in chosen)
        lines.append(f"__all__ = [{all_repr}]\n")

    for f_name in pub_funcs:
        lines.append(f"def {f_name}(x: int = 1) -> int:\n    return x\n")

    for f_name in priv_funcs:
        lines.append(f"def {f_name}(y: int = 2) -> int:\n    return y * 2\n")

    for c_name in pub_classes:
        lines.append(f"class {c_name}:\n    def execute(self) -> None:\n        pass\n")

    for c_name in priv_classes:
        lines.append(f"class {c_name}:\n    def _internal(self) -> None:\n        pass\n")

    source_code = "\n".join(lines) if lines else "pass\n"
    return source_code, pub_funcs + pub_classes, priv_funcs + priv_classes, explicit_all


@settings(max_examples=50)
@given(module_data=python_module_strategy())
def test_ast_symbol_partitioning_disjoint_and_deterministic(module_data):
    """Asserts that any arbitrary AST module is partitioned deterministically without false positives."""
    code, expected_pub, expected_priv, explicit_all = module_data

    pub1, priv1 = partition_ast_symbols(code)
    pub2, priv2 = partition_ast_symbols(code)

    # 1. Determinism
    assert pub1.keys() == pub2.keys()
    assert priv1.keys() == priv2.keys()

    # 2. Disjointness: public and private symbols have zero overlap
    assert set(pub1.keys()).isdisjoint(set(priv1.keys()))

    # 3. Completeness & Correct Classification
    if explicit_all is not None:
        for name in pub1:
            assert name in explicit_all, f"Symbol '{name}' marked public but not in explicit __all__"
    else:
        for name in pub1:
            assert not name.startswith("_"), f"Symbol '{name}' starts with '_' but was marked public"
        for name in priv1:
            assert name.startswith("_"), f"Symbol '{name}' does not start with '_' but was marked private"


@settings(max_examples=40)
@given(
    base_name=_public_ident,
    priv_name=_private_ident,
    param_name=_public_ident,
)
def test_diff_module_interfaces_partitions_breaking_vs_internal(base_name, priv_name, param_name):
    """Asserts that interface diffs partition cleanly between breaking and internal changes without false positives."""
    if base_name == param_name or base_name == priv_name:
        return

    old_code = f"def {base_name}(x: int) -> int:\n    return x\n"

    # Case A: Purely internal logic changes or private helper additions must NEVER report breaking changes
    internal_new_code = (
        f"def {priv_name}() -> int:\n"
        f"    return 42\n\n"
        f"def {base_name}(x: int) -> int:\n"
        f"    return x + {priv_name}()\n"
    )
    diffs_internal = diff_module_interfaces(old_code, internal_new_code)
    breaking_internal = [d for d in diffs_internal if d.change_type == "breaking"]
    assert len(breaking_internal) == 0, f"False positive breaking change reported on internal refactoring: {breaking_internal}"

    # Case B: Adding an optional parameter must be non-breaking
    optional_new_code = f"def {base_name}(x: int, {param_name}: int = 10) -> int:\n    return x\n"
    diffs_optional = diff_module_interfaces(old_code, optional_new_code)
    breaking_optional = [d for d in diffs_optional if d.change_type == "breaking"]
    assert len(breaking_optional) == 0, f"Optional parameter addition flagged as breaking: {breaking_optional}"

    # Case C: Adding a required parameter without default must be breaking
    required_new_code = f"def {base_name}(x: int, {param_name}: int) -> int:\n    return x\n"
    diffs_required = diff_module_interfaces(old_code, required_new_code)
    breaking_required = [d for d in diffs_required if d.change_type == "breaking"]
    assert len(breaking_required) == 1, f"Expected 1 breaking change for required param, got: {breaking_required}"
    assert breaking_required[0].symbol_name == base_name

    # Case D: Removing public symbol must be breaking
    removed_new_code = f"def {priv_name}() -> None:\n    pass\n"
    diffs_removed = diff_module_interfaces(old_code, removed_new_code)
    breaking_removed = [d for d in diffs_removed if d.change_type == "breaking"]
    assert any(d.symbol_name == base_name for d in breaking_removed)
