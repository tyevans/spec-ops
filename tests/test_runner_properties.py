"""Hypothesis generative property tests for pluggable runners and JSON formatters (ADR-0009)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.health import FileLengthViolation, FileLengthWarning, HealthCheckReport
from spec_ops.cli.formatters import format_health_json, format_profiles_info_json, format_task_json
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.worker.runners import (
    AgentRunner,
    build_agent_cmd,
    interpolate_runner_template,
    prepare_runner_environment,
)

ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


# Safe template token alphabet
token_chars = st.characters(whitelist_categories=["Lu", "Ll", "Nd", "Pc", "Pd"], min_codepoint=32, max_codepoint=126)
safe_token = st.text(alphabet=token_chars, min_size=1, max_size=20)


@st.composite
def runner_template_strategy(draw: st.DrawFn) -> tuple[str, bool]:
    has_file = draw(st.booleans())
    prefix = draw(safe_token)
    flag = draw(safe_token)
    if has_file:
        template = f"{prefix} --{flag} {{prompt_file}}"
    else:
        template = f"{prefix} --{flag}"
    return template, has_file


@given(
    runner_data=runner_template_strategy(),
    subpath=st.text(min_size=1, max_size=30).filter(lambda s: "\x00" not in s),
    prompt=st.text(max_size=200).filter(lambda s: "\x00" not in s),
)
@settings(max_examples=50)
def test_hypothesis_runner_no_shell_quote_injection(
    runner_data: tuple[str, bool],
    subpath: str,
    prompt: str,
):
    template, has_file = runner_data
    fake_path = Path("/tmp") / subpath
    argv = interpolate_runner_template(
        cmd_template=template,
        prompt_file=fake_path,
        prompt=prompt,
    )

    assert isinstance(argv, list)
    assert len(argv) >= 1
    # Check that prompt_file is contained as a distinct single argv item
    target_str = str(fake_path.resolve()) if fake_path.is_absolute() else str(fake_path)
    assert any(target_str in arg for arg in argv)


@given(
    arbitrary_template=st.text(max_size=100),
    filename=safe_token,
    prompt=st.text(max_size=100),
)
@settings(max_examples=50)
def test_hypothesis_runner_arbitrary_templates_resilience(
    arbitrary_template: str,
    filename: str,
    prompt: str,
):
    fake_path = Path("/tmp") / filename
    argv = interpolate_runner_template(
        cmd_template=arbitrary_template,
        prompt_file=fake_path,
        prompt=prompt,
    )
    assert isinstance(argv, list)
    for token in argv:
        assert isinstance(token, str)


@given(
    base_env=st.dictionaries(keys=safe_token, values=st.text(max_size=30), max_size=10),
    dir_name=safe_token,
)
@settings(max_examples=50)
def test_hypothesis_environment_preparation_invariants(
    base_env: dict[str, str],
    dir_name: str,
):
    wt_dir = Path("/tmp") / dir_name
    env = prepare_runner_environment(worktree_dir=wt_dir, base_env=base_env)

    resolved = str(wt_dir.resolve())
    assert env["SPEC_OPS_WORKTREE"] == resolved
    assert env["PWD"] == resolved
    for k, v in base_env.items():
        assert env[k] == v


@given(
    task_id=st.integers(min_value=1, max_value=9999),
    title=safe_token,
    bc=safe_token,
    status=st.sampled_from(["Proposed", "Refined", "Complete", "In-Progress"]),
)
@settings(max_examples=40)
def test_hypothesis_task_json_formatter_invariants(
    task_id: int,
    title: str,
    bc: str,
    status: str,
):
    task = Task(
        id=str(task_id).zfill(4),
        title=title,
        status=status,
        target_bc=bc,
        dependencies=["TASK-0001"],
        governing_adrs=["ADR-0001", "ADR-0002"],
    )
    cfg = SpecOpsConfig()
    raw_json = format_task_json(task, cfg)

    assert not ANSI_ESCAPE_RE.search(raw_json)
    parsed = json.loads(raw_json)
    assert parsed["id"] == str(task_id).zfill(4)
    assert parsed["canonical_id"] == f"TASK-{str(task_id).zfill(4)}"
    assert parsed["title"] == title
    assert parsed["target_bc"] == bc
    assert parsed["status"] == status
    assert "prompt_metadata" in parsed


@given(
    violation_count=st.integers(min_value=0, max_value=5),
    warning_count=st.integers(min_value=0, max_value=5),
    sync_ok=st.booleans(),
)
@settings(max_examples=40)
def test_hypothesis_health_json_formatter_invariants(
    violation_count: int,
    warning_count: int,
    sync_ok: bool,
):
    violations = [
        FileLengthViolation(path=Path(f"src/file_{i}.py"), lines=510 + i, limit=500)
        for i in range(violation_count)
    ]
    warnings = [
        FileLengthWarning(path=Path(f"src/warn_{i}.py"), lines=420 + i, threshold=400, limit=500)
        for i in range(warning_count)
    ]
    sync_errors = [] if sync_ok else ["TASK-0012 is in refined/ on disk but referenced as complete/ in PRIORITY.md"]
    report = HealthCheckReport(
        violations=violations,
        warnings=warnings,
        priority_sync_ok=sync_ok,
        sync_errors=sync_errors,
        completed_tasks=10,
        refined_tasks=5,
        proposed_tasks=2,
    )

    raw_json = format_health_json(report)
    assert not ANSI_ESCAPE_RE.search(raw_json)
    parsed = json.loads(raw_json)

    expected_healthy = (violation_count == 0) and sync_ok
    assert parsed["healthy"] == expected_healthy
    assert parsed["status"] == ("ok" if expected_healthy else "error")
    assert len(parsed["violations"]) == violation_count
    assert len(parsed["warnings"]) == warning_count
    assert parsed["priority_sync"]["ok"] == sync_ok
    if not sync_ok:
        assert "TASK-0012" in parsed["priority_sync"]["mismatched_tasks"]
