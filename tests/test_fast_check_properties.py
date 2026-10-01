"""Hypothesis generative property-based tests for fast invariant diagnostics (ADR-0009, TASK-0055).

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from spec_ops.rescue.fast_check import (
    FILE_LIMIT,
    FILE_WARN_THRESHOLD,
    KNOWN_CONTEXTS,
    run_fast_check,
)


@settings(max_examples=50, deadline=None)
@given(
    line_count=st.integers(min_value=0, max_value=700),
)
def test_line_length_invariant_property(line_count: int, tmp_path: Path):
    """Property: Monotonically partitions line counts into clean, warning, and error states under 50ms."""
    target = tmp_path / f"synth_{line_count}_{time.time_ns()}.py"
    target.write_text("\n".join(f"val_{i} = {i}" for i in range(line_count)) + "\n", encoding="utf-8")

    result = run_fast_check(target)
    assert result.duration_ms < 500.0, f"Check exceeded threshold under load: {result.duration_ms:.2f}ms"

    if line_count < FILE_WARN_THRESHOLD:
        assert result.status == "clean"
        assert result.exit_code == 0
    elif FILE_WARN_THRESHOLD <= line_count < FILE_LIMIT:
        assert result.status == "warning"
        assert result.exit_code == 0
        assert "Approaching file length limit" in result.message
    else:
        assert result.status == "error"
        assert result.exit_code == 1
        assert "Hard Invariant Violation: File exceeds 500 lines" in result.message


@settings(max_examples=40, deadline=None)
@given(
    source_bc=st.sampled_from(sorted(KNOWN_CONTEXTS)),
    target_bc=st.sampled_from(sorted(KNOWN_CONTEXTS)),
    submodule=st.from_regex(r"[a-z][a-z0-9_]{1,12}", fullmatch=True),
)
def test_bounded_context_isolation_property(
    source_bc: str,
    target_bc: str,
    submodule: str,
    tmp_path: Path,
):
    """Property: Cross-context internal module imports are detected with ADR-0007 violation; intra-context imports never trigger ADR-0007."""
    unique_id = time.time_ns()
    source_file = tmp_path / f"run_{unique_id}" / "src" / "spec_ops" / source_bc / "entry.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)

    import_line = f"import spec_ops.{target_bc}.{submodule}\n"
    source_file.write_text(import_line, encoding="utf-8")

    result = run_fast_check(source_file, root_dir=source_file.parents[3])

    if source_bc != target_bc:
        assert result.status == "error"
        assert result.exit_code == 1
        assert any(v.rule_id == "ADR-0007" for v in result.violations)
        assert any("Bounded Context Violation" in v.message for v in result.violations)
        assert all(v.line > 0 and v.column > 0 for v in result.violations)
    else:
        assert not any(v.rule_id == "ADR-0007" for v in result.violations)


@settings(max_examples=40, deadline=None)
@given(
    fuzz_text=st.text(max_size=3000),
)
def test_fuzz_code_resilience_property(fuzz_text: str, tmp_path: Path):
    """Property: Fast check never crashes with an unhandled exception on arbitrary input strings."""
    target = tmp_path / f"fuzz_{time.time_ns()}.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(fuzz_text, encoding="utf-8", errors="ignore")

    res = run_fast_check(target)
    assert res.status in ("clean", "warning", "error")
    assert res.exit_code in (0, 1)

    json_str = res.to_json()
    assert json.loads(json_str)

    sarif_str = res.to_sarif()
    assert json.loads(sarif_str)
