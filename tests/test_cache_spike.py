"""Comprehensive tests for content-addressed graph cache and resilient AST parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from spec_ops.core.models import ADR, PRD, Persona, Task, UserStory
from spec_ops.core.spikes.cache_spike import (
    BenchmarkResult,
    CompileStats,
    FrontmatterDiagnosticError,
    RelationalGraphCacheEngine,
    _deserialize_entity,
    _serialize_entity,
    benchmark_graph_compilation,
    compute_cache_checksum,
    compute_content_sha256,
    parse_markdown_document,
)


def test_frontmatter_diagnostic_error_formatting():
    err_delim = FrontmatterDiagnosticError(
        file_path="task.md",
        line=1,
        column=1,
        message="Missing Frontmatter: File does not start with standard YAML '---' delimiter",
        hint="Run 'spec-ops scaffold task' to generate a valid frontmatter template",
        is_missing_delim=True,
    )
    assert "Missing Frontmatter:" in str(err_delim)
    assert "spec-ops scaffold task" in err_delim.format_error()

    err_syntax = FrontmatterDiagnosticError(
        file_path="task.md",
        line=4,
        column=3,
        message="unexpected mapping indentation",
        source_snippet="  dependencies: [TASK-0001]",
    )
    msg = str(err_syntax)
    assert "error: Frontmatter YAML Syntax Error in task.md:4:3" in msg
    assert "4 |   dependencies: [TASK-0001]" in msg
    assert "|   ^ unexpected mapping indentation" in msg


def test_parse_markdown_document_missing_delimiters():
    with pytest.raises(FrontmatterDiagnosticError) as exc_info:
        parse_markdown_document("# No delimiter here\nContent", file_path="sample.md")
    assert exc_info.value.is_missing_delim is True
    assert "Missing Frontmatter" in exc_info.value.message

    with pytest.raises(FrontmatterDiagnosticError) as exc_info2:
        parse_markdown_document("---\nid: '0001'\ntitle: Unclosed\n", file_path="sample.md")
    assert exc_info2.value.is_missing_delim is True
    assert "Closing '---' delimiter not found" in exc_info2.value.message


def test_parse_markdown_document_valid_preserves_ast():
    content = """---
id: '0042'
title: Sample Task
status: Refined
---
<!-- Comments -->
# Table
| A | B |
|---|---|
| 1 | 2 |
```python
def foo():
    return 42
```
"""
    meta, body = parse_markdown_document(content, file_path="task.md")
    assert meta["id"] == "0042"
    assert meta["title"] == "Sample Task"
    assert "<!-- Comments -->" in body
    assert "| A | B |" in body
    assert "def foo():" in body


def test_parse_markdown_document_malformed_yaml_diagnostics():
    bad_yaml = """---
id: '0051'
title: Broken Task
  dependencies: [TASK-0001]
---
# Body
"""
    with pytest.raises(FrontmatterDiagnosticError) as exc_info:
        parse_markdown_document(bad_yaml, file_path="0051.md")
    err = exc_info.value
    assert err.line == 4
    assert err.column == 3
    assert "unexpected mapping indentation" in err.message

    bad_syntax = """---
id: '0052'
title: [unclosed bracket
---
# Body
"""
    with pytest.raises(FrontmatterDiagnosticError) as exc_info2:
        parse_markdown_document(bad_syntax, file_path="0052.md")
    assert exc_info2.value.line >= 2


def test_compute_hashes_and_checksums():
    h1 = compute_content_sha256("test")
    h2 = compute_content_sha256(b"test")
    assert h1 == h2
    assert len(h1) == 64

    payload = {"entities": {"a": 1}, "edges": [{"b": 2}]}
    cs = compute_cache_checksum(payload)
    assert len(cs) == 64
    assert compute_cache_checksum(payload) == cs


def test_serialize_and_deserialize_entities(tmp_path: Path):
    persona = Persona(id="alex", name="Alex", role="Architect", file_path=tmp_path / "p.md")
    ser_p = _serialize_entity(persona)
    des_p = _deserialize_entity("persona", ser_p)
    assert des_p.id == "alex"
    assert des_p.name == "Alex"

    story = UserStory(id="US-0001", title="Story 1", persona="Alex", file_path=tmp_path / "s.md")
    ser_s = _serialize_entity(story)
    des_s = _deserialize_entity("story", ser_s)
    assert des_s.id == "US-0001"

    prd = PRD(id="PRD-0001", title="PRD 1", target_persona="Alex")
    ser_prd = _serialize_entity(prd)
    des_prd = _deserialize_entity("prd", ser_prd)
    assert des_prd.id == "PRD-0001"

    task = Task(id="0001", title="Task 1", dependencies=["TASK-0002"], target_bc="core")
    ser_t = _serialize_entity(task)
    des_t = _deserialize_entity("task", ser_t)
    assert des_t.canonical_id == "TASK-0001"

    adr = ADR(id="ADR-0001", title="Arch 1", decision="Decide")
    ser_a = _serialize_entity(adr)
    des_a = _deserialize_entity("adr", ser_a)
    assert des_a.id == "ADR-0001"

    assert _deserialize_entity("unknown", {}) is None


def test_cache_engine_missing_docs_dir(tmp_path: Path):
    engine = RelationalGraphCacheEngine(tmp_path)
    data, stats = engine.compile_graph()
    assert stats.cold is True
    assert stats.total_indexed == 0


def test_cache_engine_downstream_dependency_invalidation(tmp_path: Path):
    """Verifies DoD 2: single-file edit invalidates strictly that node and immediate downstream dependents."""
    docs = tmp_path / "docs" / "project"
    backlog = docs / "backlog" / "refined"
    backlog.mkdir(parents=True, exist_ok=True)

    # Task 1 (base)
    (backlog / "0001-task.md").write_text(
        "---\nid: '0001'\ntitle: Task 1 Base\nstatus: Refined\ndependencies: []\n---\n# T1\n",
        encoding="utf-8",
    )
    # Task 2 depends on Task 1 (downstream of Task 1)
    (backlog / "0002-task.md").write_text(
        "---\nid: '0002'\ntitle: Task 2 Dependent\nstatus: Refined\ndependencies: [TASK-0001]\n---\n# T2\n",
        encoding="utf-8",
    )
    # Task 3 depends on Task 2 (downstream of Task 2)
    (backlog / "0003-task.md").write_text(
        "---\nid: '0003'\ntitle: Task 3 Independent\nstatus: Refined\ndependencies: [TASK-0002]\n---\n# T3\n",
        encoding="utf-8",
    )

    engine = RelationalGraphCacheEngine(tmp_path)
    # 1. Cold compile
    p_data, stats = engine.compile_graph(force_cold=True)
    assert stats.cold is True
    assert stats.total_indexed == 3
    assert stats.invalidated == 0

    # 2. Modify Task 1
    (backlog / "0001-task.md").write_text(
        "---\nid: '0001'\ntitle: Task 1 Updated\nstatus: Refined\ndependencies: []\n---\n# T1 Modified\n",
        encoding="utf-8",
    )

    # 3. Incremental compile
    p_data2, stats2 = engine.compile_graph()
    assert stats2.cold is False
    # Task 1 was modified, Task 2 is immediate downstream dependent of Task 1 -> both invalidated (2 files)
    # Task 3 is downstream of Task 2, not immediate downstream of Task 1 -> remains cached (1 cache hit)
    assert stats2.invalidated == 2
    assert stats2.cache_hits == 1


def test_cache_engine_corrupt_payload_recovery(tmp_path: Path):
    """Verifies DoD 3: corrupted or truncated cache files are detected and self-healed cleanly."""
    docs = tmp_path / "docs" / "project" / "backlog" / "refined"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "0001-task.md").write_text(
        "---\nid: '0001'\ntitle: Task 1\nstatus: Refined\n---\n# Body\n", encoding="utf-8"
    )

    engine = RelationalGraphCacheEngine(tmp_path)
    engine.compile_graph(force_cold=True)
    assert engine.cache_file.exists()

    # Corrupt the cache file
    engine.cache_file.write_text("{truncated json...", encoding="utf-8")
    raw, was_corrupt = engine.load_cache()
    assert raw is None
    assert was_corrupt is True

    # Checksum mismatch
    valid_json = {"version": 1, "checksum": "wrong-checksum", "entities": {}, "edges": []}
    engine.cache_file.write_text(json.dumps(valid_json), encoding="utf-8")
    raw2, was_corrupt2 = engine.load_cache()
    assert raw2 is None
    assert was_corrupt2 is True

    # Rebuild recovers cleanly
    p_data, stats = engine.compile_graph()
    assert stats.cold is True
    assert stats.total_indexed == 1
    assert engine.cache_file.exists()
    payload = json.loads(engine.cache_file.read_text(encoding="utf-8"))
    assert payload["checksum"] == compute_cache_checksum(payload)


def test_benchmark_graph_compilation_synthetic():
    """Verifies DoD 1: 1,000-entity graph compilation benchmark."""
    res = benchmark_graph_compilation(num_entities=1000)
    assert isinstance(res, BenchmarkResult)
    assert res.entities_count == 1000
    assert res.cold_seconds < 1.5
    assert res.warm_seconds < 0.100
