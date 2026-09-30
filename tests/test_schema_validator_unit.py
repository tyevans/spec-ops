"""Unit tests for src/spec_ops/core/schema_validator.py to maximize test and mutation coverage."""

from __future__ import annotations

from pathlib import Path

from spec_ops.core.schema_validator import (
    ADRFrontmatter,
    PRDFrontmatter,
    SchemaDiagnosticError,
    TaskFrontmatter,
    UserStoryFrontmatter,
    collect_specification_files,
    detect_document_type,
    get_field_locations,
    is_specification_file,
    validate_document,
    validate_frontmatter_dict,
    validate_specifications,
)


def test_schema_diagnostic_error_formatting():
    err1 = SchemaDiagnosticError(
        file_path="task.md",
        line=4,
        column=2,
        message="Invalid syntax",
        source_snippet="  bad_indent: 1",
        hint="Fix indentation",
    )
    msg1 = err1.format_error()
    assert "error: Schema Validation Error in task.md:4:2" in msg1
    assert "4 |   bad_indent: 1" in msg1
    assert "^ Invalid syntax" in msg1
    assert "hint: Fix indentation" in msg1
    assert str(err1) == msg1

    err2 = SchemaDiagnosticError(
        file_path="task.md",
        line=1,
        column=1,
        message="Missing delimiter",
    )
    msg2 = err2.format_error()
    assert "| Missing delimiter" in msg2


def test_detect_document_type():
    # By path
    assert detect_document_type("docs/project/user_stories/accepted/us-0001.md") == "story"
    assert detect_document_type("us-0002.md") == "story"
    assert detect_document_type("docs/project/product/accepted/prd-0001.md") == "prd"
    assert detect_document_type("prd-0002.md") == "prd"
    assert detect_document_type("docs/project/backlog/refined/0001.md") == "task"
    assert detect_document_type("task-0001.md") == "task"
    assert detect_document_type("docs/project/adrs/accepted/adr-0001.md") == "adr"

    # By frontmatter meta clues
    assert detect_document_type("custom.md", {"target_persona": "Dev"}) == "prd"
    assert detect_document_type("custom.md", {"component": "core"}) == "prd"
    assert detect_document_type("custom.md", {"persona": "Alex"}) == "story"
    assert detect_document_type("custom.md", {"governing_prd": "PRD-0001"}) == "story"
    assert detect_document_type("custom.md", {"governing_adrs": ["ADR-0001"]}) == "task"
    assert detect_document_type("custom.md", {"target_bc": "core"}) == "task"
    assert detect_document_type("custom.md", {}) == "task"


def test_get_field_locations():
    # Empty or invalid YAML
    assert get_field_locations("") == {}
    assert get_field_locations(": invalid: [") == {}
    assert get_field_locations("- list\n- item") == {}

    # Valid YAML mapping
    yaml_txt = "id: '0076'\ntitle: Task Title\nstatus: Refined\n"
    locs = get_field_locations(yaml_txt, offset=2)
    assert locs["id"] == (2, 1)
    assert locs["title"] == (3, 1)
    assert locs["status"] == (4, 1)


def test_validate_frontmatter_dict():
    # Valid Task
    meta = {
        "id": "0076",
        "title": "Title",
        "status": "Refined",
        "target_bc": "core",
        "dependencies": [],
        "governing_adrs": ["ADR-0001"],
    }
    errs = validate_frontmatter_dict(meta, "task")
    assert errs == []

    # Task with legacy field
    legacy_meta = {
        "id": "0076",
        "title": "Title",
        "status": "Refined",
        "target_bc": "core",
        "governing_adr": 1,
    }
    errs = validate_frontmatter_dict(legacy_meta, "task", file_path="task.md")
    assert len(errs) >= 1
    assert any("Legacy field 'governing_adr'" in e.message for e in errs)

    # Missing required field
    missing_meta = {"id": "0076", "status": "Refined"}
    errs = validate_frontmatter_dict(missing_meta, "task", file_path="task.md")
    assert any("Missing required field 'title'" in e.message for e in errs)

    # Extra forbidden field
    extra_meta = {"id": "0076", "title": "T", "status": "Refined", "unknown_field": "val"}
    errs = validate_frontmatter_dict(extra_meta, "task", file_path="task.md")
    assert any("Forbidden extra field 'unknown_field'" in e.message for e in errs)


def test_validate_document_edge_cases():
    # Missing opening delimiter
    errs = validate_document("# Title\nNo frontmatter\n", file_path="no_fm.md")
    assert len(errs) == 1
    assert "File does not start with standard YAML '---' delimiter" in errs[0].message

    # Syntax error in YAML
    errs = validate_document("---\nid: '0001'\n  bad_indent: 123\n---\n# Body\n", file_path="bad_yaml.md")
    assert len(errs) == 1
    assert errs[0].line >= 2

    # Clean document
    clean_doc = (
        "---\n"
        "id: '0076'\n"
        "title: Valid Task\n"
        "status: Refined\n"
        "target_bc: core\n"
        "governing_adrs:\n"
        "- ADR-0001\n"
        "---\n\n"
        "# Body\n"
    )
    assert validate_document(clean_doc, file_path="clean.md") == []


def test_is_specification_file(tmp_path: Path):
    # Non-markdown
    assert not is_specification_file(Path("file.txt"))

    # Ignored metadata names
    assert not is_specification_file(Path("docs/project/backlog/PRIORITY.md"))
    assert not is_specification_file(Path("docs/project/backlog/ROADMAP.md"))
    assert not is_specification_file(Path("docs/project/product/REGISTRY.md"))
    assert not is_specification_file(Path("docs/project/user_stories/PERSONAS.md"))

    # File in backlog
    assert is_specification_file(Path("docs/project/backlog/refined/task-0001.md"))

    # Arbitrary file with frontmatter
    fm_file = tmp_path / "custom.md"
    fm_file.write_text("---\nid: '1'\n---\n")
    assert is_specification_file(fm_file)

    # Arbitrary file without frontmatter
    no_fm_file = tmp_path / "other.md"
    no_fm_file.write_text("# Just Heading")
    assert not is_specification_file(no_fm_file)


def test_collect_and_validate_specifications(tmp_path: Path):
    # Empty directory
    is_valid, errors, count = validate_specifications(tmp_path)
    assert is_valid is True
    assert errors == []
    assert count == 0

    # Directory with clean file
    docs = tmp_path / "docs" / "project" / "backlog" / "refined"
    docs.mkdir(parents=True)
    task1 = docs / "task-0001.md"
    task1.write_text(
        "---\n"
        "id: '0001'\n"
        "title: Task 1\n"
        "status: Refined\n"
        "target_bc: core\n"
        "governing_adrs: ['ADR-0001']\n"
        "---\n"
    )
    is_valid, errors, count = validate_specifications(tmp_path)
    assert is_valid is True
    assert count == 1
    assert errors == []

    # Add invalid file
    task2 = docs / "task-0002.md"
    task2.write_text(
        "---\n"
        "id: '0002'\n"
        "status: Refined\n"
        "---\n"
    )
    is_valid, errors, count = validate_specifications(tmp_path)
    assert is_valid is False
    assert count == 2
    assert len(errors) >= 1
