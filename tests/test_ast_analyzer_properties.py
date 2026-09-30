"""Generative property tests for AST analyzer invariants (ADR-0009)."""

from __future__ import annotations

import ast
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.worker.ast_analyzer import (
    AstNodeSeam,
    extract_top_level_nodes,
    find_largest_node,
    generate_ast_decomposition_hint,
)

import keyword

identifier_strategy = st.from_regex(r"[a-z_][a-z0-9_]{0,15}", fullmatch=True).filter(
    lambda s: not keyword.iskeyword(s) and not keyword.issoftkeyword(s)
)
class_name_strategy = st.from_regex(r"[A-Z][a-zA-Z0-9]{0,15}", fullmatch=True).filter(
    lambda s: not keyword.iskeyword(s) and not keyword.issoftkeyword(s)
)


@st.composite
def python_syntax_tree_strategy(draw: st.DrawFn) -> tuple[str, list[tuple[str, str, int]]]:
    """Generates random Python code with known top-level classes and functions."""
    num_nodes = draw(st.integers(min_value=0, max_value=8))
    expected: list[tuple[str, str, int]] = []
    lines: list[str] = []

    for idx in range(num_nodes):
        kind = draw(st.sampled_from(["class", "function"]))
        body_lines = draw(st.integers(min_value=1, max_value=25))

        if kind == "class":
            name = draw(class_name_strategy) or f"Class{idx}"
            lines.append(f"class {name}:")
            for b in range(body_lines - 1):
                lines.append(f"    var_{b} = {b}")
            lines.append("    pass")
            expected.append(("class", name, body_lines + 1))
        else:
            name = draw(identifier_strategy) or f"func_{idx}"
            lines.append(f"def {name}():")
            for b in range(body_lines - 1):
                lines.append(f"    temp_{b} = {b}")
            lines.append("    return 1")
            expected.append(("function", name, body_lines + 1))

        lines.append("")

    source_code = "\n".join(lines)
    return source_code, expected


@settings(max_examples=100)
@given(syntax_data=python_syntax_tree_strategy())
def test_ast_analyzer_reliably_locates_nodes_and_line_ranges(
    syntax_data: tuple[str, list[tuple[str, str, int]]],
):
    """Invariant: Locates top-level classes/functions and computes accurate line ranges."""
    source_code, expected_nodes = syntax_data
    nodes = extract_top_level_nodes(source_code)

    assert len(nodes) == len(expected_nodes)

    for node, (exp_kind, exp_name, _) in zip(nodes, expected_nodes):
        assert node.kind == exp_kind
        assert node.name == exp_name
        assert node.lineno >= 1
        assert node.end_lineno >= node.lineno
        assert node.line_count == (node.end_lineno - node.lineno + 1)
        assert node.display_kind in ("class", "function")


@settings(max_examples=100)
@given(syntax_data=python_syntax_tree_strategy())
def test_ast_analyzer_identifies_largest_node(
    syntax_data: tuple[str, list[tuple[str, str, int]]],
):
    """Invariant: Identifies largest node by line count without exceptions."""
    source_code, _ = syntax_data
    nodes = extract_top_level_nodes(source_code)
    largest = find_largest_node(nodes)

    if not nodes:
        assert largest is None
    else:
        assert largest is not None
        assert largest in nodes
        for other in nodes:
            assert largest.line_count >= other.line_count


@settings(max_examples=100)
@given(arbitrary_code=st.text())
def test_ast_analyzer_handles_arbitrary_inputs_resiliently(arbitrary_code: str):
    """Invariant: Resilient against arbitrary malformed inputs without throwing exceptions."""
    nodes = extract_top_level_nodes(arbitrary_code)
    assert isinstance(nodes, list)
    for node in nodes:
        assert node.lineno <= node.end_lineno
        assert node.line_count >= 1

    largest = find_largest_node(nodes)
    if nodes:
        assert largest is not None
    else:
        assert largest is None

    hint = generate_ast_decomposition_hint("arbitrary.py", len(arbitrary_code.splitlines()), source_code=arbitrary_code)
    assert "## AST Decomposition Hints" in hint
    assert "arbitrary.py" in hint


@settings(max_examples=50)
@given(
    attempt=st.integers(min_value=1, max_value=10),
    total_lines=st.integers(min_value=500, max_value=5000),
    limit=st.integers(min_value=100, max_value=1000),
)
def test_generate_ast_hint_structure_invariants(attempt: int, total_lines: int, limit: int):
    """Invariant: Hint generation maintains deterministic structure across attempts and limits."""
    code = f"class GiantService:\n" + "\n".join(f"    x_{i} = {i}" for i in range(100))
    hint = generate_ast_decomposition_hint("src/service.py", total_lines, attempt=attempt, source_code=code, limit=limit)

    assert f"## AST Decomposition Hints (Attempt {attempt})" in hint
    assert f"src/service.py ({total_lines} lines, limit: {limit})" in hint
    assert "Largest AST node: class GiantService" in hint
    assert "Suggested seam: extract GiantService into separate module" in hint
