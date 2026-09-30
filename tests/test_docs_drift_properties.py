"""Hypothesis generative property tests for documentation drift guard and visualizer deep linking."""

from __future__ import annotations

import string
from hypothesis import given, strategies as st

from spec_ops.docs.checker import evaluate_cli_drift, is_command_documented
from spec_ops.visualizer.cli_bridge import generate_entity_deep_link, normalize_entity_id

cmd_alphabet = string.ascii_lowercase + string.digits + "-_"
cmd_strategy = st.text(alphabet=cmd_alphabet, min_size=1, max_size=20).map(lambda s: f"spec-ops test-{s}")
doc_text_strategy = st.text(alphabet=string.ascii_letters + string.digits + " \n\t`#|-*_", min_size=0, max_size=100)


@given(cmd=cmd_strategy, doc_texts=st.lists(doc_text_strategy, min_size=0, max_size=5))
def test_property_undocumented_command_flagged_deterministically(cmd: str, doc_texts: list[str]):
    """Any command not appearing in doc_texts is deterministically flagged by evaluate_cli_drift."""
    is_present = any(cmd in text for text in doc_texts)
    undocumented = evaluate_cli_drift([cmd], doc_texts)

    if is_present:
        assert cmd not in undocumented
        assert is_command_documented(cmd, doc_texts) is True
    else:
        assert cmd in undocumented
        assert is_command_documented(cmd, doc_texts) is False


@given(
    commands=st.lists(cmd_strategy, min_size=1, max_size=10, unique=True),
    doc_texts=st.lists(doc_text_strategy, min_size=0, max_size=5),
)
def test_property_subset_and_sorted_invariants(commands: list[str], doc_texts: list[str]):
    """Undocumented commands are always a subset of original commands and sorted."""
    undocumented = evaluate_cli_drift(commands, doc_texts)
    assert set(undocumented).issubset(set(commands))
    assert undocumented == sorted(undocumented)

    for cmd in commands:
        if any(cmd in text for text in doc_texts):
            assert cmd not in undocumented
        else:
            assert cmd in undocumented


@given(cmd=cmd_strategy)
def test_property_fully_documented_returns_empty(cmd: str):
    """When documentation text contains the command, evaluate_cli_drift returns zero drift."""
    doc_texts = [f"Here is `{cmd}` in reference.\n"]
    assert evaluate_cli_drift([cmd], doc_texts) == []
    assert is_command_documented(cmd, doc_texts) is True


@given(
    entity_num=st.integers(min_value=1, max_value=9999),
    host=st.sampled_from(["127.0.0.1", "localhost", "0.0.0.0"]),
    port=st.integers(min_value=1024, max_value=65535),
    tab=st.sampled_from(["graph", "kanban", "matrix", "gantt", None]),
)
def test_property_entity_deep_link_structure(entity_num: int, host: str, port: int, tab: str | None):
    """Assert deep links always preserve host, port, uppercase entity, and valid hash."""
    entity_str = f"task-{entity_num:04d}"
    url = generate_entity_deep_link(entity_str, host=host, port=port, tab=tab)

    expected_base = f"http://{host}:{port}/"
    assert url.startswith(expected_base)

    norm_id = normalize_entity_id(entity_str)
    assert norm_id == f"TASK-{entity_num:04d}"
    assert f"entity={norm_id}" in url

    if tab and tab != "graph":
        assert f"#tab={tab}&entity={norm_id}" in url
    else:
        assert f"#entity={norm_id}" in url
