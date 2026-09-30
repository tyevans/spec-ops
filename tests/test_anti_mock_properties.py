"""Generative property-based tests for anti-mock AST verification invariants using Hypothesis (ADR-0009)."""

from __future__ import annotations

import ast
from hypothesis import given, strategies as st

from spec_ops.core.anti_mock import (
    PROHIBITED_CALL_NAMES,
    PROHIBITED_MOCK_MODULES,
    _is_private_name,
    _resolve_call_path,
    scan_test_code,
)


# Strategy for generating valid public Python identifiers
valid_public_ident = st.from_regex(r"[a-z][a-z0-9_]{1,15}", fullmatch=True).filter(
    lambda s: not s.startswith("_")
    and s not in PROHIBITED_CALL_NAMES
    and s
    not in (
        "def", "class", "import", "from", "return", "pass", "if", "else", "elif",
        "for", "while", "with", "as", "try", "except", "finally", "raise", "assert",
        "yield", "lambda", "global", "nonlocal", "True", "False", "None", "and", "or",
        "not", "is", "in", "async", "await", "patch", "mock", "spy"
    )
)

# Strategy for generating private identifiers
private_ident = st.from_regex(r"_[a-z][a-z0-9_]{1,15}", fullmatch=True).filter(
    lambda s: s.startswith("_") and not (s.startswith("__") and s.endswith("__"))
)


@given(
    func_name=valid_public_ident,
    var_name=valid_public_ident,
    val_int=st.integers(min_value=0, max_value=1000),
)
def test_clean_blackbox_tests_produce_zero_violations_invariant(
    func_name: str, var_name: str, val_int: int
):
    """Invariant: Arbitrary valid public test fixtures and frontdoors yield 0 anti-mock violations."""
    code = (
        f"import math\n"
        f"import pathlib\n"
        f"from dataclasses import dataclass\n"
        f"\n"
        f"def test_{func_name}(tmp_path, monkeypatch):\n"
        f"    {var_name} = {val_int}\n"
        f"    monkeypatch.setenv('PUBLIC_CONFIG', str({var_name}))\n"
        f"    assert math.sqrt({var_name} * {var_name}) == {var_name}\n"
    )
    violations = scan_test_code(code)
    assert len(violations) == 0, f"Expected 0 violations for clean code, got: {violations}"


@given(
    mock_mod=st.sampled_from(list(PROHIBITED_MOCK_MODULES)),
    alias_name=valid_public_ident,
)
def test_mock_module_imports_always_flagged_invariant(mock_mod: str, alias_name: str):
    """Invariant: Any import of prohibited mock modules is flagged at the exact line."""
    code_import = f"import {mock_mod}\n"
    violations1 = scan_test_code(code_import)
    assert len(violations1) == 1
    assert violations1[0].rule == "prohibited_mock_import"
    assert violations1[0].line == 1

    code_as = f"import {mock_mod} as {alias_name}\n"
    violations2 = scan_test_code(code_as)
    assert len(violations2) == 1
    assert violations2[0].rule == "prohibited_mock_import"
    assert violations2[0].line == 1

    code_from = f"from {mock_mod} import something\n"
    violations3 = scan_test_code(code_from)
    assert len(violations3) == 1
    assert violations3[0].rule == "prohibited_mock_import"
    assert violations3[0].line == 1


@given(
    pkg_name=valid_public_ident,
    private_fn=private_ident,
)
def test_private_symbol_imports_always_flagged_invariant(pkg_name: str, private_fn: str):
    """Invariant: Importing private symbols prefixed with '_' is strictly flagged."""
    code = f"from {pkg_name} import {private_fn}\n"
    violations = scan_test_code(code)
    assert len(violations) == 1
    assert violations[0].rule == "private_symbol_import"
    assert violations[0].line == 1
    assert private_fn in violations[0].message


@given(
    obj_name=valid_public_ident,
    private_attr=private_ident,
    val=st.integers(min_value=0, max_value=100),
)
def test_private_monkeypatch_always_flagged_invariant(
    obj_name: str, private_attr: str, val: int
):
    """Invariant: Monkeypatching private attributes/methods is detected deterministically."""
    code_obj = (
        f"def test_tamper(monkeypatch):\n"
        f"    monkeypatch.setattr({obj_name}, '{private_attr}', {val})\n"
    )
    violations = scan_test_code(code_obj)
    assert len(violations) == 1
    assert violations[0].rule == "private_monkeypatch"
    assert violations[0].line == 2

    code_str = (
        f"def test_tamper_str(monkeypatch):\n"
        f"    monkeypatch.setattr('{obj_name}.{private_attr}', {val})\n"
    )
    violations_str = scan_test_code(code_str)
    assert len(violations_str) == 1
    assert violations_str[0].rule == "private_monkeypatch"
    assert violations_str[0].line == 2


@given(
    call_target=st.sampled_from([
        "patch",
        "patch.object",
        "MagicMock",
        "Mock",
        "AsyncMock",
        "mocker.patch",
        "mocker.patch.object",
        "mocker.spy",
        "spy",
    ]),
    target_ident=valid_public_ident,
)
def test_mock_backdoor_calls_always_flagged_invariant(call_target: str, target_ident: str):
    """Invariant: Direct invocations of mock and spy backdoors are flagged."""
    code = (
        f"def test_backdoor():\n"
        f"    m = {call_target}({target_ident})\n"
    )
    violations = scan_test_code(code)
    assert len(violations) >= 1
    assert violations[0].rule == "prohibited_mock_call"
    assert violations[0].line == 2


@given(
    name=st.text(min_size=1, max_size=30),
)
def test_is_private_name_classifier_property(name: str):
    """Property: _is_private_name correctly distinguishes private vs dunder vs public."""
    res = _is_private_name(name)
    if name.startswith("_") and not (name.startswith("__") and name.endswith("__")):
        assert res is True
    else:
        assert res is False
