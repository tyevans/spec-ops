"""Unit tests for ast_analyzer.py to maximize mutant kill rate."""

from __future__ import annotations

from pathlib import Path

from spec_ops.worker.ast_analyzer import (
    AstNodeSeam,
    extract_top_level_nodes,
    find_largest_node,
    format_preflight_ast_feedback,
    generate_ast_decomposition_hint,
    scan_worktree_file_length_violations,
)


def test_ast_node_seam_properties():
    node = AstNodeSeam(name="Service", kind="class", lineno=10, end_lineno=30)
    assert node.line_count == 21
    assert node.display_kind == "class"

    func_node = AstNodeSeam(name="handle", kind="function", lineno=5, end_lineno=5)
    assert func_node.line_count == 1
    assert func_node.display_kind == "function"

    inverted_node = AstNodeSeam(name="weird", kind="other", lineno=15, end_lineno=10)
    assert inverted_node.line_count == 1
    assert inverted_node.display_kind == "function"


def test_extract_top_level_nodes():
    code = """
import os

class FirstClass:
    pass

def sync_func():
    return 1

async def async_func():
    return 2
"""
    nodes = extract_top_level_nodes(code)
    assert len(nodes) == 3
    assert nodes[0].name == "FirstClass"
    assert nodes[0].kind == "class"
    assert nodes[1].name == "sync_func"
    assert nodes[1].kind == "function"
    assert nodes[2].name == "async_func"
    assert nodes[2].kind == "function"

    # Syntax error resilience
    assert extract_top_level_nodes("def broken(:") == []
    # No nodes
    assert extract_top_level_nodes("a = 1\nb = 2\n") == []


def test_find_largest_node():
    assert find_largest_node([]) is None

    n1 = AstNodeSeam("small", "function", 1, 5)  # 5 lines
    n2 = AstNodeSeam("big", "class", 10, 30)     # 21 lines
    n3 = AstNodeSeam("medium", "function", 40, 50) # 11 lines

    assert find_largest_node([n1, n2, n3]) == n2
    assert find_largest_node([n1]) == n1


def test_generate_ast_decomposition_hint_class_and_function(tmp_path: Path):
    code_class = "class WorkerPool:\n" + "\n".join("    pass" for _ in range(550))
    hint1 = generate_ast_decomposition_hint("src/worker.py", 551, attempt=1, source_code=code_class, limit=500)
    assert "## AST Decomposition Hints (Attempt 1)" in hint1
    assert "- File: src/worker.py (551 lines, limit: 500)" in hint1
    assert "Largest AST node: class WorkerPool" in hint1
    assert "Suggested seam: extract WorkerPool into separate module" in hint1

    code_func = "def execute_fleet():\n" + "\n".join("    pass" for _ in range(520))
    hint2 = generate_ast_decomposition_hint("src/runner.py", 521, attempt=2, source_code=code_func, limit=500)
    assert "## AST Decomposition Hints (Attempt 2)" in hint2
    assert "Largest AST node: function execute_fleet" in hint2
    assert "Suggested seam: extract execute_fleet into separate module" in hint2

    # Fallback when no top-level node exists
    hint_empty = generate_ast_decomposition_hint("src/empty.py", 510, attempt=1, source_code="# just comments\n", limit=500)
    assert "Suggested seam: decompose module into separate files" in hint_empty

    # Reading from disk
    f = tmp_path / "mod.py"
    f.write_text("class DiskClass: pass\n", encoding="utf-8")
    hint_disk = generate_ast_decomposition_hint(f, 1, attempt=1)
    assert "Largest AST node: class DiskClass" in hint_disk

    # Nonexistent file handling
    hint_nonexist = generate_ast_decomposition_hint(tmp_path / "missing.py", 10)
    assert "Suggested seam: decompose module into separate files" in hint_nonexist


def test_scan_worktree_file_length_violations(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    ok_file = src / "ok.py"
    ok_file.write_text("def a(): pass\n", encoding="utf-8")

    violating_file = src / "bloated.py"
    violating_file.write_text("\n".join(f"# line {i}" for i in range(505)) + "\n", encoding="utf-8")

    violations = scan_worktree_file_length_violations(tmp_path, limit=500)
    assert len(violations) == 1
    rel, lines, content = violations[0]
    assert rel == "src/bloated.py"
    assert lines == 505
    assert len(content.splitlines()) == 505


def test_format_preflight_ast_feedback(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    big_file = src / "big.py"
    big_file.write_text("class HugeClass:\n" + "\n".join("    pass" for _ in range(510)) + "\n", encoding="utf-8")

    feedback = format_preflight_ast_feedback("preflight failed", 1, tmp_path, limit=500)
    assert "## Preflight Failure Feedback (Attempt 1)" in feedback
    assert "## AST Decomposition Hints (Attempt 1)" in feedback
    assert "Largest AST node: class HugeClass" in feedback

    # When scan finds nothing but log mentions file length violation
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    clean_src = clean_dir / "src"
    clean_src.mkdir()
    logged_file = clean_src / "logged.py"
    logged_file.write_text("class LoggedClass: pass\n", encoding="utf-8")

    fake_log = "File Length Violation: src/logged.py (520 lines > 500 line limit)"
    fb_log = format_preflight_ast_feedback(fake_log, 2, clean_dir, limit=500)
    assert "## AST Decomposition Hints (Attempt 2)" in fb_log
    assert "Largest AST node: class LoggedClass" in fb_log
