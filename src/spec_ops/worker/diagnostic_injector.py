"""Targeted AST diagnostic injector for in-worktree preflight recovery and self-healing (PRD-0004, ADR-0004)."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DiagnosticCard:
    """Structured diagnostic telemetry card for preflight and invariant failures."""

    file_path: str
    line_number: int | None
    node_type: str
    node_name: str | None
    source_snippet: str | None
    failure_category: str  # "assertion_error", "file_limit_violation", "syntax_error", "unknown"
    breached_rule: str | None  # "ADR-0002", "ADR-0003", etc.
    actionable_guidance: str

    def to_dict(self) -> dict[str, Any]:
        """Converts card to a JSON-serializable dictionary."""
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "node_type": self.node_type,
            "node_name": self.node_name,
            "source_snippet": self.source_snippet,
            "failure_category": self.failure_category,
            "breached_rule": self.breached_rule,
            "actionable_guidance": self.actionable_guidance,
        }


def resolve_source_file(file_path: str, repo_root: Path | None = None) -> tuple[Path | None, str | None]:
    """Resolves file path and reads its content safely without throwing."""
    p = Path(file_path)
    candidates = [repo_root / file_path, repo_root / p.name, p] if repo_root else [p]
    for cand in candidates:
        if cand.is_file():
            try:
                return cand, cand.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
    return None, None


def find_containing_ast_node(source_code: str, line_number: int) -> tuple[str, str | None, str | None]:
    """Identifies the containing AST node and extracts snippet for line_number."""
    if not source_code:
        return "unknown", None, None
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        lines = source_code.splitlines()
        snip = lines[line_number - 1] if 1 <= line_number <= len(lines) else None
        return "SyntaxError", None, snip
    except Exception:
        return "unknown", None, None

    lines = source_code.splitlines()
    c_func, c_cls, c_stmt = None, None, None

    def span(n: Any) -> int:
        return (getattr(n, "end_lineno", n.lineno) or n.lineno) - n.lineno

    for node in ast.walk(tree):
        if not hasattr(node, "lineno"):
            continue
        start, end = node.lineno, getattr(node, "end_lineno", node.lineno) or node.lineno
        if start <= line_number <= end:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if c_func is None or span(node) <= span(c_func):
                    c_func = node
            elif isinstance(node, ast.ClassDef):
                if c_cls is None or span(node) <= span(c_cls):
                    c_cls = node
            elif isinstance(node, ast.stmt):
                if c_stmt is None or span(node) <= span(c_stmt):
                    c_stmt = node

    chosen = c_func or c_cls or c_stmt or tree
    name = getattr(chosen, "name", None)
    snip = None
    if chosen is not tree and hasattr(chosen, "lineno"):
        s = max(0, chosen.lineno - 1)
        e = min(len(lines), getattr(chosen, "end_lineno", chosen.lineno) or chosen.lineno)
        snip = "\n".join(lines[s:e])
    elif 1 <= line_number <= len(lines):
        snip = lines[line_number - 1]

    return type(chosen).__name__, name, snip


def _parse_file_length_violations(output: str, repo_root: Path | None) -> list[DiagnosticCard]:
    cards: list[DiagnosticCard] = []
    markers = ("file length violation", "file length limit", "lines >", "exceeds length limit", "adr-0002")
    for line in output.splitlines():
        if any(m in line.lower() for m in markers):
            m_path = re.search(r"([a-zA-Z0-9_./\\-]+\.py)", line)
            if not m_path:
                continue
            fpath = m_path.group(1).lstrip("./")
            m_lines = re.search(r"(\d+)\s*lines", line, re.IGNORECASE)
            tot = int(m_lines.group(1)) if m_lines else None
            _, src = resolve_source_file(fpath, repo_root)
            if src:
                from .ast_analyzer import extract_top_level_nodes, find_largest_node

                nodes = extract_top_level_nodes(src)
                largest = find_largest_node(nodes)
                if largest:
                    sc = src.splitlines()
                    cards.append(DiagnosticCard(
                        file_path=fpath,
                        line_number=largest.lineno,
                        node_type="ClassDef" if largest.kind == "class" else "FunctionDef",
                        node_name=largest.name,
                        source_snippet="\n".join(sc[max(0, largest.lineno - 1) : min(len(sc), largest.lineno + 6)]),
                        failure_category="file_limit_violation",
                        breached_rule="ADR-0002",
                        actionable_guidance=(
                            f"File '{fpath}' ({tot or len(sc)} lines) exceeds file length limit (ADR-0002). "
                            f"Suggested seam: extract {largest.display_kind} '{largest.name}' "
                            f"(lines {largest.lineno}-{largest.end_lineno}, {largest.line_count} lines) into separate module."
                        ),
                    ))
                    continue
            cards.append(DiagnosticCard(
                file_path=fpath,
                line_number=None,
                node_type="Module",
                node_name=None,
                source_snippet=None,
                failure_category="file_limit_violation",
                breached_rule="ADR-0002",
                actionable_guidance=f"File '{fpath}' exceeds file length limit (ADR-0002). Decompose module into focused files.",
            ))
    return cards


def _parse_syntax_errors(output: str, repo_root: Path | None) -> list[DiagnosticCard]:
    cards: list[DiagnosticCard] = []
    if "SyntaxError" not in output:
        return cards
    matches = list(re.finditer(r'File ["\']([^"\']+\.py)["\'], line (\d+)(?:[^\n]*\n)*?\s*SyntaxError:\s*([^\n]+)', output))
    matches += list(re.finditer(r'SyntaxError:\s*([^\n]+)\s*\(([^,\s]+\.py),\s*line\s*(\d+)\)', output))
    for m in matches:
        if len(m.groups()) == 3 and m.group(1).endswith(".py"):
            fpath, lno, msg = m.group(1).lstrip("./"), int(m.group(2)), m.group(3).strip()
        else:
            msg, fpath, lno = m.group(1).strip(), m.group(2).lstrip("./"), int(m.group(3))
        _, src = resolve_source_file(fpath, repo_root)
        ntype, nname, snip = find_containing_ast_node(src or "", lno)
        cards.append(DiagnosticCard(
            file_path=fpath,
            line_number=lno,
            node_type=ntype if ntype not in ("unknown", "Module") else "SyntaxError",
            node_name=nname,
            source_snippet=snip,
            failure_category="syntax_error",
            breached_rule=None,
            actionable_guidance=f"Fix Python syntax error at {fpath}:{lno}: {msg}. Ensure syntax is valid Python.",
        ))
    return cards


def _parse_assertion_errors(output: str, repo_root: Path | None) -> list[DiagnosticCard]:
    cards: list[DiagnosticCard] = []
    if "AssertionError" not in output and "assertion" not in output.lower():
        return cards
    coords: list[tuple[str, int]] = []
    for m in re.finditer(r"([a-zA-Z0-9_./\\-]+\.py):(\d+):\s*AssertionError", output):
        coords.append((m.group(1).lstrip("./"), int(m.group(2))))
    for m in re.finditer(r"([a-zA-Z0-9_./\\-]+\.py):(\d+):\s*in\s+([a-zA-Z0-9_]+)", output):
        coords.append((m.group(1).lstrip("./"), int(m.group(2))))
    for m in re.finditer(r'File ["\']([^"\']+\.py)["\'], line (\d+)', output):
        coords.append((m.group(1).lstrip("./"), int(m.group(2))))
    for m in re.finditer(
        r"(?:AssertionError[^\n]*?line\s+(\d+)[^\n]*?(?:of|in)\s+([a-zA-Z0-9_./\\-]+\.py)|"
        r"reporting an AssertionError at line\s+(\d+)[^\n]*?(?:of\s+)?(?:source file\s+)?([a-zA-Z0-9_./\\-]+\.py)?)",
        output,
        re.IGNORECASE,
    ):
        l_str = m.group(1) or m.group(3)
        f_str = m.group(2) or m.group(4)
        if l_str and f_str:
            coords.append((f_str.lstrip("./"), int(l_str)))
        elif l_str and not f_str:
            m_py = re.search(r"([a-zA-Z0-9_./\\-]+\.py)", output)
            if m_py:
                coords.append((m_py.group(1).lstrip("./"), int(l_str)))

    for fpath, lno in coords:
        _, src = resolve_source_file(fpath, repo_root)
        ntype, nname, snip = find_containing_ast_node(src or "", lno)
        cards.append(DiagnosticCard(
            file_path=fpath,
            line_number=lno,
            node_type=ntype,
            node_name=nname,
            source_snippet=snip,
            failure_category="assertion_error",
            breached_rule="ADR-0003",
            actionable_guidance=(
                f"Assertion error in {nname or fpath} at line {lno}. "
                "Verify public frontdoor contracts and domain invariants under ADR-0003 without introducing mock backdoors."
            ),
        ))
    return cards


def _parse_general_tracebacks(output: str, repo_root: Path | None) -> list[DiagnosticCard]:
    cards: list[DiagnosticCard] = []
    if "Traceback (most recent call last):" not in output:
        return cards
    frames = list(re.finditer(r'File ["\']([^"\']+\.py)["\'], line (\d+)', output))
    if frames:
        lf = frames[-1]
        fpath, lno = lf.group(1).lstrip("./"), int(lf.group(2))
        m_exc = re.search(r"([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception):\s*([^\n]*)", output[lf.end() :])
        exc = m_exc.group(1) if m_exc else "RuntimeError"
        msg = m_exc.group(2) if m_exc else ""
        _, src = resolve_source_file(fpath, repo_root)
        ntype, nname, snip = find_containing_ast_node(src or "", lno)
        is_assert = "Assertion" in exc
        cards.append(DiagnosticCard(
            file_path=fpath,
            line_number=lno,
            node_type=ntype,
            node_name=nname,
            source_snippet=snip,
            failure_category="assertion_error" if is_assert else "runtime_error",
            breached_rule="ADR-0003" if is_assert else None,
            actionable_guidance=f"{exc} in {nname or fpath} at line {lno}: {msg}.",
        ))
    return cards


class DiagnosticInjector:
    """AST-driven failure diagnostic analyzer and retry prompt injector."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root

    def diagnose(self, output: str) -> list[DiagnosticCard]:
        return self.diagnose_failure(output, repo_root=self.repo_root)

    @classmethod
    def diagnose_failure(cls, output: str, repo_root: Path | None = None) -> list[DiagnosticCard]:
        if not output or not output.strip():
            return []
        cards: list[DiagnosticCard] = []
        try:
            cards.extend(_parse_file_length_violations(output, repo_root))
            cards.extend(_parse_syntax_errors(output, repo_root))
            cards.extend(_parse_assertion_errors(output, repo_root))
            if not cards:
                cards.extend(_parse_general_tracebacks(output, repo_root))
        except Exception:
            pass

        seen: set[tuple[str, int | None, str, str | None]] = set()
        deduped: list[DiagnosticCard] = []
        for c in cards:
            key = (c.file_path, c.line_number, c.failure_category, c.node_name)
            if key not in seen:
                seen.add(key)
                deduped.append(c)

        if not deduped and output.strip():
            deduped.append(DiagnosticCard(
                file_path="unknown",
                line_number=None,
                node_type="unknown",
                node_name=None,
                source_snippet=None,
                failure_category="unknown",
                breached_rule=None,
                actionable_guidance="Unrecognized preflight output format. Review raw execution logs and verify test/health assertions.",
            ))
        return deduped

    @classmethod
    def synthesize_retry_prompt(cls, cards: list[DiagnosticCard]) -> str:
        if not cards:
            return ""
        lines: list[str] = [
            "## Preflight Failure Diagnostics & AST Self-Healing Guidance",
            "",
            f"The previous attempt failed preflight checks. Review the following {len(cards)} diagnostic issue(s) and AST node locations to self-heal:",
            "",
        ]
        has_len = any(c.failure_category == "file_limit_violation" for c in cards)
        has_ast = any(c.failure_category == "assertion_error" for c in cards)
        for idx, c in enumerate(cards, start=1):
            lines.append(f"### Issue {idx}: {c.failure_category.replace('_', ' ').title()}")
            lines.append(f"- **Target File**: `{c.file_path}`")
            if c.line_number is not None:
                lines.append(f"- **Line Number**: `{c.line_number}`")
            lines.append(f"- **AST Node**: `{c.node_type}`" + (f" (`{c.node_name}`)" if c.node_name else ""))
            if c.breached_rule:
                lines.append(f"- **Breached Invariant**: `{c.breached_rule}`")
            lines.append(f"- **Actionable Guidance**: {c.actionable_guidance}")
            if c.source_snippet:
                lines.append("- **Source Context**:\n  ```python")
                for s_line in c.source_snippet.splitlines():
                    lines.append(f"  {s_line}")
                lines.append("  ```")
            lines.append("")

        lines.append("## Mandatory Invariant Prohibitions (DO NOT REPEAT)")
        if has_len:
            lines.append("- **ADR-0002 (File Length Limit)**: Source files must remain strictly < 500 lines (proactive warning at >= 400 lines). Decompose oversized modules into single-responsibility files without modifying backlog specifications directly.")
        else:
            lines.append("- **ADR-0002 (File Length Limit)**: All source files must remain strictly under 500 lines.")
        if has_ast:
            lines.append("- **ADR-0003 (Blackbox Frontdoors)**: All verification must exercise public interfaces. Zero private mock backdoors or internal monkey-patching permitted.")
        else:
            lines.append("- **ADR-0003 (Blackbox Frontdoors)**: Verify public interfaces without mock backdoors.")
        lines.append("- **ADR-0005 (Backlog Isolation)**: Multi-agent workers execute in isolated worktrees. Never modify files under `docs/project/backlog/` directly on feature branches.")
        lines.append("- **ADR-0020 (Anti-Loop Invariant)**: Do not repeat flawed implementation strategies or bypass preflight checks.")
        return "\n".join(lines)
