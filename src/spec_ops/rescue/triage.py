"""Interactive preserved worktree failure triage and diagnostic takeover."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..backlog.queue import BacklogQueue, write_task_file
from ..config.models import SpecOpsConfig
from ..worker.ast_analyzer import extract_top_level_nodes
from .lifecycle import create_worktree, init_worktree_environment

CATEGORY_FILE_LENGTH = "File Length Invariant"
CATEGORY_TEST_SUITE = "Test Suite"
CATEGORY_LOCKFILE = "Lockfile Integrity"
CATEGORY_WORKING_TREE = "Working Tree State"
CATEGORY_SYNTAX_DEFECT = "Syntax Defect"
CATEGORY_GENERAL = "General Diagnostic"

ALL_CATEGORIES = {
    CATEGORY_FILE_LENGTH,
    CATEGORY_TEST_SUITE,
    CATEGORY_LOCKFILE,
    CATEGORY_WORKING_TREE,
    CATEGORY_SYNTAX_DEFECT,
    CATEGORY_GENERAL,
}


@dataclass
class TriageFinding:
    category: str
    status: str
    details: str
    line_number: int | None = None
    file_path: str | None = None


@dataclass
class FileDiffMetric:
    file_path: str
    head_lines: int
    current_lines: int
    net_delta: int
    headroom: int
    headroom_status: str
    ast_diff_summary: str = ""
    diff_text: str = ""


def classify_log_snippet(snippet: str) -> str:
    """Classifies any arbitrary log string into the recognized failure taxonomy."""
    text = snippet.lower()
    if re.search(r"lines\s*>\s*\d+\s*limit|file length limit|exceeds file length", text):
        return CATEGORY_FILE_LENGTH
    if re.search(r"syntaxerror|indentationerror|ast parse error|invalid syntax", text):
        return CATEGORY_SYNTAX_DEFECT
    if re.search(r"assertionerror|failed|def test_|::test_|pytest", text):
        return CATEGORY_TEST_SUITE
    if re.search(r"uv\.lock|lockfile", text):
        return CATEGORY_LOCKFILE
    if re.search(r"modified file|untracked file|working tree", text):
        return CATEGORY_WORKING_TREE
    return CATEGORY_GENERAL


def parse_feedback_diagnostics(log_text: str) -> list[TriageFinding]:
    """Parses preflight failure log output into structured findings."""
    findings: list[TriageFinding] = []
    last_file: str | None = None
    last_line: int | None = None

    for line in log_text.splitlines():
        clean = line.strip()
        m_file = re.search(r'File "([^"]+)", line (\d+)', clean)
        if m_file:
            last_file = m_file.group(1)
            last_line = int(m_file.group(2))

        fl = re.search(r"([a-zA-Z0-9_\-\./]+\.py)[\s:]*\(?(\d+)\s+lines\s*>\s*(\d+)\s*limit\)?", clean)
        if fl:
            findings.append(TriageFinding(CATEGORY_FILE_LENGTH, "FAIL", f"{fl.group(1)} ({fl.group(2)} lines > {fl.group(3)} limit)", file_path=fl.group(1)))
            continue

        st = re.search(r'(?:([a-zA-Z0-9_\-\./]+\.py):(\d+)[:\s]+)?(SyntaxError|IndentationError):\s*(.+)', clean)
        if st:
            fp = st.group(1) or last_file or "unknown.py"
            ln = int(st.group(2)) if st.group(2) else (last_line or 1)
            findings.append(TriageFinding(CATEGORY_SYNTAX_DEFECT, "FAIL", f"{fp}:{ln} ({st.group(4).strip()})", line_number=ln, file_path=fp))
            continue

        ts = re.search(r"(?:FAILED\s+)?(tests/[^\s:]+::\w+)\s*(?:[-:]\s*\(?(\w+)\)?)?", clean)
        if ts and not any(f.category == CATEGORY_TEST_SUITE for f in findings):
            findings.append(TriageFinding(CATEGORY_TEST_SUITE, "FAIL", f"{ts.group(1)} ({ts.group(2) or 'AssertionError'})"))
    return findings


def analyze_worktree(worktree_dir: Path, feedback_text: str = "") -> list[TriageFinding]:
    """Examines worktree disk state and preflight feedback to produce full diagnostic findings."""
    parsed = parse_feedback_diagnostics(feedback_text)
    findings: list[TriageFinding] = []

    # 1. File Length Invariant
    fl_findings = [p for p in parsed if p.category == CATEGORY_FILE_LENGTH]
    if fl_findings:
        findings.extend(fl_findings)
    else:
        violating: list[tuple[str, int]] = []
        if worktree_dir.exists():
            for p in worktree_dir.rglob("*.py"):
                if not any(part.startswith(".") or part in ("venv", ".venv") for part in p.parts):
                    try:
                        n = len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
                        if n > 500:
                            violating.append((str(p.relative_to(worktree_dir)), n))
                    except OSError:
                        pass
        if violating:
            for rel, count in violating:
                findings.append(TriageFinding(CATEGORY_FILE_LENGTH, "FAIL", f"{rel} ({count} lines > 500 limit)", file_path=rel))
        else:
            findings.append(TriageFinding(CATEGORY_FILE_LENGTH, "PASS", "all files compliant (<500 lines)"))

    # 2. Test Suite
    ts_findings = [p for p in parsed if p.category == CATEGORY_TEST_SUITE]
    if ts_findings:
        findings.extend(ts_findings)
    else:
        status_pass = bool(re.search(r"passed|100%|test suite ok", feedback_text.lower())) or not bool(
            re.search(r"pytest|assertionerror|test failure", feedback_text.lower())
        )
        findings.append(TriageFinding(CATEGORY_TEST_SUITE, "PASS" if status_pass else "FAIL", "all tests passing" if status_pass else "test failures detected"))

    # 3. Lockfile Integrity
    lock_fail = bool(re.search(r"uv\.lock\s*(drift|out of sync|mismatch)", feedback_text.lower()))
    findings.append(TriageFinding(CATEGORY_LOCKFILE, "FAIL" if lock_fail else "PASS", "uv.lock drift detected" if lock_fail else "uv.lock synchronized"))

    # 4. Working Tree State
    if worktree_dir.exists():
        st = subprocess.run(["git", "status", "--porcelain"], cwd=worktree_dir, capture_output=True, text=True)
        st_lines = [l for l in st.stdout.splitlines() if l.strip()]
        mods = [l for l in st_lines if not l.startswith("??")]
        untracked = [l for l in st_lines if l.startswith("??")]
        if mods or untracked:
            parts = []
            if mods:
                parts.append(f"{len(mods)} modified {'file' if len(mods) == 1 else 'files'}")
            if untracked:
                parts.append(f"{len(untracked)} untracked {'file' if len(untracked) == 1 else 'files'}")
            findings.append(TriageFinding(CATEGORY_WORKING_TREE, "DIRTY", ", ".join(parts)))
        else:
            findings.append(TriageFinding(CATEGORY_WORKING_TREE, "CLEAN", "working tree clean"))
    else:
        findings.append(TriageFinding(CATEGORY_WORKING_TREE, "CLEAN", "worktree not found"))

    return findings


def format_triage_table(findings: list[TriageFinding]) -> str:
    """Renders formatted Markdown diagnostic table with Category, Status, and Details."""
    c_w = max(max(len(f.category) for f in findings), len("Category"))
    s_w = max(max(len(f.status) for f in findings), len("Status"))
    d_w = max(max(len(f.details) for f in findings), len("Details"))
    rows = [
        f"| {'Category':<{c_w}} | {'Status':<{s_w}} | {'Details':<{d_w}} |",
        f"| {'-' * c_w} | {'-' * s_w} | {'-' * d_w} |",
    ]
    for f in findings:
        rows.append(f"| {f.category:<{c_w}} | {f.status:<{s_w}} | {f.details:<{d_w}} |")
    return "\n".join(rows)


def get_targeted_recommendation(findings: list[TriageFinding], task_id: str) -> str:
    """Formulates clear action recommendations based on triage classification."""
    fl_fails = [f for f in findings if f.category == CATEGORY_FILE_LENGTH and f.status == "FAIL"]
    ts_fails = [f for f in findings if f.category == CATEGORY_TEST_SUITE and f.status == "FAIL"]
    if fl_fails and not ts_fails:
        fname = Path(fl_fails[0].file_path or "source.py").name
        return (
            f"Recommendation: Code passes tests but violates file limits. "
            f"Run 'spec-ops rescue shell {task_id}' to decompose {fname}, "
            f"then 'spec-ops rescue {task_id} --complete'."
        )
    if ts_fails:
        return f"Recommendation: Test failures detected. Run 'spec-ops rescue shell {task_id}' to fix tests, then 'spec-ops rescue {task_id} --complete'."
    return f"Recommendation: Review diagnostics. Run 'spec-ops rescue shell {task_id}' to inspect, then 'spec-ops rescue {task_id} --complete'."


def calculate_file_diff(worktree_dir: Path, rel_file_path: str) -> FileDiffMetric:
    """Calculates line delta, invariant limit headroom, and AST structural diff against HEAD."""
    clean_rel = rel_file_path.strip().removeprefix("./")
    target_path = worktree_dir / clean_rel

    curr_text = target_path.read_text(encoding="utf-8", errors="ignore") if target_path.exists() else ""
    curr_lines = len(curr_text.splitlines()) if curr_text else 0

    head_res = subprocess.run(["git", "show", f"HEAD:{clean_rel}"], cwd=worktree_dir, capture_output=True, text=True)
    head_text = head_res.stdout if head_res.returncode == 0 else ""
    head_lines = len(head_text.splitlines()) if head_text else 0

    net_delta = curr_lines - head_lines
    headroom = 500 - curr_lines
    headroom_status = "VIOLATION" if headroom < 0 else ("WARNING" if headroom <= 100 else "COMPLIANT")

    # AST structural diff
    head_nodes = {n.name: n for n in extract_top_level_nodes(head_text)}
    curr_nodes = {n.name: n for n in extract_top_level_nodes(curr_text)}
    ast_lines: list[str] = []
    for name, c_node in curr_nodes.items():
        if name not in head_nodes:
            ast_lines.append(f"  + [{c_node.display_kind}] {name} (lines {c_node.lineno}-{c_node.end_lineno})")
        else:
            delta = c_node.line_count - head_nodes[name].line_count
            if delta != 0:
                ast_lines.append(f"  ~ [{c_node.display_kind}] {name} (lines {c_node.lineno}-{c_node.end_lineno}, {delta:+d} lines)")
    for name, h_node in head_nodes.items():
        if name not in curr_nodes:
            ast_lines.append(f"  - [{h_node.display_kind}] {name}")

    diff_res = subprocess.run(["git", "diff", "HEAD", "--", clean_rel], cwd=worktree_dir, capture_output=True, text=True)
    return FileDiffMetric(
        file_path=clean_rel,
        head_lines=head_lines,
        current_lines=curr_lines,
        net_delta=net_delta,
        headroom=headroom,
        headroom_status=headroom_status,
        ast_diff_summary="\n".join(ast_lines) if ast_lines else "  No structural symbol changes.",
        diff_text=diff_res.stdout if diff_res.returncode == 0 else "",
    )


def takeover_task(config: SpecOpsConfig, task_id_input: str, claimant: str = "") -> tuple[bool, str]:
    """Transfers task claim to human developer and provisions the worktree."""
    clean_num = task_id_input.upper().replace("TASK-", "").lstrip("0")
    tid_num = clean_num.zfill(4) if clean_num else "0000"
    canonical_id = f"TASK-{tid_num}"

    queue = BacklogQueue(config.backlog_dir)
    target_task = next((t for t in queue.list_all_tasks() if t.canonical_id == canonical_id), None)
    if not target_task:
        return False, f"Task {canonical_id} not found in backlog."

    human_claimant = claimant or os.environ.get("SPECOPS_CLAIMANT") or "riley"
    target_task.claimed_by = human_claimant
    write_task_file(target_task)

    worktree_dir = config.root_dir / ".worktrees" / f"task-{tid_num}"
    branch = f"feat/{canonical_id}"
    if not worktree_dir.exists():
        create_worktree(config.root_dir, branch=branch, worktree_dir=worktree_dir)
    init_worktree_environment(config.root_dir, worktree_dir)

    msg = (
        f"✅ Task {canonical_id} claim transferred to human developer: {human_claimant}\n"
        f"Worktree location: .worktrees/task-{tid_num} on branch {branch}\n\n"
        f"Instructions:\n"
        f"👉 1. Enter the worktree: cd .worktrees/task-{tid_num}\n"
        f"👉 2. Make your edits and verify preflight: uv run pytest\n"
        f"👉 3. Finish and squash-merge: spec-ops rescue {canonical_id} --complete"
    )
    return True, msg
