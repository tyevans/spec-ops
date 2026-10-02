"""Code snippet syntax and CLI execution validator for documentation."""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import re
import shlex
import subprocess
from pathlib import Path

from .models import AuditViolation


def _validate_bash_cli_invocations(
    code: str,
    md_path: Path,
    docs_dir: Path,
    parser: argparse.ArgumentParser,
    violations: list[AuditViolation],
) -> None:
    for line in code.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        commands = re.split(r"&&|\|\||;|\|", line)
        for cmd_raw in commands:
            cmd = cmd_raw.strip()
            if "spec-ops" not in cmd:
                continue

            sanitized_cmd = re.sub(r"<[^>]+>", "DUMMY_ARG", cmd)
            sanitized_cmd = re.sub(r"\{[^}]+\}", "DUMMY_ARG", sanitized_cmd)

            try:
                tokens = shlex.split(sanitized_cmd)
            except ValueError:
                continue

            if "spec-ops" in tokens:
                idx = tokens.index("spec-ops")
                cli_args = tokens[idx + 1 :]

                normalized_args: list[str] = []
                for arg in cli_args:
                    if arg.startswith("<") and arg.endswith(">"):
                        normalized_args.append("DUMMY_ID")
                    elif arg.startswith("{") and arg.endswith("}"):
                        continue
                    else:
                        normalized_args.append(arg)

                with contextlib.redirect_stderr(io.StringIO()):
                    try:
                        _, unknown = parser.parse_known_args(normalized_args)
                        unknown_flags = [u for u in unknown if u.startswith("-")]
                        if unknown_flags:
                            violations.append(
                                AuditViolation(
                                    category="snippet",
                                    file_path=md_path,
                                    message=(
                                        f"Unrecognized CLI flag(s) in {md_path.relative_to(docs_dir)}: "
                                        f"{unknown_flags} (command: '{cmd}')"
                                    ),
                                    severity="error",
                                )
                            )
                    except SystemExit:
                        violations.append(
                            AuditViolation(
                                category="snippet",
                                file_path=md_path,
                                message=f"Invalid CLI command syntax in {md_path.relative_to(docs_dir)}: '{cmd}'",
                                severity="error",
                            )
                        )


def check_code_snippets(
    docs_dir: Path, parser: argparse.ArgumentParser | None = None
) -> tuple[list[AuditViolation], int]:
    """Validates syntax and CLI invocation correctness in documentation code blocks."""
    violations: list[AuditViolation] = []
    snippet_count = 0

    extra_dirs: set[str] = set()
    current = docs_dir.resolve()
    toml_path: Path | None = None
    while current.parent != current:
        candidate = current / "specops.toml"
        if candidate.is_file():
            toml_path = candidate
            break
        current = current.parent

    if toml_path and toml_path.is_file():
        try:
            import sys
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib  # type: ignore
            with toml_path.open("rb") as f:
                tdata = tomllib.load(f)
            doc_cfg = tdata.get("documentation", {})
            extra_dirs = (
                set(doc_cfg.get("allowed_directories", []))
                | set(doc_cfg.get("ignored_directories", []))
                | set(doc_cfg.get("ignored_dirs", []))
            )
        except Exception:
            pass

    for md_path in sorted(docs_dir.rglob("*.md")):
        rel = md_path.relative_to(docs_dir)
        if any(part.startswith(".") for part in rel.parts) or (rel.parts and rel.parts[0] in ("project", *extra_dirs)):
            continue

        content = md_path.read_text(encoding="utf-8", errors="replace")
        blocks = re.findall(r"```([a-zA-Z0-9_-]*)\n(.*?)```", content, flags=re.DOTALL)

        for lang, code in blocks:
            clean_lang = lang.strip().lower()

            if clean_lang in ("python", "py", "python3"):
                snippet_count += 1
                try:
                    import textwrap
                    ast.parse(textwrap.dedent(code), filename=str(md_path))
                except SyntaxError as e:
                    violations.append(
                        AuditViolation(
                            category="snippet",
                            file_path=md_path,
                            message=f"Python syntax error in {md_path.relative_to(docs_dir)} (line {e.lineno}): {e.msg}",
                            severity="error",
                        )
                    )

            elif clean_lang in ("bash", "sh", "shell", "zsh"):
                snippet_count += 1
                sanitized_bash = re.sub(r"<[^>\n]+>", "dummy_placeholder", code)
                sanitized_bash = re.sub(r"\{[^}\n]+\}", "dummy_placeholder", sanitized_bash)
                try:
                    import textwrap
                    res = subprocess.run(
                        ["bash", "-n", "-c", textwrap.dedent(sanitized_bash)],
                        capture_output=True,
                        text=True,
                    )
                    if res.returncode != 0:
                        err_msg = res.stderr.strip() or "Syntax error in bash snippet"
                        violations.append(
                            AuditViolation(
                                category="snippet",
                                file_path=md_path,
                                message=f"Bash syntax error in {md_path.relative_to(docs_dir)}: {err_msg}",
                                severity="error",
                            )
                        )
                except FileNotFoundError:
                    pass

                if parser is not None:
                    _validate_bash_cli_invocations(code, md_path, docs_dir, parser, violations)

    return violations, snippet_count
