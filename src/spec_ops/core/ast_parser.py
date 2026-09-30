"""Resilient Markdown AST parsing and precision frontmatter diagnostic reporting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class FrontmatterDiagnosticError(Exception):
    """Compiler-grade diagnostic error with precise line and column pointers."""

    file_path: str
    line: int
    column: int
    message: str
    source_snippet: str = ""
    hint: str = ""
    is_missing_delim: bool = False

    def format_error(self) -> str:
        if self.is_missing_delim:
            msg = self.message
            if self.hint:
                return f"{msg}\n{self.hint}"
            return msg
        return (
            f"error: Frontmatter YAML Syntax Error in {self.file_path}:{self.line}:{self.column}\n"
            f"|\n"
            f"{self.line} | {self.source_snippet}\n"
            f"| {' ' * max(0, self.column - 1)}^ {self.message}"
        )

    def __str__(self) -> str:
        return self.format_error()


def parse_markdown_document(
    content: str, file_path: str | Path = ""
) -> tuple[dict[str, Any], str]:
    """Parses a markdown document with YAML frontmatter, preserving markdown AST verbatim.

    Raises FrontmatterDiagnosticError on missing delimiters or malformed YAML.
    """
    str_path = str(file_path)
    if not content.startswith("---"):
        raise FrontmatterDiagnosticError(
            file_path=str_path,
            line=1,
            column=1,
            message="Missing Frontmatter: File does not start with standard YAML '---' delimiter",
            hint="Run 'spec-ops scaffold task' to generate a valid frontmatter template",
            is_missing_delim=True,
        )

    rest = content[3:]
    m = re.search(r"(\r?\n)---\s*(\r?\n|\Z)", rest)
    if not m:
        raise FrontmatterDiagnosticError(
            file_path=str_path,
            line=1,
            column=1,
            message="Missing Frontmatter: Closing '---' delimiter not found",
            is_missing_delim=True,
        )

    yaml_raw = rest[: m.start()]
    body = rest[m.end() :]
    clean_yaml = yaml_raw[1:] if yaml_raw.startswith("\n") else yaml_raw
    lines = clean_yaml.splitlines()
    file_lines = content.splitlines()

    for idx, line in enumerate(lines):
        file_line_num = idx + 2
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent > 0 and ":" in line:
            prev_lines = [l for l in lines[:idx] if l.strip() and not l.strip().startswith("#")]
            if prev_lines:
                prev = prev_lines[-1]
                prev_indent = len(prev) - len(prev.lstrip(" "))
                if prev_indent == 0 and ":" in prev and not prev.strip().endswith((":", "|", ">", "[]", "{}")):
                    src_line = file_lines[file_line_num - 1] if file_line_num <= len(file_lines) else line
                    raise FrontmatterDiagnosticError(
                        file_path=str_path,
                        line=file_line_num,
                        column=indent + 1,
                        message="unexpected mapping indentation",
                        source_snippet=src_line,
                    )

    try:
        data = yaml.safe_load(clean_yaml) or {}
    except yaml.MarkedYAMLError as err:
        line_num = (err.problem_mark.line + 2) if err.problem_mark else 1
        col_num = (err.problem_mark.column + 1) if err.problem_mark else 1
        src_line = file_lines[line_num - 1] if line_num <= len(file_lines) else ""
        raise FrontmatterDiagnosticError(
            file_path=str_path,
            line=line_num,
            column=col_num,
            message=err.problem or "YAML syntax error",
            source_snippet=src_line,
        ) from err
    except yaml.YAMLError as err:
        raise FrontmatterDiagnosticError(
            file_path=str_path, line=1, column=1, message=str(err), source_snippet=""
        ) from err

    if not isinstance(data, dict):
        raise FrontmatterDiagnosticError(
            file_path=str_path,
            line=1,
            column=1,
            message="Invalid frontmatter: expected dictionary mapping",
            source_snippet=file_lines[0] if file_lines else "",
        )

    return data, body
