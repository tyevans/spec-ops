"""Living Diataxis documentation drift checker."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

_DEFAULT_PARSER_FACTORY: Callable[[], argparse.ArgumentParser] | None = None


def register_default_parser_factory(
    factory: Callable[[], argparse.ArgumentParser] | None,
) -> None:
    """Registers a parser factory to avoid docs depending on cli (ADR-0021)."""
    global _DEFAULT_PARSER_FACTORY
    _DEFAULT_PARSER_FACTORY = factory


def is_command_documented(command: str, doc_texts: list[str]) -> bool:
    """Checks whether a command string is documented in any of the provided doc texts."""
    target = command.strip()
    if not target:
        return True
    return any(target in text for text in doc_texts)


def evaluate_cli_drift(
    commands: list[str],
    doc_texts: list[str],
) -> list[str]:
    """Evaluates a list of CLI commands against documented texts and returns undocumented commands."""
    undocumented = []
    for cmd in commands:
        if not is_command_documented(cmd, doc_texts):
            undocumented.append(cmd)
    return sorted(undocumented)


def load_diataxis_texts(docs_dir: Path) -> list[str]:
    """Loads text from markdown files in docs/how-to/ and docs/reference/."""
    texts: list[str] = []
    for quadrant in ("how-to", "reference"):
        quad_dir = docs_dir / quadrant
        if quad_dir.is_dir():
            for md_file in sorted(quad_dir.glob("*.md")):
                try:
                    texts.append(md_file.read_text(encoding="utf-8"))
                except OSError:
                    pass
    return texts


def check_docs_drift(
    docs_dir: Path,
    parser: argparse.ArgumentParser | None = None,
) -> tuple[int, list[str]]:
    """Audits public CLI commands against docs/how-to/ and docs/reference/.

    Returns (exit_code, alert_messages).
    """
    if parser is None:
        if _DEFAULT_PARSER_FACTORY is not None:
            parser = _DEFAULT_PARSER_FACTORY()
        else:
            try:
                import importlib

                mod = importlib.import_module("spec_ops.cli.parser")
                parser = mod.build_parser()
            except Exception:
                raise ValueError(
                    "An ArgumentParser instance must be provided via dependency injection (ADR-0021)."
                )

    from .cli_inspector import extract_parser_commands

    parser_cmds = extract_parser_commands(parser)
    cmd_list = sorted(parser_cmds.keys())
    doc_texts = load_diataxis_texts(docs_dir)

    undocumented = evaluate_cli_drift(cmd_list, doc_texts)
    if undocumented:
        messages = [
            f"Documentation Drift Detected: Public CLI command '{cmd}' is not documented."
            for cmd in undocumented
        ]
        return 1, messages

    return 0, ["All public interfaces and CLI commands are documented."]


def run_docs_check(
    docs_dir: Path,
    parser: argparse.ArgumentParser | None = None,
) -> int:
    """CLI runner for docs check subcommand."""
    exit_code, messages = check_docs_drift(docs_dir, parser=parser)
    for msg in messages:
        print(msg)
    return exit_code
