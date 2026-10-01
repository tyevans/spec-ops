"""Executable BDD acceptance tests for US-0085: AST Self-Healing Diagnostic Injector."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.worker.diagnostic_injector import DiagnosticCard, DiagnosticInjector

scenarios("features/us_0085_diagnostic_injector.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "worktree_repo"
    repo.mkdir(parents=True, exist_ok=True)
    return {
        "repo": repo,
        "failure_log": "",
        "cards": [],
        "retry_prompt": "",
        "target_file": None,
        "file_hash_before": None,
    }


@given("a preflight failure output reporting an AssertionError at line 42 of a source file")
def given_assertion_failure_at_line_42(bdd_context: dict[str, Any]):
    repo = bdd_context["repo"]
    src_dir = repo / "src" / "spec_ops"
    src_dir.mkdir(parents=True, exist_ok=True)
    source_file = src_dir / "calc_service.py"

    # Write a file where line 42 is an assertion inside a function
    lines = [f"# Line {i}: preamble comment for padding" for i in range(1, 40)]
    lines.append("def calculate_metrics(items: list[int]) -> int:")
    lines.append("    # Line 41: validation setup")
    lines.append("    assert len(items) > 0  # Line 42: target assertion")
    lines.append("    return sum(items)")
    source_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    failure_log = (
        "=================================== FAILURES ===================================\n"
        "___________________________ test_calculate_metrics ____________________________\n"
        "src/spec_ops/calc_service.py:42: in calculate_metrics\n"
        "    assert len(items) > 0\n"
        "E   AssertionError: assert 0 > 0\n"
        "=========================== short test summary info ============================\n"
        "FAILED tests/test_calc.py::test_calculate_metrics - AssertionError: assert 0 > 0\n"
    )

    bdd_context["target_file"] = source_file
    bdd_context["failure_log"] = failure_log


@when("the diagnostic injector processes the failure log")
def when_diagnostic_injector_processes_log(bdd_context: dict[str, Any]):
    repo = bdd_context["repo"]
    log = bdd_context["failure_log"]
    cards = DiagnosticInjector.diagnose_failure(log, repo_root=repo)
    bdd_context["cards"] = cards


@then("the failing function AST node is identified")
def then_failing_function_ast_node_identified(bdd_context: dict[str, Any]):
    cards: list[DiagnosticCard] = bdd_context["cards"]
    assert len(cards) >= 1, "Expected at least one diagnostic card"
    matching = [c for c in cards if c.node_type in ("FunctionDef", "AsyncFunctionDef") and c.node_name == "calculate_metrics"]
    assert len(matching) >= 1, f"Expected FunctionDef 'calculate_metrics', found: {[c.node_name for c in cards]}"
    card = matching[0]
    assert card.line_number == 42
    assert card.failure_category == "assertion_error"
    assert card.breached_rule == "ADR-0003"


@then("a structured diagnostic card includes the node signature and source context")
def then_card_includes_node_signature_and_source_context(bdd_context: dict[str, Any]):
    cards: list[DiagnosticCard] = bdd_context["cards"]
    card = [c for c in cards if c.node_name == "calculate_metrics"][0]
    assert card.source_snippet is not None
    # Verify node signature is included
    assert "def calculate_metrics" in card.source_snippet
    # Verify source context / assertion is included
    assert "assert len(items) > 0" in card.source_snippet


@given("a worktree preflight failure violating file length limit ADR-0002")
def given_file_length_limit_violation(bdd_context: dict[str, Any]):
    repo = bdd_context["repo"]
    src_dir = repo / "src" / "spec_ops"
    src_dir.mkdir(parents=True, exist_ok=True)
    oversized_file = src_dir / "oversized_engine.py"

    lines = ["class GiantWorkerEngine:"]
    for i in range(1, 520):
        lines.append(f"    field_{i} = {i}")
    lines.append("    pass")
    content = "\n".join(lines) + "\n"
    oversized_file.write_text(content, encoding="utf-8")

    bdd_context["target_file"] = oversized_file
    bdd_context["file_hash_before"] = hashlib.sha256(content.encode()).hexdigest()
    bdd_context["failure_log"] = (
        "=== SpecOps Health Check ===\n"
        "❌ 1 File Length Violation(s):\n"
        "File Length Violation: src/spec_ops/oversized_engine.py (521 lines > 500 line limit)\n"
    )


@when("the diagnostic injector synthesizes retry guidance")
def when_synthesizes_retry_guidance(bdd_context: dict[str, Any]):
    repo = bdd_context["repo"]
    log = bdd_context["failure_log"]
    cards = DiagnosticInjector.diagnose_failure(log, repo_root=repo)
    bdd_context["cards"] = cards
    bdd_context["retry_prompt"] = DiagnosticInjector.synthesize_retry_prompt(cards)


@then("the retry prompt highlights the exact oversized module")
def then_retry_prompt_highlights_oversized_module(bdd_context: dict[str, Any]):
    prompt = bdd_context["retry_prompt"]
    assert "src/spec_ops/oversized_engine.py" in prompt
    assert "GiantWorkerEngine" in prompt


@then("provides decomposition guidance without modifying source files directly")
def then_provides_decomposition_guidance_without_modification(bdd_context: dict[str, Any]):
    prompt = bdd_context["retry_prompt"]
    # Check decomposition guidance & ADR-0002
    assert "ADR-0002" in prompt
    lower_prompt = prompt.lower()
    assert "decompose" in lower_prompt or "extract" in lower_prompt or "seam" in lower_prompt

    # Invariant: source file is NOT modified directly
    target_file: Path = bdd_context["target_file"]
    assert target_file.exists()
    current_content = target_file.read_text(encoding="utf-8")
    current_hash = hashlib.sha256(current_content.encode()).hexdigest()
    assert current_hash == bdd_context["file_hash_before"]
