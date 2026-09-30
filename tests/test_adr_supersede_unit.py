"""Unit tests for spec_ops.adrs.supersede to maximize mutant kill rate under mutmut."""

from __future__ import annotations

import argparse
from pathlib import Path
import pytest

from spec_ops.adrs.supersede import (
    ADRNotFoundError,
    CircularSupersessionError,
    detect_supersession_cycles,
    discover_superseded_adrs,
    find_adr_file,
    find_tasks_citing_adr,
    normalize_adr_id,
    parse_adr_info,
    supersede_adr,
    update_registry_supersession,
    write_adr_frontmatter,
)
from spec_ops.cli.adr_handler import handle_adr_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.parser import extract_frontmatter


def test_normalize_adr_id_variations():
    assert normalize_adr_id("ADR-0003") == "ADR-0003"
    assert normalize_adr_id("adr-3") == "ADR-0003"
    assert normalize_adr_id("15") == "ADR-0015"
    assert normalize_adr_id("ADR-15") == "ADR-0015"
    assert normalize_adr_id(Path("some/dir/adr-0042-test.md")) == "ADR-0042"
    assert normalize_adr_id("ADR-CUSTOM") == "ADR-CUSTOM"
    assert normalize_adr_id("custom") == "CUSTOM"


def test_find_adr_file_direct_and_search(tmp_path: Path):
    adrs_dir = tmp_path / "docs" / "project" / "adrs"
    accepted = adrs_dir / "accepted"
    proposed = adrs_dir / "proposed"
    accepted.mkdir(parents=True, exist_ok=True)
    proposed.mkdir(parents=True, exist_ok=True)

    adr1 = accepted / "adr-0001-first.md"
    adr1.write_text("# ADR-0001: First\n\n## Status\nAccepted\n", encoding="utf-8")

    adr2 = proposed / "adr-0002-second.md"
    adr2.write_text("---\nid: '0002'\ntitle: Second\nstatus: Proposed\n---\n", encoding="utf-8")

    adr3 = accepted / "special-name.md"
    adr3.write_text("---\nid: '0003'\ntitle: Special\n---\n", encoding="utf-8")

    adr4 = accepted / "heading-only.md"
    adr4.write_text("# ADR-0004: Heading Only\n\nContent here.\n", encoding="utf-8")

    # Direct Path
    assert find_adr_file(adrs_dir, adr1) == adr1.resolve()

    # Relative to adrs_dir
    assert find_adr_file(adrs_dir, "accepted/adr-0001-first.md") == adr1.resolve()

    # Relative to adrs_dir.parent
    assert find_adr_file(adrs_dir, "adrs/accepted/adr-0001-first.md") == adr1.resolve()

    # By canonical ID
    assert find_adr_file(adrs_dir, "ADR-0001") == adr1.resolve()
    assert find_adr_file(adrs_dir, "1") == adr1.resolve()
    assert find_adr_file(adrs_dir, "ADR-0002") == adr2.resolve()
    assert find_adr_file(adrs_dir, "ADR-0003") == adr3.resolve()
    assert find_adr_file(adrs_dir, "ADR-0004") == adr4.resolve()

    # Not found
    with pytest.raises(ADRNotFoundError):
        find_adr_file(adrs_dir, "ADR-9999")


def test_detect_supersession_cycles_all_cases():
    # Self-supersession
    with pytest.raises(CircularSupersessionError, match="cannot supersede itself"):
        detect_supersession_cycles({}, ("ADR-0001", "ADR-0001"))

    # Direct cycle: A -> B and then B -> A
    existing = {"ADR-0001": "ADR-0002"}
    with pytest.raises(CircularSupersessionError, match="Circular ADR supersession detected"):
        detect_supersession_cycles(existing, ("ADR-0002", "ADR-0001"))

    # 3-node cycle: A -> B -> C and then C -> A
    existing_3 = {"ADR-0001": "ADR-0002", "ADR-0002": "ADR-0003"}
    with pytest.raises(CircularSupersessionError, match="Circular ADR supersession detected: ADR-0001 -> ADR-0002 -> ADR-0003 -> ADR-0001"):
        detect_supersession_cycles(existing_3, ("ADR-0003", "ADR-0001"))

    # Valid chain without cycle
    detect_supersession_cycles(existing_3, ("ADR-0003", "ADR-0004"))


def test_update_registry_supersession_scenarios(tmp_path: Path):
    reg = tmp_path / "REGISTRY.md"

    # Missing file returns cleanly
    update_registry_supersession(reg, "ADR-0001", "ADR-0002")
    assert not reg.exists()

    # Populate registry
    reg.write_text(
        "# ADR Registry\n\n"
        "| ID | Title | Status | Date |\n"
        "|---|---|---|---|\n"
        "| ADR-0001 | First Rule | Accepted | 2026-09-01 |\n"
        "| ADR-0002 | Second Rule | Proposed | 2026-09-02 |\n",
        encoding="utf-8",
    )

    # Supersede existing with existing
    update_registry_supersession(reg, "ADR-0001", "ADR-0002", new_title="Second Rule")
    content = reg.read_text(encoding="utf-8")
    assert "| ADR-0001 | First Rule | Superseded (by ADR-0002) | 2026-09-01 |" in content
    assert "| ADR-0002 | Second Rule | Accepted | 2026-09-02 |" in content

    # Supersede with a brand new ADR not in registry
    update_registry_supersession(reg, "ADR-0002", "ADR-0003", new_title="Third Rule", new_date="2026-09-30")
    content2 = reg.read_text(encoding="utf-8")
    assert "| ADR-0002 | Second Rule | Superseded (by ADR-0003) | 2026-09-02 |" in content2
    assert "| ADR-0003 | Third Rule | Accepted | 2026-09-30 |" in content2


def test_write_adr_frontmatter_and_parse_info(tmp_path: Path):
    f = tmp_path / "adr-0010-test.md"

    # Write without body
    write_adr_frontmatter(f, {"id": "0010", "status": "Accepted"}, "")
    meta, body, title, canon_id = parse_adr_info(f)
    assert meta["id"] == "0010"
    assert canon_id == "ADR-0010"
    assert title == "adr-0010-test"

    # Write with body and title
    write_adr_frontmatter(f, {"id": "0010", "title": "Custom Title", "status": "Accepted"}, "# Heading\n\nSome body")
    meta2, body2, title2, canon_id2 = parse_adr_info(f)
    assert title2 == "Custom Title"
    assert "Some body" in body2

    # File without frontmatter
    f_raw = tmp_path / "adr-0020-raw.md"
    f_raw.write_text("# ADR-0020: Raw Heading\n\n## Status\nAccepted\n", encoding="utf-8")
    meta3, body3, title3, canon_id3 = parse_adr_info(f_raw)
    assert canon_id3 == "ADR-0020"
    assert title3 == "Raw Heading"
    assert "## Status" in body3


def test_discover_superseded_adrs_sources(tmp_path: Path):
    adrs_dir = tmp_path / "adrs"

    # Non-existent directory
    assert discover_superseded_adrs(adrs_dir) == {}

    adrs_dir.mkdir(parents=True)

    # 1. Via REGISTRY.md
    (adrs_dir / "REGISTRY.md").write_text(
        "| ADR-0001 | Title | Superseded (by ADR-0002) | 2026-09-29 |\n",
        encoding="utf-8",
    )

    # 2. Via Frontmatter
    (adrs_dir / "adr-0002-second.md").write_text(
        "---\nid: '0002'\nstatus: Superseded\nsuperseded_by: ADR-0003\n---\n",
        encoding="utf-8",
    )

    # 3. Via Body text
    (adrs_dir / "adr-0003-third.md").write_text(
        "---\nid: '0003'\n---\n# ADR-0003\n\nSuperseded by ADR-0004\n",
        encoding="utf-8",
    )

    superseded = discover_superseded_adrs(adrs_dir)
    # Transitive flattening: 1 -> 2 -> 3 -> 4  =>  1 -> 4, 2 -> 4, 3 -> 4
    assert superseded["ADR-0001"] == "ADR-0004"
    assert superseded["ADR-0002"] == "ADR-0004"
    assert superseded["ADR-0003"] == "ADR-0004"


def test_find_tasks_citing_adr_sources(tmp_path: Path):
    backlog_dir = tmp_path / "backlog"

    # Non-existent
    assert find_tasks_citing_adr(backlog_dir, "ADR-0001") == []

    refined = backlog_dir / "refined"
    proposed = backlog_dir / "proposed"
    refined.mkdir(parents=True)
    proposed.mkdir(parents=True)

    # Task with singular governing_adr
    t1 = refined / "0001-task.md"
    t1.write_text("---\nid: '0001'\ngoverning_adr: ADR-0001\n---\n", encoding="utf-8")

    # Task with list governing_adrs
    t2 = proposed / "0002-task.md"
    t2.write_text("---\nid: '0002'\ngoverning_adrs: ['ADR-0001', 'ADR-0005']\n---\n", encoding="utf-8")

    # Task with body citation
    t3 = refined / "0003-task.md"
    t3.write_text("---\nid: '0003'\n---\n# TASK-0003\nGoverned by ADR-0001\n", encoding="utf-8")

    # Task with different ADR
    t4 = proposed / "0004-task.md"
    t4.write_text("---\nid: '0004'\ngoverning_adrs: ['ADR-0099']\n---\n", encoding="utf-8")

    citing = find_tasks_citing_adr(backlog_dir, "ADR-0001")
    assert citing == ["TASK-0001", "TASK-0002", "TASK-0003"]


def test_handle_adr_command_cli_interface(tmp_path: Path, capsys: pytest.CaptureFixture):
    cfg = SpecOpsConfig(root_dir=tmp_path)
    adrs_dir = cfg.project_docs_dir / "adrs"
    accepted = adrs_dir / "accepted"
    proposed = adrs_dir / "proposed"
    accepted.mkdir(parents=True)
    proposed.mkdir(parents=True)

    (accepted / "adr-0001-a.md").write_text("# ADR-0001: A\n\n## Status\nAccepted\n", encoding="utf-8")
    (proposed / "adr-0002-b.md").write_text("# ADR-0002: B\n\n## Status\nProposed\n", encoding="utf-8")
    (adrs_dir / "REGISTRY.md").write_text("| ADR-0001 | A | Accepted | 2026-09-29 |\n", encoding="utf-8")

    # Missing action
    args_bad = argparse.Namespace(command="adr", adr_action="unknown")
    assert handle_adr_command(args_bad, cfg) == 1

    # Missing target
    args_no_target = argparse.Namespace(command="adr", adr_action="supersede", old_id="ADR-0001", by=None, new_id_pos=None)
    assert handle_adr_command(args_no_target, cfg) == 1

    # Successful supersession
    args_ok = argparse.Namespace(command="adr", adr_action="supersede", old_id="ADR-0001", by="ADR-0002", new_id_pos=None)
    ret = handle_adr_command(args_ok, cfg)
    assert ret == 0
    captured = capsys.readouterr()
    assert "✨ Superseded ADR-0001 by ADR-0002" in captured.out

    # Circular error handling
    args_circular = argparse.Namespace(command="adr", adr_action="supersede", old_id="ADR-0002", by="ADR-0001", new_id_pos=None)
    ret_circ = handle_adr_command(args_circular, cfg)
    assert ret_circ == 1
    captured_circ = capsys.readouterr()
    assert "Circular ADR supersession detected" in captured_circ.err
