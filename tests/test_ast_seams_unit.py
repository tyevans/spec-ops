"""Unit tests for ast_seams.py to maximize mutant kill rate under mutmut."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_ops.core.ast_seams import (
    AstSymbol,
    DecompositionBlueprint,
    SubmoduleBlueprint,
    _cluster_symbols,
    _extract_python_symbols,
    _extract_ts_symbols,
    _generate_barrel_code,
    _tokenize_name,
    derive_task_slug,
    emit_refactor_task,
    emit_split_task,
    generate_refactor_task_content,
    generate_split_task_content,
    suggest_decomposition,
)


def test_ast_symbol_properties():
    sym = AstSymbol(name="OrderAggregate", kind="class", lineno=10, end_lineno=25)
    assert sym.line_count == 16
    sym_single = AstSymbol(name="fn", kind="function", lineno=5, end_lineno=5)
    assert sym_single.line_count == 1


def test_submodule_blueprint_properties():
    s1 = AstSymbol(name="ClassA", kind="class", lineno=1, end_lineno=10)
    s2 = AstSymbol(name="func_b", kind="function", lineno=11, end_lineno=20)
    sub = SubmoduleBlueprint(name="sub_core.py", symbols=[s1, s2])
    assert sub.symbol_names == ["ClassA", "func_b"]
    assert sub.estimated_lines == 20


def test_tokenize_name():
    assert _tokenize_name("OrderAggregate") == ["order", "aggregate"]
    assert _tokenize_name("parse_markdown_yaml") == ["parse", "markdown", "yaml"]
    assert _tokenize_name("APIClient") == ["api", "client"]
    assert _tokenize_name("simple") == ["simple"]


def test_extract_python_symbols():
    code = """
import os

class ParserCore:
    def __init__(self): pass

def parse_data(raw: str):
    return raw

async def fetch_async():
    pass
"""
    syms = _extract_python_symbols(code)
    names = [s.name for s in syms]
    assert "ParserCore" in names
    assert "parse_data" in names
    assert "fetch_async" in names

    assert _extract_python_symbols("def invalid(:") == []


def test_extract_ts_symbols():
    code = """
export class UserService {}
export interface UserPayload {}
export type UserId = string;
export function getUser() {}
export const DEFAULT_USER = {};
const localConst = 123;
"""
    syms = _extract_ts_symbols(code)
    names = [s.name for s in syms]
    assert "UserService" in names
    assert "UserPayload" in names
    assert "UserId" in names
    assert "getUser" in names
    assert "DEFAULT_USER" in names
    assert "localConst" in names


def test_cluster_symbols_empty_and_single():
    empty_clusters = _cluster_symbols("empty", [], is_ts=False)
    assert len(empty_clusters) == 2
    assert empty_clusters[0].name == "empty_part1.py"
    assert empty_clusters[1].name == "empty_part2.py"

    single_sym = [AstSymbol("SingleClass", "class", 1, 10)]
    single_cluster = _cluster_symbols("single", single_sym, is_ts=False)
    assert len(single_cluster) == 1
    assert single_cluster[0].name == "single_core.py"


def test_generate_barrel_code_python_and_ts():
    s1 = AstSymbol("Alpha", "class", 1, 5)
    s2 = AstSymbol("Beta", "class", 6, 10)
    sub1 = SubmoduleBlueprint("mod_alpha.py", [s1])
    sub2 = SubmoduleBlueprint("mod_beta.py", [s2])

    py_barrel = _generate_barrel_code([sub1, sub2], is_ts=False)
    assert "from .mod_alpha import Alpha" in py_barrel
    assert "from .mod_beta import Beta" in py_barrel
    assert '__all__ = ["Alpha", "Beta"]' in py_barrel

    ts_sub1 = SubmoduleBlueprint("mod_alpha.ts", [s1])
    ts_sub2 = SubmoduleBlueprint("mod_beta.ts", [s2])
    ts_barrel = _generate_barrel_code([ts_sub1, ts_sub2], is_ts=True)
    assert 'export * from "./mod_alpha";' in ts_barrel
    assert 'export * from "./mod_beta";' in ts_barrel


def test_derive_task_slug():
    assert derive_task_slug("src/orders/service.py") == "orders-service"
    assert derive_task_slug("orders/service.py") == "orders-service"
    assert derive_task_slug("parser.py") == "parser"


def test_suggest_decomposition_blueprint_summary():
    code = """
class MarkdownParser: pass
def parse_markdown(): pass
class FrontmatterParser: pass
def parse_frontmatter(): pass
"""
    bp = suggest_decomposition("src/parser.py", source_text=code)
    summary = bp.summary()
    assert "Decomposition Blueprint for src/parser.py" in summary
    assert "Suggested barrel exports:" in summary


def test_generate_and_emit_tasks(tmp_path: Path):
    code = "class A: pass\nclass B: pass\n"
    bp = suggest_decomposition("src/orders/service.py", source_text=code)

    split_content = generate_split_task_content("src/orders/service.py", bp)
    assert "TASK-SPLIT-orders-service" in split_content
    assert "INVEST Criteria" in split_content
    assert "ADR-0002" in split_content

    refactor_content = generate_refactor_task_content("src/orders/service.py", bp)
    assert "TASK-REFACTOR-orders-service" in refactor_content
    assert "Target Submodule Decomposition Path" in refactor_content
    assert "ADR-0002" in refactor_content

    split_path = emit_split_task(tmp_path, "src/orders/service.py", bp)
    assert split_path.is_file()
    assert split_path.name == "TASK-SPLIT-orders-service.md"

    refactor_path = emit_refactor_task(tmp_path, "src/orders/service.py", bp)
    assert refactor_path.is_file()
    assert refactor_path.name == "TASK-REFACTOR-orders-service.md"
