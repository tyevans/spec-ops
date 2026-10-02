"""Unit tests for spec_ops.adrs.supersession to verify ADR supersession engine and maximize mutant kill score."""

from __future__ import annotations

import argparse
from pathlib import Path
import pytest

from spec_ops.adrs.supersede import (
    ADRNotFoundError,
    CircularSupersessionError,
)
from spec_ops.adrs.supersession import (
    ADRSupersessionEngine,
    find_next_adr_id,
    slugify,
)
from spec_ops.cli.adr_handler import handle_adr_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.parser import extract_frontmatter


def test_slugify():
    assert slugify("SQLite Storage Engine") == "sqlite-storage-engine"
    assert slugify("  Special   Characters! & Symbols?  ") == "special-characters-symbols"
    assert slugify("Already-Hyphenated") == "already-hyphenated"
    assert slugify("") == ""


def test_find_next_adr_id(tmp_path: Path):
    adrs_dir = tmp_path / "adrs"
    # Non-existent dir returns ADR-0001, 1
    next_id, num = find_next_adr_id(adrs_dir)
    assert next_id == "ADR-0001"
    assert num == 1

    adrs_dir.mkdir(parents=True)
    (adrs_dir / "adr-0003-test.md").write_text("content", encoding="utf-8")
    (adrs_dir / "adr-0010-test.md").write_text("content", encoding="utf-8")
    (adrs_dir / "non-adr.md").write_text("content", encoding="utf-8")

    next_id, num = find_next_adr_id(adrs_dir)
    assert next_id == "ADR-0011"
    assert num == 11


def test_get_adrs_dir(tmp_path: Path):
    engine = ADRSupersessionEngine(root_dir=tmp_path)
    # Default scaffolds docs/project/adrs
    adrs = engine.get_adrs_dir()
    assert adrs == tmp_path / "docs" / "project" / "adrs"
    assert adrs.exists()

    # Pre-existing candidate
    root2 = tmp_path / "root2"
    custom_adrs = root2 / "docs" / "adrs"
    custom_adrs.mkdir(parents=True)
    engine2 = ADRSupersessionEngine(root_dir=root2)
    assert engine2.get_adrs_dir() == custom_adrs


def test_scaffold_superseding_adr(tmp_path: Path):
    engine = ADRSupersessionEngine(root_dir=tmp_path)
    adrs_dir = tmp_path / "docs" / "project" / "adrs"

    # dry-run returns path without writing
    path_dry = engine.scaffold_superseding_adr(
        new_id="ADR-0002",
        title="New Architecture",
        old_id="ADR-0001",
        adrs_dir=adrs_dir,
        dry_run=True,
    )
    assert path_dry.name == "adr-0002-new-architecture.md"
    assert not path_dry.exists()

    # normal run writes file
    path_real = engine.scaffold_superseding_adr(
        new_id="ADR-0002",
        title="New Architecture",
        old_id="ADR-0001",
        adrs_dir=adrs_dir,
        dry_run=False,
    )
    assert path_real.exists()
    content = path_real.read_text(encoding="utf-8")
    assert "id: ADR-0002" in content
    assert "supersedes: ADR-0001" in content
    assert "status: Accepted" in content
    assert "# ADR-0002: New Architecture" in content


def test_supersede_raises_when_no_title_and_no_target(tmp_path: Path):
    engine = ADRSupersessionEngine(root_dir=tmp_path)
    adrs_dir = engine.get_adrs_dir()
    (adrs_dir / "accepted").mkdir(parents=True, exist_ok=True)
    adr1 = adrs_dir / "accepted" / "adr-0001.md"
    adr1.write_text("---\nid: ADR-0001\ntitle: One\nstatus: Accepted\n---\n# One\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Must provide either superseding target"):
        engine.supersede(old_target="ADR-0001")


def test_supersede_with_existing_target(tmp_path: Path):
    engine = ADRSupersessionEngine(root_dir=tmp_path)
    adrs_dir = engine.get_adrs_dir()
    accepted = adrs_dir / "accepted"
    proposed = adrs_dir / "proposed"
    accepted.mkdir(parents=True, exist_ok=True)
    proposed.mkdir(parents=True, exist_ok=True)

    adr1 = accepted / "adr-0001-old.md"
    adr1.write_text(
        "---\nid: ADR-0001\ntitle: Old Decision\nstatus: Accepted\n---\n# ADR-0001: Old Decision\n\n## Status\nAccepted\n",
        encoding="utf-8",
    )

    adr2 = proposed / "adr-0002-new.md"
    adr2.write_text(
        "---\nid: ADR-0002\ntitle: New Decision\nstatus: Proposed\n---\n# ADR-0002: New Decision\n\n## Status\nProposed\n",
        encoding="utf-8",
    )

    registry = adrs_dir / "REGISTRY.md"
    registry.write_text(
        "| [ADR-0001](file://accepted/adr-0001-old.md) | Old Decision | Accepted | - |\n",
        encoding="utf-8",
    )

    # Add a task citing ADR-0001 to test warning generation
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    task1 = backlog_dir / "0001-test-task.md"
    task1.write_text(
        "---\nid: TASK-0001\ntitle: Task 1\ngoverning_adrs:\n  - ADR-0001\n---\n",
        encoding="utf-8",
    )

    res = engine.supersede(old_target="ADR-0001", new_target="ADR-0002")
    assert res.old_id == "ADR-0001"
    assert res.new_id == "ADR-0002"
    assert len(res.warnings) == 1
    assert "TASK-0001 cites superseded ADR-0001" in res.warnings[0]

    # Verify ADR-0002 was moved to accepted
    assert not adr2.exists()
    assert (accepted / "adr-0002-new.md").exists()

    meta2, _ = extract_frontmatter((accepted / "adr-0002-new.md").read_text(encoding="utf-8"))
    assert meta2["status"] == "Accepted"
    assert meta2["supersedes"] == "ADR-0001"

    meta1, _ = extract_frontmatter(adr1.read_text(encoding="utf-8"))
    assert meta1["status"] == "Superseded"
    assert meta1["superseded_by"] == "ADR-0002"


def test_supersede_dry_run(tmp_path: Path):
    engine = ADRSupersessionEngine(root_dir=tmp_path)
    adrs_dir = engine.get_adrs_dir()
    accepted = adrs_dir / "accepted"
    accepted.mkdir(parents=True, exist_ok=True)

    adr1 = accepted / "adr-0001-old.md"
    adr1.write_text(
        "---\nid: ADR-0001\ntitle: Old Decision\nstatus: Accepted\n---\n# ADR-0001: Old Decision\n",
        encoding="utf-8",
    )

    res = engine.supersede(old_target="ADR-0001", title="Simulated Replacement", dry_run=True)
    assert res.old_id == "ADR-0001"
    assert res.new_id == "ADR-0002"

    # ADR-0001 should not be modified
    meta1, _ = extract_frontmatter(adr1.read_text(encoding="utf-8"))
    assert meta1["status"] == "Accepted"
    assert "superseded_by" not in meta1

    # New file should not be created
    assert not (accepted / "adr-0002-simulated-replacement.md").exists()


def test_handle_adr_command_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    config = SpecOpsConfig(root_dir=tmp_path)
    
    # Missing old_id
    args = argparse.Namespace(adr_action="supersede", opt_old=None, old_id=None, by=None, new_id_pos=None, title=None, dry_run=False)
    ret = handle_adr_command(args, config)
    assert ret == 1
    err = capsys.readouterr().err
    assert "Target ADR ID to supersede must be specified" in err

    # Missing both new_target and title
    args2 = argparse.Namespace(adr_action="supersede", opt_old="ADR-0001", old_id="ADR-0001", by=None, new_id_pos=None, title=None, dry_run=False)
    ret2 = handle_adr_command(args2, config)
    assert ret2 == 1
    err2 = capsys.readouterr().err
    assert "Superseding ADR must be specified" in err2
