"""Unit test suite for milestone rollover engine and CLI handler.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0077.
Deals strictly with public frontdoors and domain contracts without private mocks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from spec_ops.backlog.rollover import (
    MilestoneRolloverCoordinator,
    matches_milestone,
    normalize_ms_token,
    rollover_milestone,
    update_frontmatter_milestone,
)
from spec_ops.cli.milestone_handler import handle_milestone_command
from spec_ops.config.loader import load_config
from spec_ops.core.migration import parse_frontmatter_and_body
from spec_ops.scaffold.init import init_project


class TestMilestoneMatching:
    """Verifies milestone token normalization and query matching contracts."""

    def test_normalize_ms_token(self) -> None:
        assert normalize_ms_token("Milestone 1") == "milestone1"
        assert normalize_ms_token("M-1") == "m1"
        assert normalize_ms_token("  m_2  ") == "m2"

    def test_exact_and_case_insensitive_matching(self) -> None:
        assert matches_milestone("M1", "M1")
        assert matches_milestone("m1", "M1")
        assert matches_milestone("M1", "m1")
        assert matches_milestone("Sprint-4", "sprint-4")

    def test_milestone_word_and_prefix_variations(self) -> None:
        assert matches_milestone("Milestone 1", "M1")
        assert matches_milestone("M1", "Milestone 1")
        assert matches_milestone("Milestone-1", "m1")
        assert matches_milestone("1", "M1")
        assert matches_milestone("M1", "1")
        assert matches_milestone(1, "M1")

    def test_milestone_extended_names(self) -> None:
        assert matches_milestone("M1-MVP", "M1")
        assert matches_milestone("M1", "M1-MVP")

    def test_negative_matches(self) -> None:
        assert not matches_milestone("M1", "M2")
        assert not matches_milestone("M1", "M10")
        assert not matches_milestone("M10", "M1")
        assert not matches_milestone(None, "M1")
        assert not matches_milestone("", "M1")
        assert not matches_milestone("M1", "")


class TestFrontmatterMilestoneUpdate:
    """Verifies atomic frontmatter update logic preserving body and comments byte-for-byte."""

    def test_updates_target_release(self) -> None:
        content = (
            "---\n"
            "id: '0010'\n"
            "title: Sample Task\n"
            "status: Refined\n"
            "target_release: M1\n"
            "target_bc: backlog\n"
            "---\n\n"
            "# TASK-0010\n"
            "Body remains intact.\n"
        )
        modified, new_c, key, old_v = update_frontmatter_milestone(content, "M1", "M2")
        assert modified
        assert key == "target_release"
        assert old_v == "M1"
        assert "target_release: M2" in new_c
        assert "target_bc: backlog" in new_c
        assert "# TASK-0010\nBody remains intact.\n" in new_c

    def test_updates_milestone_tag(self) -> None:
        content = (
            "---\n"
            "id: '0011'\n"
            "title: Sample Task\n"
            "status: Proposed\n"
            "milestone: M1\n"
            "---\n\n"
            "Markdown body\n"
        )
        modified, new_c, key, old_v = update_frontmatter_milestone(content, "M1", "M2")
        assert modified
        assert key == "milestone"
        assert "milestone: M2" in new_c
        assert "Markdown body" in new_c

    def test_preserves_comments_and_quotes(self) -> None:
        content = (
            "---\n"
            "id: '0012'\n"
            'target_release: "M1" # High priority deliverable\n'
            "---\n\n"
            "Body\n"
        )
        modified, new_c, _, _ = update_frontmatter_milestone(content, "M1", "M2")
        assert modified
        assert 'target_release: "M2" # High priority deliverable' in new_c

    def test_quotes_values_with_special_characters(self) -> None:
        content = (
            "---\n"
            "id: '0013'\n"
            "target_release: M1\n"
            "---\n"
        )
        modified, new_c, _, _ = update_frontmatter_milestone(content, "M1", "Milestone 2: Delivery")
        assert modified
        assert "target_release: 'Milestone 2: Delivery'" in new_c

    def test_force_update_appends_target_release(self) -> None:
        content = (
            "---\n"
            "id: '0014'\n"
            "title: Task Without Milestone\n"
            "status: Refined\n"
            "---\n\n"
            "Body\n"
        )
        modified, new_c, key, _ = update_frontmatter_milestone(
            content, "M1", "M2", force_update=True
        )
        assert modified
        assert key == "target_release"
        assert "target_release: M2" in new_c

    def test_unmatched_milestone_returns_false(self) -> None:
        content = (
            "---\n"
            "id: '0015'\n"
            "target_release: M3\n"
            "---\n"
        )
        modified, new_c, _, _ = update_frontmatter_milestone(content, "M1", "M2")
        assert not modified
        assert new_c == content

    def test_invalid_or_missing_frontmatter(self) -> None:
        content = "# Markdown with no frontmatter\n"
        modified, new_c, _, _ = update_frontmatter_milestone(content, "M1", "M2")
        assert not modified
        assert new_c == content


class TestMilestoneRolloverCoordinator:
    """Verifies coordinator behavior across workspace directories."""

    def test_coordinator_transitions_refined_and_proposed(self, tmp_path: Path) -> None:
        repo = tmp_path / "coordinator_ws"
        init_project(repo, name="CoordinatorTest")
        backlog = repo / "docs" / "project" / "backlog"

        (backlog / "complete").mkdir(parents=True, exist_ok=True)
        (backlog / "refined").mkdir(parents=True, exist_ok=True)
        (backlog / "proposed").mkdir(parents=True, exist_ok=True)

        comp_f = backlog / "complete" / "0001-comp.md"
        comp_f.write_text("---\nid: '0001'\nstatus: Complete\ntarget_release: M1\n---\nBody\n", encoding="utf-8")

        ref_f = backlog / "refined" / "0002-ref.md"
        ref_f.write_text("---\nid: '0002'\nstatus: Refined\ntarget_release: M1\n---\nBody\n", encoding="utf-8")

        prop_f = backlog / "proposed" / "0003-prop.md"
        prop_f.write_text("---\nid: '0003'\nstatus: Proposed\nmilestone: M1\n---\nBody\n", encoding="utf-8")

        coord = MilestoneRolloverCoordinator(backlog)
        result = coord.rollover("M1", "M2")

        assert result.transitioned_count == 2
        assert result.transitioned_tasks == ["TASK-0002", "TASK-0003"]
        assert not result.dry_run

        # Verify complete task is NOT touched
        comp_meta, _, _ = parse_frontmatter_and_body(comp_f.read_text(encoding="utf-8"))
        assert comp_meta["target_release"] == "M1"

        # Verify refined and proposed tasks are updated
        ref_meta, _, _ = parse_frontmatter_and_body(ref_f.read_text(encoding="utf-8"))
        assert ref_meta["target_release"] == "M2"

        prop_meta, _, _ = parse_frontmatter_and_body(prop_f.read_text(encoding="utf-8"))
        assert prop_meta["milestone"] == "M2"

    def test_dry_run_leaves_disk_untouched(self, tmp_path: Path) -> None:
        repo = tmp_path / "dry_run_ws"
        init_project(repo, name="DryRunTest")
        backlog = repo / "docs" / "project" / "backlog"
        (backlog / "refined").mkdir(parents=True, exist_ok=True)

        ref_f = backlog / "refined" / "0005-ref.md"
        initial_c = "---\nid: '0005'\nstatus: Refined\ntarget_release: M1\n---\nBody\n"
        ref_f.write_text(initial_c, encoding="utf-8")

        result = rollover_milestone(backlog, "M1", "M2", dry_run=True)
        assert result.dry_run
        assert result.transitioned_count == 1
        assert result.transitioned_tasks == ["TASK-0005"]
        assert ref_f.read_text(encoding="utf-8") == initial_c

    def test_roadmap_task_association(self, tmp_path: Path) -> None:
        repo = tmp_path / "roadmap_ws"
        init_project(repo, name="RoadmapTest")
        backlog = repo / "docs" / "project" / "backlog"
        (backlog / "refined").mkdir(parents=True, exist_ok=True)

        # Task in refined without frontmatter milestone
        ref_f = backlog / "refined" / "0006-ref.md"
        ref_f.write_text("---\nid: '0006'\ntitle: Task From Roadmap\nstatus: Refined\n---\nBody\n", encoding="utf-8")

        # Declare TASK-0006 under Milestone 1 in ROADMAP.md
        roadmap_f = backlog / "ROADMAP.md"
        roadmap_f.write_text("## Milestone 1: Core (Active)\n- Work item (`TASK-0006`).\n", encoding="utf-8")

        result = rollover_milestone(backlog, "M1", "M2", roadmap_path=roadmap_f)
        assert result.transitioned_count == 1
        assert result.transitioned_tasks == ["TASK-0006"]

        ref_meta, _, _ = parse_frontmatter_and_body(ref_f.read_text(encoding="utf-8"))
        assert ref_meta["target_release"] == "M2"

    def test_structured_result_to_dict(self) -> None:
        coord = MilestoneRolloverCoordinator(Path("/tmp/nonexistent"))
        result = coord.rollover("M1", "M2", dry_run=True)
        d = result.to_dict()
        assert d["from_milestone"] == "M1"
        assert d["to_milestone"] == "M2"
        assert d["transitioned_count"] == 0
        assert d["dry_run"] is True


class TestCLIHandler:
    """Verifies public CLI command dispatcher contracts."""

    def test_missing_milestones_returns_error(self, tmp_path: Path) -> None:
        config = load_config(tmp_path)
        args = argparse.Namespace(milestone_action="rollover", from_m=None, to_m=None)
        code = handle_milestone_command(args, config)
        assert code == 1

    def test_json_and_dry_run_dispatch(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        repo = tmp_path / "cli_ws"
        init_project(repo, name="CLITest")
        config = load_config(repo)

        args = argparse.Namespace(
            milestone_action="rollover",
            from_m="M1",
            to_m="M2",
            dry_run=True,
            json=True,
        )
        code = handle_milestone_command(args, config)
        assert code == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["from_milestone"] == "M1"
        assert data["to_milestone"] == "M2"
        assert data["dry_run"] is True
