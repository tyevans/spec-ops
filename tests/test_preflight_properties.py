"""Generative property tests for PreflightPipeline invariants using Hypothesis."""

from __future__ import annotations

import sys
from pathlib import Path
from hypothesis import given, settings, strategies as st

from spec_ops.worker.preflight import PreflightPipeline, PreflightStage, PipelineResult


@st.composite
def random_preflight_stages(draw):
    """Generates a randomized sequence of preflight stages with controllable pass/fail codes."""
    stage_count = draw(st.integers(min_value=1, max_value=8))
    stages = []
    for i in range(1, stage_count + 1):
        name = f"stage_{i}"
        # Random exit code: 0 (success) or 1..125 (failure)
        exit_code = draw(st.sampled_from([0, 0, 0, 1, 2, 42]))
        # Command that exits with the chosen exit code
        cmd = f"{sys.executable} -c 'import sys; sys.exit({exit_code})'"
        timeout = draw(st.floats(min_value=5.0, max_value=30.0))
        stages.append(PreflightStage(name=name, command=cmd, required=True, timeout_seconds=timeout))
    return stages


@settings(max_examples=50, deadline=None)
@given(stages=random_preflight_stages())
def test_hypothesis_pipeline_early_fast_fail_invariants(stages: list[PreflightStage]):
    """Hypothesis Invariant (ADR-0009):

    Any stage failure immediately aborts downstream stages, isolates the root failure cause,
    and guarantees zero subsequent side effects.
    """
    pipeline = PreflightPipeline(stages=stages)
    result = pipeline.run()

    # Determine expected first failure index
    first_failure_idx = None
    for idx, stage in enumerate(stages):
        if "sys.exit(0)" not in stage.command:
            first_failure_idx = idx
            break

    if first_failure_idx is None:
        # Property 1: All stages succeeded
        assert result.success is True
        assert result.failed_stage is None
        assert len(result.stage_results) == len(stages)
        assert result.aborted_stages == []
        assert "all configured preflight gates passed successfully" in result.summary.lower()
    else:
        # Property 2: Fast-fail aborted downstream stages
        assert result.success is False
        assert result.failed_stage is not None
        assert result.failed_stage.stage_name == stages[first_failure_idx].name
        assert result.failed_stage.exit_code != 0

        # Number of executed stages is exactly first_failure_idx + 1
        assert len(result.stage_results) == first_failure_idx + 1

        # Downstream stages are strictly aborted and never executed
        expected_aborted = [s.name for s in stages[first_failure_idx + 1:]]
        assert result.aborted_stages == expected_aborted

        # Executed stages never contain any aborted stages
        executed_names = [r.stage_name for r in result.stage_results]
        for aborted_name in expected_aborted:
            assert aborted_name not in executed_names

        # Property 3: Root failure cause is isolated in summary and logs
        assert stages[first_failure_idx].name in result.summary
        assert stages[first_failure_idx].name in result.logs
        assert str(result.failed_stage.exit_code) in result.logs
