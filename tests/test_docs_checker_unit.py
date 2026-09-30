"""Unit tests for src/spec_ops/docs/checker.py to maximize mutant kill rate under mutmut."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

from spec_ops.docs.checker import (
    check_docs_drift,
    evaluate_cli_drift,
    is_command_documented,
    load_diataxis_texts,
    run_docs_check,
)


def test_is_command_documented():
    assert is_command_documented("", ["some doc"]) is True
    assert is_command_documented("   ", ["some doc"]) is True
    assert is_command_documented("spec-ops init", ["# SpecOps\nRun `spec-ops init` to start."]) is True
    assert is_command_documented("spec-ops init", ["# SpecOps\nRun other command."]) is False
    assert is_command_documented("spec-ops init", []) is False
    assert is_command_documented("spec-ops task archive", ["doc 1", "see spec-ops task archive here"]) is True


def test_evaluate_cli_drift():
    assert evaluate_cli_drift([], ["any text"]) == []
    assert evaluate_cli_drift(["cmd-a", "cmd-b"], ["cmd-a", "cmd-b"]) == []

    # Returns sorted list
    res = evaluate_cli_drift(["cmd-z", "cmd-a", "cmd-m"], ["cmd-m"])
    assert res == ["cmd-a", "cmd-z"]

    res_all = evaluate_cli_drift(["cmd-b", "cmd-a"], [])
    assert res_all == ["cmd-a", "cmd-b"]


def test_load_diataxis_texts(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    # When dirs do not exist
    assert load_diataxis_texts(docs_dir) == []

    # Create how-to and reference with markdown files
    (docs_dir / "how-to").mkdir(parents=True)
    (docs_dir / "reference").mkdir(parents=True)

    (docs_dir / "how-to" / "guide2.md").write_text("guide two", encoding="utf-8")
    (docs_dir / "how-to" / "guide1.md").write_text("guide one", encoding="utf-8")
    (docs_dir / "reference" / "ref1.md").write_text("ref one", encoding="utf-8")
    (docs_dir / "reference" / "other.txt").write_text("ignore", encoding="utf-8")

    texts = load_diataxis_texts(docs_dir)
    assert len(texts) == 3
    assert "guide one" in texts
    assert "guide two" in texts
    assert "ref one" in texts
    assert "ignore" not in texts


def test_check_docs_drift_clean(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "reference").mkdir(parents=True)
    (docs_dir / "reference" / "cli.md").write_text("spec-ops custom-cmd\n", encoding="utf-8")

    parser = argparse.ArgumentParser(prog="spec-ops")
    subs = parser.add_subparsers(dest="command")
    subs.add_parser("custom-cmd")

    code, msgs = check_docs_drift(docs_dir, parser=parser)
    assert code == 0
    assert msgs == ["All public interfaces and CLI commands are documented."]


def test_check_docs_drift_detected(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "reference").mkdir(parents=True)
    (docs_dir / "reference" / "cli.md").write_text("empty\n", encoding="utf-8")

    parser = argparse.ArgumentParser(prog="spec-ops")
    subs = parser.add_subparsers(dest="command")
    subs.add_parser("missing-cmd")

    code, msgs = check_docs_drift(docs_dir, parser=parser)
    assert code == 1
    assert msgs == ["Documentation Drift Detected: Public CLI command 'spec-ops missing-cmd' is not documented."]


def test_check_docs_drift_default_parser(tmp_path: Path):
    real_docs = Path.cwd() / "docs"
    code, msgs = check_docs_drift(real_docs)
    assert code == 0
    assert msgs == ["All public interfaces and CLI commands are documented."]


def test_run_docs_check(tmp_path: Path, capsys):
    docs_dir = tmp_path / "docs"
    (docs_dir / "reference").mkdir(parents=True)
    (docs_dir / "reference" / "cli.md").write_text("spec-ops test-cmd\n", encoding="utf-8")

    parser = argparse.ArgumentParser(prog="spec-ops")
    subs = parser.add_subparsers(dest="command")
    subs.add_parser("test-cmd")

    code = run_docs_check(docs_dir, parser=parser)
    captured = capsys.readouterr()
    assert code == 0
    assert "All public interfaces and CLI commands are documented." in captured.out
