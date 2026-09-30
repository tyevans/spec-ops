"""Generative Hypothesis property-based tests for cache transparency and parser resilience."""

from __future__ import annotations

import string
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.spikes.cache_spike import (
    FrontmatterDiagnosticError,
    RelationalGraphCacheEngine,
    compute_cache_checksum,
    compute_content_sha256,
    parse_markdown_document,
)


@given(
    content=st.text(
        alphabet=string.ascii_letters + string.digits + string.whitespace + string.punctuation,
        max_size=500,
    )
)
@settings(max_examples=100)
def test_hypothesis_ast_parser_resilience(content: str):
    """Resilience invariant: arbitrary inputs always yield (dict, str) or FrontmatterDiagnosticError."""
    try:
        data, body = parse_markdown_document(content, file_path="arbitrary.md")
        assert isinstance(data, dict)
        assert isinstance(body, str)
    except FrontmatterDiagnosticError as err:
        assert isinstance(err.line, int)
        assert isinstance(err.column, int)
        assert len(err.format_error()) > 0
    except Exception as exc:
        pytest.fail(f"Unhandled exception raised on input {content!r}: {type(exc)}: {exc}")


@given(
    titles=st.lists(
        st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=20),
        min_size=2,
        max_size=8,
        unique=True,
    )
)
@settings(max_examples=25)
def test_hypothesis_cache_transparency_invariant(tmp_path_factory, titles: list[str]):
    """Cache transparency invariant: warm compilation yields identical ProjectData to cold compilation."""
    tmp_path = tmp_path_factory.mktemp("hyp_cache")
    docs = tmp_path / "docs" / "project" / "backlog" / "refined"
    docs.mkdir(parents=True, exist_ok=True)

    for idx, t in enumerate(titles, start=1):
        (docs / f"{idx:04d}-{t}.md").write_text(
            f"---\nid: '{idx:04d}'\ntitle: Task {t}\nstatus: Refined\n---\n# Body\n",
            encoding="utf-8",
        )

    engine = RelationalGraphCacheEngine(tmp_path)
    cold_data, cold_stats = engine.compile_graph(force_cold=True)
    assert cold_stats.cold is True

    warm_data, warm_stats = engine.compile_graph()
    assert warm_stats.cold is False
    assert warm_stats.invalidated == 0
    assert warm_stats.cache_hits == len(titles)

    cold_titles = sorted(t.title for t in cold_data.tasks)
    warm_titles = sorted(t.title for t in warm_data.tasks)
    assert cold_titles == warm_titles
    assert len(cold_data.edges) == len(warm_data.edges)


@given(
    corrupt_data=st.text(
        alphabet=string.ascii_letters + string.digits + "{}[];:,.'\" \n\r\t",
        max_size=200,
    )
)
@settings(max_examples=30)
def test_hypothesis_cache_corruption_recovery(tmp_path_factory, corrupt_data: str):
    """Corruption recovery invariant: arbitrary corrupt cache file payloads cleanly self-heal."""
    tmp_path = tmp_path_factory.mktemp("hyp_corrupt")
    docs = tmp_path / "docs" / "project" / "backlog" / "refined"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "0001-task.md").write_text(
        "---\nid: '0001'\ntitle: Task One\nstatus: Refined\n---\n# Task\n",
        encoding="utf-8",
    )

    engine = RelationalGraphCacheEngine(tmp_path)
    engine.cache_file.parent.mkdir(parents=True, exist_ok=True)
    engine.cache_file.write_text(corrupt_data, encoding="utf-8")

    data, stats = engine.compile_graph()
    assert stats.cold is True
    assert stats.total_indexed == 1
    assert len(data.tasks) == 1
    assert data.tasks[0].title == "Task One"
