"""Unit tests for PRD checkable outcome parsing, falsifiability validation, and delta scope calculation."""

from pathlib import Path

import pytest

from spec_ops.prd.delta import (
    CheckableOutcome,
    FalsifiabilityError,
    calculate_prd_deltas,
    find_existing_stories,
    find_existing_tasks,
    parse_checkable_outcomes,
    validate_falsifiability,
)


def test_parse_checkable_outcomes_missing_section():
    content = "# Title\n## Section 1\nSome content"
    outcomes = parse_checkable_outcomes(content)
    assert outcomes == []


def test_parse_checkable_outcomes_empty_and_comments():
    content = """---
id: '0001'
---
# PRD
## Checkable Outcomes
<!-- Full comment line -->
1. <!-- inline comment --> CLI metrics emit valid JSON <!-- end comment -->

## Next Section
1. Should not be parsed
"""
    outcomes = parse_checkable_outcomes(content)
    assert len(outcomes) == 1
    assert outcomes[0].id == 1
    assert outcomes[0].clean_text == "CLI metrics emit valid JSON"
    assert outcomes[0].is_falsifiable is True
    assert outcomes[0].subjective_term == ""


def test_parse_checkable_outcomes_formats():
    content = """## Checkable Outcomes
1. First numbered outcome
2. Outcome 2: Second outcome with explicit prefix
- Outcome 3 - Hyphen bullet with prefix
* Asterisk bullet without prefix
Outcome 5: Unbulleted outcome line
"""
    outcomes = parse_checkable_outcomes(content)
    assert len(outcomes) == 5
    assert outcomes[0].id == 1
    assert outcomes[0].clean_text == "First numbered outcome"
    assert outcomes[1].id == 2
    assert outcomes[1].clean_text == "Second outcome with explicit prefix"
    assert outcomes[2].id == 3
    assert outcomes[2].clean_text == "Hyphen bullet with prefix"
    assert outcomes[3].id == 4
    assert outcomes[3].clean_text == "Asterisk bullet without prefix"
    assert outcomes[4].id == 5
    assert outcomes[4].clean_text == "Unbulleted outcome line"


def test_parse_checkable_outcomes_falsifiability():
    content = """## Checkable Outcomes
1. Clean and modern UI with responsive buttons
2. Latency is noticeably faster under load
3. Database query responds in under 50ms
"""
    outcomes = parse_checkable_outcomes(content)
    assert len(outcomes) == 3
    assert outcomes[0].is_falsifiable is False
    assert outcomes[0].subjective_term != ""
    assert outcomes[1].is_falsifiable is False
    assert outcomes[1].subjective_term != ""
    assert outcomes[2].is_falsifiable is True
    assert outcomes[2].subjective_term == ""

    errors = validate_falsifiability(outcomes)
    assert len(errors) == 2
    assert "Outcome 'Clean and modern UI with responsive buttons' is non-falsifiable; refine into an observable metric or contract" in errors
    assert "Outcome 'Latency is noticeably faster under load' is non-falsifiable; refine into an observable metric or contract" in errors


def test_falsifiability_error_class():
    err = FalsifiabilityError(["Error 1", "Error 2"])
    assert err.errors == ["Error 1", "Error 2"]
    assert str(err) == "Error 1; Error 2"


def test_find_existing_stories(tmp_path: Path):
    stories_dir = tmp_path / "stories"
    assert find_existing_stories(stories_dir, "PRD-0001") == []

    stories_dir.mkdir(parents=True)
    # Story 1 matching PRD-0001 with int outcome_id
    (stories_dir / "us-0001.md").write_text(
        "---\nid: '0001'\ntitle: Story One\ngoverning_prd: PRD-0001\noutcome_id: 1\n---\n",
        encoding="utf-8",
    )
    # Story 2 matching PRD-0001 with string outcome_id
    (stories_dir / "us-0002.md").write_text(
        "---\nid: '0002'\ntitle: Story Two\ngoverning_prd: PRD-0001\noutcome_id: '2'\n---\n",
        encoding="utf-8",
    )
    # Story 3 matching PRD-0001 with invalid outcome_id
    (stories_dir / "us-0003.md").write_text(
        "---\nid: '0003'\ntitle: Story Three\ngoverning_prd: PRD-0001\noutcome_id: 'invalid'\n---\n",
        encoding="utf-8",
    )
    # Story 4 for different PRD
    (stories_dir / "us-0004.md").write_text(
        "---\nid: '0004'\ntitle: Story Four\ngoverning_prd: PRD-0002\noutcome_id: 1\n---\n",
        encoding="utf-8",
    )
    # Story 5 with missing governing_prd
    (stories_dir / "us-0005.md").write_text(
        "---\nid: '0005'\ntitle: Story Five\n---\n",
        encoding="utf-8",
    )

    found = find_existing_stories(stories_dir, "PRD-0001")
    assert len(found) == 3
    assert found[0]["id"] == "US-0001"
    assert found[0]["outcome_id"] == 1
    assert found[1]["id"] == "US-0002"
    assert found[1]["outcome_id"] == 2
    assert found[2]["id"] == "US-0003"
    assert found[2]["outcome_id"] is None


def test_find_existing_tasks(tmp_path: Path):
    backlog_dir = tmp_path / "backlog"
    assert find_existing_tasks(backlog_dir, "PRD-0001") == []

    backlog_dir.mkdir(parents=True)
    # Ignored PRIORITY.md
    (backlog_dir / "PRIORITY.md").write_text("# Priority\n", encoding="utf-8")

    # Task 1: direct outcome_id, string governing_prds
    (backlog_dir / "0001-task1.md").write_text(
        "---\nid: '0001'\ntitle: Task 1\ngoverning_prds: PRD-0001\noutcome_id: 1\nstatus: Complete\n---\n",
        encoding="utf-8",
    )
    # Task 2: outcome_id via stories_map and governing_stories list
    (backlog_dir / "0002-task2.md").write_text(
        "---\nid: 'TASK-0002'\ntitle: Task 2\ngoverning_prds:\n  - PRD-0001\ngoverning_stories:\n  - US-0002\nstatus: Refined\n---\n",
        encoding="utf-8",
    )
    # Task 3: outcome_id via content regex fallback
    (backlog_dir / "0003-task3.md").write_text(
        "---\nid: '0003'\ntitle: Task 3\ngoverning_prds:\n  - PRD-0001\nstatus: Proposed\n---\n# Task 3\nImplements Outcome 3 for PRD.\n",
        encoding="utf-8",
    )
    # Task 4: different PRD
    (backlog_dir / "0004-task4.md").write_text(
        "---\nid: '0004'\ntitle: Task 4\ngoverning_prds: - PRD-0009\noutcome_id: 1\nstatus: Proposed\n---\n",
        encoding="utf-8",
    )
    # Task 5: after PRIORITY.md alphabetically to ensure continue vs break is tested
    (backlog_dir / "ZZ-0099.md").write_text(
        "---\nid: 'TASK-0099'\ntitle: Task 99\ngoverning_prds:\n  - PRD-1\noutcome_id: 5\nstatus: Proposed\n---\n",
        encoding="utf-8",
    )

    # Calling with default stories_map=None ensures stories_map={} initialization mutant is killed
    found_default = find_existing_tasks(backlog_dir, "0001")
    assert len(found_default) == 4
    assert any(t["id"] == "TASK-0099" for t in found_default)

    stories_map = {"2": 2}
    found = find_existing_tasks(backlog_dir, "PRD-0001", stories_map=stories_map)
    assert len(found) == 4
    assert found[0]["id"] == "TASK-0001"
    assert found[0]["outcome_id"] == 1
    assert found[0]["status"] == "Complete"

    assert found[1]["id"] == "TASK-0002"
    assert found[1]["outcome_id"] == 2
    assert found[1]["status"] == "Refined"

    assert found[2]["id"] == "TASK-0003"
    assert found[2]["outcome_id"] == 3
    assert found[2]["status"] == "Proposed"

    assert found[3]["id"] == "TASK-0099"
    assert found[3]["outcome_id"] == 5
    assert found[3]["status"] == "Proposed"


def test_calculate_prd_deltas():
    # Current outcomes: 1, 2, 4 (outcome 3 was removed, outcome 4 was added)
    outcomes = [
        CheckableOutcome(id=1, raw_text="1. Outcome 1", clean_text="Outcome 1"),
        CheckableOutcome(id=2, raw_text="2. Outcome 2", clean_text="Outcome 2"),
        CheckableOutcome(id=4, raw_text="4. Outcome 4", clean_text="Outcome 4"),
    ]

    existing_stories = [
        {"id": "US-0001", "outcome_id": 1, "title": "Outcome 1"},
        {"id": "US-0002", "outcome_id": 2, "title": "Outcome 2"},
        {"id": "US-0003", "outcome_id": 3, "title": "Outcome 3"},
    ]

    existing_tasks = [
        {"id": "TASK-0001", "outcome_id": 1, "status": "Complete"},
        {"id": "TASK-0002", "outcome_id": 2, "status": "Refined"},
        {"id": "TASK-0003", "outcome_id": 3, "status": "Proposed"},
    ]

    res = calculate_prd_deltas("PRD-0001", outcomes, existing_stories, existing_tasks)
    assert [o.id for o in res.existing_outcomes] == [1, 2]
    assert [o.id for o in res.added_outcomes] == [4]
    assert res.removed_outcome_ids == [3]
    assert len(res.warnings) == 1
    assert "Outcome 3 was removed from PRD-0001 but has pending task TASK-0003" in res.warnings[0]
    assert len(res.pending_tasks_for_removed) == 1
    assert res.pending_tasks_for_removed[0]["id"] == "TASK-0003"


def test_calculate_prd_deltas_completed_task_no_warning():
    outcomes = [
        CheckableOutcome(id=1, raw_text="1. Outcome 1", clean_text="Outcome 1"),
    ]
    existing_stories = [
        {"id": "US-0001", "outcome_id": 1, "title": "Outcome 1"},
        {"id": "US-0002", "outcome_id": 2, "title": "Outcome 2"},
    ]
    # TASK-0002 is Complete, so no pending warning
    existing_tasks = [
        {"id": "TASK-0001", "outcome_id": 1, "status": "Complete"},
        {"id": "TASK-0002", "outcome_id": 2, "status": "Complete"},
    ]
    res = calculate_prd_deltas("PRD-0001", outcomes, existing_stories, existing_tasks)
    assert res.removed_outcome_ids == [2]
    assert len(res.warnings) == 0
    assert len(res.pending_tasks_for_removed) == 0


def test_calculate_prd_deltas_text_matching_fallback():
    # Outcome ID 9 is outside range(1, len(stories) + 1), so text matching branch is strictly exercised
    outcomes = [
        CheckableOutcome(id=9, raw_text="9. Telemetry Streaming", clean_text="Telemetry Streaming"),
    ]
    # Story has title with different casing
    existing_stories = [
        {"id": "US-0001", "outcome_id": None, "title": "implement telemetry streaming pipeline"},
    ]
    existing_tasks = []
    res = calculate_prd_deltas("PRD-0001", outcomes, existing_stories, existing_tasks)
    assert len(res.existing_outcomes) == 1
    assert res.existing_outcomes[0].id == 9
    assert len(res.added_outcomes) == 0


def test_parse_checkable_outcomes_middle_comment():
    content = """## checkable outcomes
17. Numbered seventeen
<!-- only comment -->
outcome 42: Explicit forty-two
<!-- another comment -->
OUTCOME 99: Uppercase outcome
"""
    outcomes = parse_checkable_outcomes(content)
    assert len(outcomes) == 3
    assert outcomes[0].id == 17
    assert outcomes[0].raw_text == "17. Numbered seventeen"
    assert outcomes[1].id == 42
    assert outcomes[1].raw_text == "outcome 42: Explicit forty-two"
    assert outcomes[2].id == 99
    assert outcomes[2].raw_text == "OUTCOME 99: Uppercase outcome"


def test_parse_checkable_outcomes_uppercase_header():
    content = """## CHECKABLE OUTCOMES
1. Valid outcome
"""
    outcomes = parse_checkable_outcomes(content)
    assert len(outcomes) == 1
    assert outcomes[0].id == 1
    assert outcomes[0].raw_text == "1. Valid outcome"


def test_find_existing_stories_edge_cases(tmp_path: Path):
    stories_dir = tmp_path / "stories_edge"
    stories_dir.mkdir(parents=True)
    # File without governing_prd first alphabetically
    (stories_dir / "us-0000-none.md").write_text("---\nid: '0000'\ntitle: None\n---\n", encoding="utf-8")
    # File with governing_outcome
    (stories_dir / "us-0001.md").write_text(
        "---\nid: '0001'\ntitle: One\ngoverning_prd: PRD-1\ngoverning_outcome: 2\n---\n",
        encoding="utf-8",
    )
    # File with non-US filename
    (stories_dir / "story-other.md").write_text(
        "---\nid: 'OTHER'\ntitle: Other\ngoverning_prd: PRD-0001\noutcome_id: 3\n---\n",
        encoding="utf-8",
    )
    # File without id in frontmatter, extracting from filename us-0077
    (stories_dir / "us-0077-feature.md").write_text(
        "---\ntitle: Seventy Seven\ngoverning_prd: PRD-0001\noutcome_id: 5\n---\n",
        encoding="utf-8",
    )
    found = find_existing_stories(stories_dir, "PRD-0001")
    assert len(found) == 3
    assert found[0]["outcome_id"] == 3
    assert found[0]["id"] == "OTHER"
    assert found[1]["outcome_id"] == 2
    assert found[1]["id"] == "US-0001"
    assert found[2]["outcome_id"] == 5
    assert found[2]["id"] == "US-0077"


def test_find_existing_tasks_edge_cases(tmp_path: Path):
    backlog_dir = tmp_path / "backlog_edge"
    backlog_dir.mkdir(parents=True)
    # First file alphabetically has no governing_prds
    (backlog_dir / "0000-none.md").write_text("---\nid: '0000'\ntitle: None\n---\n", encoding="utf-8")
    # File with governing_outcome
    (backlog_dir / "0001-task.md").write_text(
        "---\nid: '0001'\ntitle: Task 1\ngoverning_prds: [PRD-1]\ngoverning_outcome: 4\n---\n",
        encoding="utf-8",
    )
    # File with invalid outcome_id string
    (backlog_dir / "0002-task.md").write_text(
        "---\nid: 'TASK-0002'\ntitle: Task 2\ngoverning_prds: [PRD-0001]\noutcome_id: 'bad'\n---\n",
        encoding="utf-8",
    )
    # File without id in frontmatter, extracting from stem
    (backlog_dir / "0042-derived.md").write_text(
        "---\ntitle: Task 42\ngoverning_prds: [PRD-0001]\noutcome_id: 6\n---\n",
        encoding="utf-8",
    )
    found = find_existing_tasks(backlog_dir, "PRD-0001")
    assert len(found) == 3
    assert found[0]["outcome_id"] == 4
    assert found[0]["id"] == "TASK-0001"
    assert found[1]["outcome_id"] is None
    assert found[1]["id"] == "TASK-0002"
    assert found[2]["outcome_id"] == 6
    assert found[2]["id"] == "TASK-0042"


def test_calculate_prd_deltas_story_only_and_task_only():
    outcomes = [
        CheckableOutcome(id=1, raw_text="1. Outcome 1", clean_text="Outcome 1"),
        CheckableOutcome(id=2, raw_text="2. Outcome 2", clean_text="Outcome 2"),
    ]
    # Story only covers outcome 1, story only has removed outcome 9
    res_story = calculate_prd_deltas(
        "PRD-0001",
        outcomes,
        existing_stories=[
            {"id": "US-0001", "outcome_id": 1},
            {"id": "US-0009", "outcome_id": 9},
        ],
        existing_tasks=[],
    )
    assert [o.id for o in res_story.existing_outcomes] == [1]
    assert [o.id for o in res_story.added_outcomes] == [2]
    assert res_story.removed_outcome_ids == [9]

    # Task only covers outcome 2, task only has removed outcome 8 (Proposed)
    res_task = calculate_prd_deltas(
        "PRD-0001",
        outcomes,
        existing_stories=[],
        existing_tasks=[
            {"id": "TASK-0002", "outcome_id": 2, "status": "Proposed"},
            {"id": "TASK-0008", "outcome_id": 8, "status": "Proposed"},
        ],
    )
    assert [o.id for o in res_task.existing_outcomes] == [2]
    assert [o.id for o in res_task.added_outcomes] == [1]
    assert res_task.removed_outcome_ids == [8]
    assert len(res_task.warnings) == 1


def test_calculate_prd_deltas_count_fallback():
    outcomes = [
        CheckableOutcome(id=1, raw_text="1. Outcome 1", clean_text="Outcome 1"),
        CheckableOutcome(id=2, raw_text="2. Outcome 2", clean_text="Outcome 2"),
        CheckableOutcome(id=3, raw_text="3. Outcome 3", clean_text="Outcome 3"),
    ]
    # 2 stories with no outcome_id and titles that do NOT match clean_text
    existing_stories = [
        {"id": "US-0001", "outcome_id": None, "title": "Unrelated Title Alpha"},
        {"id": "US-0002", "outcome_id": None, "title": "Unrelated Title Beta"},
    ]
    res = calculate_prd_deltas("PRD-0001", outcomes, existing_stories, [])
    assert [o.id for o in res.existing_outcomes] == [1, 2]
    assert [o.id for o in res.added_outcomes] == [3]

