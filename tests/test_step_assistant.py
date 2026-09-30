"""Unit tests for step assistant and backdoor detection."""

from __future__ import annotations

from pathlib import Path

from spec_ops.prd.step_assistant import (
    DEFAULT_FRONTDOOR_STEPS,
    detect_backdoors,
    extract_frontdoor_steps,
)


def test_detect_backdoors_positive_cases():
    """Verifies that private backdoor patterns are flagged with ADR-0003 warnings."""
    test_cases = [
        "Given the database table users has record 'admin'",
        "When the database table accounts has record 'active'",
        "Given a mocked service responding with 500",
        "And direct state manipulation of the queue",
        "When executing raw sql insert into metrics",
        "Then select * from logs yields empty result",
        "Given the internal state of worker is idle",
        "And the private internals of parser are inspected",
        "When accessing private attributes _config",
        "Then backdoor access is attempted",
    ]

    for step in test_cases:
        is_bd, warn, alt = detect_backdoors(step)
        assert is_bd is True, f"Failed to flag: {step}"
        assert "Backdoor violation (ADR-0003)" in warn
        assert len(alt) > 0


def test_detect_backdoors_negative_cases():
    """Verifies that public frontdoor steps are never flagged."""
    clean_cases = [
        "Given a project initialized with SpecOps",
        "Given the standalone visualizer is open in a browser",
        "When Taylor navigates to the \"PRDs & Features\" tab",
        "When Taylor clicks \"Save PRD Draft\"",
        "Then a new Markdown file is created at docs/project/product/idea/prd-0002.md",
        "And the generated document contains valid YAML frontmatter",
        "When running 'uv run spec-ops health'",
        "Then 0 file limit violations are reported",
    ]

    for step in clean_cases:
        is_bd, warn, alt = detect_backdoors(step)
        assert is_bd is False, f"Falsely flagged: {step}"
        assert warn == ""
        assert alt == ""


def test_extract_frontdoor_steps_default():
    """Verifies default established frontdoor fixtures are returned."""
    steps = extract_frontdoor_steps()
    assert len(steps) >= len(DEFAULT_FRONTDOOR_STEPS)
    patterns = {s["pattern"] for s in steps}
    assert "Given a project initialized with SpecOps" in patterns
    assert "Given the standalone visualizer is open in a browser" in patterns


def test_extract_frontdoor_steps_with_repo(tmp_path: Path):
    """Verifies discovery of steps from test_bdd_*.py files in repository."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    sample_bdd = tests_dir / "test_bdd_custom.py"
    sample_bdd.write_text(
        '@given("a custom fixture initialized")\n'
        'def custom_given(): pass\n\n'
        '@when("a custom action executes")\n'
        'def custom_when(): pass\n\n'
        '@then("a custom assertion succeeds")\n'
        'def custom_then(): pass\n',
        encoding="utf-8",
    )

    steps = extract_frontdoor_steps(tmp_path)
    patterns = {s["pattern"] for s in steps}
    assert "Given a custom fixture initialized" in patterns
    assert "When a custom action executes" in patterns
    assert "Then a custom assertion succeeds" in patterns


def test_extract_frontdoor_steps_filter():
    """Verifies filtering of steps by query string."""
    steps = extract_frontdoor_steps(query="SpecOps")
    assert len(steps) >= 1
    assert any("SpecOps" in s["pattern"] for s in steps)

    empty_steps = extract_frontdoor_steps(query="NonExistentPatternXYZ123")
    assert len(empty_steps) == 0
