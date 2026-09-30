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


def test_accept_user_story_success(tmp_path: Path):
    """Verifies that accept_user_story writes valid markdown and links to governing PRD."""
    from spec_ops.visualizer.story_assistant import accept_user_story

    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd_file = prd_dir / "prd-0003-test.md"
    prd_file.write_text(
        "---\nid: PRD-0003\ntitle: Test PRD\n---\n# PRD-0003\n\n## Linked User Stories\n",
        encoding="utf-8",
    )

    story_data = {
        "title": "Low-Code Assistant",
        "story_id": "0045",
        "persona": "Taylor",
        "governing_prd": "PRD-0003",
        "scenario": (
            "Scenario: Autocomplete steps\n"
            "  Given a project initialized with SpecOps\n"
            "  When Taylor types Given\n"
            "  Then autocomplete is shown\n"
        ),
    }

    res = accept_user_story(tmp_path, story_data)
    assert res["success"] is True
    assert res["story_id"] == "US-0045"
    assert (tmp_path / res["file_path"]).exists()

    # Verify link in PRD
    updated_prd = prd_file.read_text(encoding="utf-8")
    assert "- `US-0045`" in updated_prd


def test_accept_user_story_backdoor_rejection(tmp_path: Path):
    """Verifies that scenarios with private backdoors are rejected citing ADR-0003."""
    from spec_ops.visualizer.story_assistant import accept_user_story

    story_data = {
        "title": "Backdoor Story",
        "scenario": (
            "Scenario: Backdoor access\n"
            "  Given the database table users has record 'admin'\n"
            "  When something happens\n"
            "  Then something succeeds\n"
        ),
    }

    res = accept_user_story(tmp_path, story_data)
    assert res["success"] is False
    assert "ADR-0003" in res["error"] or "Backdoor violation" in res["error"]
    assert "offending_line" in res


def test_accept_user_story_invest_rejection(tmp_path: Path):
    """Verifies that scenarios without proper Gherkin INVEST criteria are rejected citing ADR-0006."""
    from spec_ops.visualizer.story_assistant import accept_user_story

    story_data = {
        "title": "Unstructured Story",
        "scenario": "Just some plain text without Given When Then",
    }

    res = accept_user_story(tmp_path, story_data)
    assert res["success"] is False
    assert "ADR-0006" in res["error"] or "INVEST" in res["error"]


def test_accept_user_story_validation_errors(tmp_path: Path):
    """Verifies error handling for missing title or scenario."""
    from spec_ops.visualizer.story_assistant import accept_user_story

    res1 = accept_user_story(tmp_path, {"title": "", "scenario": "Scenario:\n  Given x\n  When y\n  Then z"})
    assert res1["success"] is False
    assert "title" in res1["message"].lower()

    res2 = accept_user_story(tmp_path, {"title": "Title", "scenario": ""})
    assert res2["success"] is False
    assert "scenario" in res2["message"].lower()


def test_visualizer_extensions_reexport():
    """Verifies visualizer extensions decomposed into prd_studio.py and story_assistant.py."""
    from spec_ops.visualizer.prd_studio import create_prd_draft, validate_prd_schema
    from spec_ops.visualizer.story_assistant import accept_user_story, detect_backdoors

    assert callable(create_prd_draft)
    assert callable(validate_prd_schema)
    assert callable(accept_user_story)
    assert callable(detect_backdoors)

