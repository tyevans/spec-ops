"""CLI documentation drift inspector for SpecOps."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from .models import AuditViolation, ParsedCLICommand


def extract_parser_commands(
    parser: argparse.ArgumentParser, prefix: str = "spec-ops"
) -> dict[str, ParsedCLICommand]:
    """Recursively introspects an ArgumentParser into canonical command names and options."""
    commands: dict[str, ParsedCLICommand] = {}
    subactions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]

    if not subactions:
        options: set[str] = set()
        positionals: list[str] = []
        for a in parser._actions:
            if a.dest == "help" or any(opt in ("-h", "--help") for opt in a.option_strings):
                continue
            if a.option_strings:
                for opt in a.option_strings:
                    options.add(opt)
            elif not isinstance(a, argparse._SubParsersAction):
                positionals.append(a.dest)
        commands[prefix] = ParsedCLICommand(command=prefix, options=options, positionals=positionals)
        return commands

    # If this parser has its own options and is not the root parser, record it
    own_options: set[str] = set()
    own_positionals: list[str] = []
    for a in parser._actions:
        if a.dest == "help" or any(opt in ("-h", "--help") for opt in a.option_strings):
            continue
        if a.option_strings:
            for opt in a.option_strings:
                own_options.add(opt)
        elif not isinstance(a, argparse._SubParsersAction):
            own_positionals.append(a.dest)

    if own_options and prefix != "spec-ops":
        commands[prefix] = ParsedCLICommand(command=prefix, options=own_options, positionals=own_positionals)

    seen_subparsers: set[Any] = set()
    for subact in subactions:
        for name, subp in subact.choices.items():
            if subp in seen_subparsers:
                continue
            seen_subparsers.add(subp)
            full_name = f"{prefix} {name}"
            commands.update(extract_parser_commands(subp, full_name))

    return commands


def extract_doc_commands(cli_md_path: Path) -> dict[str, ParsedCLICommand]:
    """Parses documented commands and CLI options from docs/reference/cli.md."""
    if not cli_md_path.exists():
        return {}

    content = cli_md_path.read_text(encoding="utf-8")
    doc_cmds: dict[str, ParsedCLICommand] = {}

    for line in content.splitlines():
        stripped = line.strip()
        # 1. Parse markdown tables (| `spec-ops ...` | ... |)
        if stripped.startswith("|") and stripped.endswith("|"):
            parts = [p.strip() for p in stripped.strip("|").split("|")]
            if len(parts) >= 2 and "spec-ops" in parts[0]:
                m = re.search(r"`?(spec-ops[^`|]+)`?", parts[0])
                if m:
                    cmd_name = m.group(1).strip()
                    args_text = parts[1]
                    opts = set(re.findall(r"--[a-zA-Z0-9_-]+", args_text))
                    doc_cmds[cmd_name] = ParsedCLICommand(command=cmd_name, options=opts)
        # 2. Parse markdown lists (- `spec-ops ...`: ...)
        else:
            m_list = re.match(r"^[-*]\s+`?(spec-ops\s+[^`:]+)`?:\s*(.*)$", stripped)
            if m_list:
                cmd_name = m_list.group(1).strip()
                rest = m_list.group(2)
                if cmd_name not in doc_cmds:
                    opts = set(re.findall(r"--[a-zA-Z0-9_-]+", rest))
                    doc_cmds[cmd_name] = ParsedCLICommand(command=cmd_name, options=opts)

    return doc_cmds


def check_cli_drift(
    docs_dir: Path, parser: argparse.ArgumentParser
) -> tuple[list[AuditViolation], int]:
    """Compares docs/reference/cli.md against actual CLI parser definitions."""
    violations: list[AuditViolation] = []
    cli_md_path = docs_dir / "reference" / "cli.md"

    if not cli_md_path.exists():
        violations.append(
            AuditViolation(
                category="cli_drift",
                file_path=cli_md_path,
                message="CLI reference documentation missing: docs/reference/cli.md",
                severity="error",
            )
        )
        return violations, 0

    parser_cmds = extract_parser_commands(parser)
    doc_cmds = extract_doc_commands(cli_md_path)

    # Flag missing commands (in CLI parser but absent from docs)
    for cmd_name in sorted(parser_cmds.keys()):
        if cmd_name not in doc_cmds:
            violations.append(
                AuditViolation(
                    category="cli_drift",
                    file_path=cli_md_path,
                    message=f"Command '{cmd_name}' is implemented in CLI but missing from docs/reference/cli.md",
                    severity="error",
                )
            )

    # Flag extra commands (in docs but absent from CLI parser)
    for cmd_name in sorted(doc_cmds.keys()):
        if cmd_name not in parser_cmds:
            violations.append(
                AuditViolation(
                    category="cli_drift",
                    file_path=cli_md_path,
                    message=f"Command '{cmd_name}' is documented in docs/reference/cli.md but does not exist in CLI",
                    severity="error",
                )
            )

    # Verify option flags for mutual commands
    for cmd_name in sorted(set(parser_cmds.keys()) & set(doc_cmds.keys())):
        p_opts = parser_cmds[cmd_name].options
        d_opts = doc_cmds[cmd_name].options

        missing_opts: set[str] = set()
        for opt in p_opts:
            if opt not in d_opts:
                # Handle synonyms (e.g. --agent and --agents, concurrency aliases)
                if opt == "--agents" and "--agent" in d_opts:
                    continue
                if opt == "--agent" and "--agents" in d_opts:
                    continue
                if opt in ("--max-workers", "--concurrency", "--max-concurrency") and (
                    {"--max-workers", "--concurrency", "--max-concurrency"} & d_opts
                ):
                    continue
                if opt.startswith("-") and not opt.startswith("--"):
                    continue
                missing_opts.add(opt)

        extra_opts = d_opts - p_opts

        if missing_opts:
            violations.append(
                AuditViolation(
                    category="cli_drift",
                    file_path=cli_md_path,
                    message=(
                        f"Command '{cmd_name}' in docs/reference/cli.md missing option(s): "
                        f"{', '.join(sorted(missing_opts))}"
                    ),
                    severity="error",
                )
            )
        if extra_opts:
            violations.append(
                AuditViolation(
                    category="cli_drift",
                    file_path=cli_md_path,
                    message=(
                        f"Command '{cmd_name}' in docs/reference/cli.md documents non-existent option(s): "
                        f"{', '.join(sorted(extra_opts))}"
                    ),
                    severity="error",
                )
            )

    return violations, len(parser_cmds)
