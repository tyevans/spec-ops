"""Unit tests for src/spec_ops/core/migration.py to maximize mutmut mutant kill rate."""

from __future__ import annotations

from pathlib import Path

from spec_ops.core.migration import (
    canonicalize_adr_id,
    canonicalize_prd_id,
    canonicalize_story_id,
    canonicalize_task_id,
    generate_unified_diff,
    migrate_document_content,
    migrate_file,
    migrate_frontmatter,
    migrate_prd_metadata,
    migrate_specifications,
    migrate_story_metadata,
    migrate_task_metadata,
    parse_frontmatter_and_body,
    to_list_value,
)


def test_canonicalize_ids():
    # ADR
    assert canonicalize_adr_id(1) == "ADR-0001"
    assert canonicalize_adr_id("0042") == "ADR-0042"
    assert canonicalize_adr_id("adr-5") == "ADR-0005"
    assert canonicalize_adr_id("ADR-0012") == "ADR-0012"
    assert canonicalize_adr_id("CUSTOM-ADR") == "CUSTOM-ADR"

    # PRD
    assert canonicalize_prd_id(5) == "PRD-0005"
    assert canonicalize_prd_id("0003") == "PRD-0003"
    assert canonicalize_prd_id("prd-2") == "PRD-0002"
    assert canonicalize_prd_id("PRD-0001") == "PRD-0001"
    assert canonicalize_prd_id("OTHER") == "OTHER"

    # Story
    assert canonicalize_story_id(17) == "US-0017"
    assert canonicalize_story_id("0009") == "US-0009"
    assert canonicalize_story_id("us-1") == "US-0001"
    assert canonicalize_story_id("US-0017") == "US-0017"
    assert canonicalize_story_id("CUSTOM-STORY") == "CUSTOM-STORY"

    # Task
    assert canonicalize_task_id(76) == "TASK-0076"
    assert canonicalize_task_id("0008") == "TASK-0008"
    assert canonicalize_task_id("task-14") == "TASK-0014"
    assert canonicalize_task_id("TASK-0076") == "TASK-0076"
    assert canonicalize_task_id("SPIKE-0001") == "SPIKE-0001"


def test_to_list():
    assert to_list_value(None) == []
    assert to_list_value([1, 2]) == [1, 2]
    assert to_list_value("hello") == ["hello"]
    assert to_list_value(42) == [42]


def test_parse_frontmatter_and_body_edge_cases():
    # Does not start with ---
    m, raw, body = parse_frontmatter_and_body("# Just Heading\nNo frontmatter")
    assert m == {}
    assert raw == ""
    assert body == "# Just Heading\nNo frontmatter"

    # Single line with --- and no newline
    m, raw, body = parse_frontmatter_and_body("---")
    assert m == {}
    assert raw == ""
    assert body == "---"

    # Opening --- but no closing ---
    m, raw, body = parse_frontmatter_and_body("---\nid: '0001'\ntitle: Unclosed\n")
    assert m == {}
    assert raw == ""
    assert body == "---\nid: '0001'\ntitle: Unclosed\n"

    # Invalid YAML
    m, raw, body = parse_frontmatter_and_body("---\n: invalid: [yaml\n---\n# Body\n")
    assert m == {}
    assert ": invalid: [yaml" in raw
    assert body == "# Body\n"

    # Non-dictionary YAML (e.g. list or string)
    m, raw, body = parse_frontmatter_and_body("---\n- item1\n- item2\n---\n# Body\n")
    assert m == {}
    assert "- item1" in raw
    assert body == "# Body\n"

    # Empty frontmatter
    m, raw, body = parse_frontmatter_and_body("---\n---\n# Body\n")
    assert m == {}
    assert body == "# Body\n"


def test_migrate_task_metadata():
    # 1. governing_adr int
    meta = {"id": "0001", "governing_adr": 1}
    res, mod = migrate_task_metadata(meta)
    assert mod is True
    assert "governing_adr" not in res
    assert res["governing_adrs"] == ["ADR-0001"]

    # 2. governing_adr list with existing governing_adrs
    meta = {"id": "0001", "governing_adr": [2, "ADR-0003"], "governing_adrs": ["ADR-0001"]}
    res, mod = migrate_task_metadata(meta)
    assert mod is True
    assert res["governing_adrs"] == ["ADR-0001", "ADR-0002", "ADR-0003"]

    # 3. governing_prd and prd
    meta = {"id": "0001", "governing_prd": 5, "prd": 6}
    res, mod = migrate_task_metadata(meta)
    assert mod is True
    assert "governing_prd" not in res
    assert "prd" not in res
    assert res["governing_prds"] == ["PRD-0005", "PRD-0006"]

    # 4. governing_story, story, stories
    meta = {"id": "0001", "governing_story": 17, "story": 18, "stories": [19]}
    res, mod = migrate_task_metadata(meta)
    assert mod is True
    assert "governing_story" not in res
    assert "story" not in res
    assert "stories" not in res
    assert res["governing_stories"] == ["US-0017", "US-0018", "US-0019"]

    # 5. dependency scalar and existing dependencies
    meta = {"id": "0001", "dependency": 10, "dependencies": ["TASK-0005"]}
    res, mod = migrate_task_metadata(meta)
    assert mod is True
    assert "dependency" not in res
    assert res["dependencies"] == ["TASK-0005", "TASK-0010"]

    # 6. Standard ordering check
    meta = {
        "extra_field": "val",
        "title": "Title",
        "id": "0001",
        "status": "Refined",
        "target_bc": "core",
    }
    res, mod = migrate_task_metadata(meta)
    keys = list(res.keys())
    assert keys == ["id", "title", "status", "target_bc", "extra_field"]
    assert mod is False


def test_migrate_story_metadata():
    # governing_prds list -> governing_prd
    meta = {"id": "0017", "title": "Story", "governing_prds": [5, 6]}
    res, mod = migrate_story_metadata(meta)
    assert mod is True
    assert "governing_prds" not in res
    assert res["governing_prd"] == "PRD-0005"

    # prd scalar -> governing_prd
    meta = {"id": "0017", "title": "Story", "prd": "0002"}
    res, mod = migrate_story_metadata(meta)
    assert mod is True
    assert "prd" not in res
    assert res["governing_prd"] == "PRD-0002"

    # governing_prd not canonical
    meta = {"id": "0017", "title": "Story", "governing_prd": "prd-3"}
    res, mod = migrate_story_metadata(meta)
    assert mod is True
    assert res["governing_prd"] == "PRD-0003"

    # Already canonical
    meta = {"id": "0017", "title": "Story", "governing_prd": "PRD-0005"}
    res, mod = migrate_story_metadata(meta)
    assert mod is False


def test_migrate_prd_metadata():
    # target_bc -> component
    meta = {"id": "0005", "title": "PRD", "target_bc": "core"}
    res, mod = migrate_prd_metadata(meta)
    assert mod is True
    assert "target_bc" not in res
    assert res["component"] == "core"

    # target_personas list -> target_persona
    meta = {"id": "0005", "title": "PRD", "target_personas": ["Alex", "Jordan"]}
    res, mod = migrate_prd_metadata(meta)
    assert mod is True
    assert "target_personas" not in res
    assert res["target_persona"] == "Alex, Jordan"

    # target_personas str
    meta = {"id": "0005", "title": "PRD", "target_personas": "Alex"}
    res, mod = migrate_prd_metadata(meta)
    assert mod is True
    assert res["target_persona"] == "Alex"

    # Already clean
    meta = {"id": "0005", "title": "PRD", "component": "core", "target_persona": "Alex"}
    res, mod = migrate_prd_metadata(meta)
    assert mod is False


def test_migrate_frontmatter_dispatch():
    # Unknown doc type
    meta = {"id": "0001", "unknown": True}
    res, mod = migrate_frontmatter(meta, doc_type="other")
    assert mod is False
    assert res == meta


def test_migrate_document_content():
    # Empty content
    c, mod = migrate_document_content("")
    assert mod is False
    assert c == ""

    # Content without frontmatter
    c, mod = migrate_document_content("# Heading\nBody text")
    assert mod is False
    assert c == "# Heading\nBody text"

    # Content already conforming
    clean_doc = (
        "---\n"
        "id: '0076'\n"
        "title: Clean Task\n"
        "status: Refined\n"
        "target_bc: core\n"
        "governing_adrs:\n"
        "- ADR-0001\n"
        "---\n\n"
        "# Body\n"
    )
    c, mod = migrate_document_content(clean_doc, doc_type="task")
    assert mod is False
    assert c == clean_doc


def test_generate_unified_diff():
    # Identical
    assert generate_unified_diff("abc", "abc") == ""

    # Different
    diff = generate_unified_diff("line1\nline2\n", "line1\nline2_mod\n", "test.md")
    assert "--- a/test.md" in diff
    assert "+++ b/test.md" in diff
    assert "-line2" in diff
    assert "+line2_mod" in diff


def test_migrate_file_and_specifications(tmp_path: Path):
    # Non-existent file
    mod, diff, content = migrate_file(tmp_path / "non_existent.md")
    assert mod is False
    assert diff == ""
    assert content == ""

    # Clean file
    clean_file = tmp_path / "clean_task.md"
    clean_text = "---\nid: '0001'\ntitle: Clean\nstatus: Refined\ntarget_bc: core\n---\n# Body\n"
    clean_file.write_text(clean_text, encoding="utf-8")
    mod, diff, content = migrate_file(clean_file, in_place=False)
    assert mod is False
    assert diff == ""
    assert content == clean_text

    # Legacy file - dry run
    legacy_file = tmp_path / "legacy_task.md"
    legacy_text = "---\nid: '0002'\ntitle: Legacy\nstatus: Refined\ntarget_bc: core\ngoverning_adr: 1\n---\n# Body\n"
    legacy_file.write_text(legacy_text, encoding="utf-8")

    mod, diff, new_c = migrate_file(legacy_file, in_place=False)
    assert mod is True
    assert "-governing_adr: 1" in diff
    assert "+governing_adrs:" in diff
    assert legacy_file.read_text(encoding="utf-8") == legacy_text  # Unmodified on disk

    # Legacy file - in-place
    mod, diff, new_c = migrate_file(legacy_file, in_place=True)
    assert mod is True
    assert legacy_file.read_text(encoding="utf-8") != legacy_text
    assert "governing_adrs:" in legacy_file.read_text(encoding="utf-8")

    # migrate_specifications with non-existent target
    c, d, f = migrate_specifications(tmp_path, target_path=tmp_path / "nonexistent")
    assert c == 0
    assert d == ""
    assert f == []

    # migrate_specifications on tmp_path (now clean)
    c, d, f = migrate_specifications(tmp_path, target_path=tmp_path, in_place=False)
    assert c == 0
    assert d == ""
    assert f == []
