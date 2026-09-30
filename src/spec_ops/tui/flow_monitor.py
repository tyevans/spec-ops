"""Interactive terminal backlog flow monitor, JIT buffer waterlines, and worktree telemetry."""

from __future__ import annotations

import os
import re
import select
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..backlog.queue import BacklogQueue, write_task_file
from ..config.loader import load_config
from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..worker.claimer import validate_definition_of_ready
from ..worker.worktree import create_worktree


def get_buffer_waterline(refined_count: int, target: int = 10) -> tuple[str, str, str]:
    """Calculates JIT buffer ratio, status color, and display badge."""
    ratio = f"{refined_count}/{target}"
    if refined_count >= 8:
        color_name = "Green"
    elif refined_count >= 5:
        color_name = "Yellow"
    else:
        color_name = "Red"
    badge = f"Buffer: {ratio} [{color_name}]"
    return ratio, color_name, badge


def format_elapsed_time(seconds: float) -> str:
    """Formats duration seconds into human-readable elapsed time string."""
    sec = max(0, int(seconds))
    if sec < 60:
        return f"{sec}s"
    mins = sec // 60
    rem = sec % 60
    return f"{mins}m {rem}s"


@dataclass
class FlowState:
    """Live state for interactive backlog flow monitor."""

    active_column: str = "proposed"
    selected_index: dict[str, int] = field(default_factory=lambda: {"proposed": 0, "refined": 0, "worktrees": 0})
    proposed_tasks: list[Task] = field(default_factory=list)
    refined_tasks: list[Task] = field(default_factory=list)
    completed_count: int = 0
    worktrees: list[dict[str, Any]] = field(default_factory=list)
    buffer_badge: str = "Buffer: 0/10 [Red]"
    buffer_color: str = "Red"
    status_message: str = "Ready (j/k: navigate, h/l/Tab: columns, r: refine, c: claim, q: quit)"


@dataclass
class FlowAction:
    """Discrete user action triggered from keypress."""

    action: str  # "NAVIGATE", "SWITCH_COLUMN", "REFINE", "CLAIM", "QUIT", "NONE"
    target: str = ""
    column: str = ""
    index: int = 0


def handle_flow_key(key: str, state: FlowState) -> FlowAction:
    """Pure keybinding handler mapping keystrokes to flow monitor actions."""
    if not key:
        return FlowAction("NONE")

    if key in ("q", "Q", "\x03"):
        return FlowAction("QUIT")

    cols = ["proposed", "refined", "worktrees"]
    cur_col_idx = cols.index(state.active_column) if state.active_column in cols else 0

    if key in ("\t", "l", "L", "KEY_RIGHT", "\x1b[C"):
        next_col = cols[(cur_col_idx + 1) % len(cols)]
        return FlowAction("SWITCH_COLUMN", column=next_col)

    if key in ("h", "H", "KEY_LEFT", "\x1b[D"):
        prev_col = cols[(cur_col_idx - 1) % len(cols)]
        return FlowAction("SWITCH_COLUMN", column=prev_col)

    cur_col = state.active_column
    cur_idx = state.selected_index.get(cur_col, 0)
    items_count = (
        len(state.proposed_tasks) if cur_col == "proposed"
        else len(state.refined_tasks) if cur_col == "refined"
        else len(state.worktrees)
    )

    if key in ("j", "J", "KEY_DOWN", "\x1b[B"):
        new_idx = min(max(0, items_count - 1), cur_idx + 1)
        return FlowAction("NAVIGATE", column=cur_col, index=new_idx)

    if key in ("k", "K", "KEY_UP", "\x1b[A"):
        new_idx = max(0, cur_idx - 1)
        return FlowAction("NAVIGATE", column=cur_col, index=new_idx)

    if key in ("r", "R"):
        if cur_col == "proposed" and state.proposed_tasks and cur_idx < len(state.proposed_tasks):
            t = state.proposed_tasks[cur_idx]
            return FlowAction("REFINE", target=t.canonical_id)

    if key in ("c", "C"):
        if cur_col == "refined" and state.refined_tasks and cur_idx < len(state.refined_tasks):
            t = state.refined_tasks[cur_idx]
            return FlowAction("CLAIM", target=t.canonical_id)

    return FlowAction("NONE")


def _read_flow_keypress(timeout: float = 0.2) -> str | None:
    """Reads a single keypress or escape sequence non-blockingly."""
    if not sys.stdin.isatty():
        return None
    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            rlist, _, _ = select.select([sys.stdin], [], [], timeout)
            if rlist:
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if r2:
                        ch2 = sys.stdin.read(1)
                        if ch2 == "[":
                            ch3 = sys.stdin.read(1)
                            return f"\x1b[{ch3}"
                return ch
            return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        return None


class FlowMonitor:
    """SpecOps Interactive Terminal Backlog Flow Monitor."""

    def __init__(self, config: SpecOpsConfig | None = None) -> None:
        self.config = config or load_config()
        self.queue = BacklogQueue(self.config.backlog_dir)
        self.state = FlowState()
        self.refresh()

    def refresh(self) -> None:
        """Polls disk state to refresh backlog tasks and active worktree telemetry."""
        tasks = self.queue.list_all_tasks()
        self.state.proposed_tasks = [t for t in tasks if t.status == "Proposed"]
        self.state.refined_tasks = [t for t in tasks if t.status in ("Refined", "Ready")]
        self.state.completed_count = len([t for t in tasks if t.status == "Complete"])

        ratio, col_name, badge = get_buffer_waterline(
            len(self.state.refined_tasks),
            self.config.architecture.buffer_target,
        )
        self.state.buffer_badge = badge
        self.state.buffer_color = col_name

        self.state.worktrees = self._scan_worktrees()

    def _scan_worktrees(self) -> list[dict[str, Any]]:
        """Scans in-flight worktrees and active worker telemetry."""
        wt_dir = self.config.root_dir / ".worktrees"
        if not wt_dir.exists():
            return []

        worktrees: list[dict[str, Any]] = []
        now = time.time()
        for p in sorted(wt_dir.iterdir()):
            if not p.is_dir() or not p.name.startswith("task-"):
                continue
            tid_num = p.name.replace("task-", "").zfill(4)
            cid = f"TASK-{tid_num}"

            # Branch detection
            branch_res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=p,
                capture_output=True,
                text=True,
            )
            branch = branch_res.stdout.strip() if branch_res.returncode == 0 else f"feat/task-{tid_num}"

            # Elapsed time
            mtime = p.stat().st_mtime
            elapsed = format_elapsed_time(now - mtime)

            # Preflight status
            status = "Executing (uv run pytest)"
            worker_json = p / ".specops" / "worker.json"
            if worker_json.exists():
                try:
                    import json
                    wdata = json.loads(worker_json.read_text(encoding="utf-8"))
                    check = wdata.get("active_preflight_check", "uv run pytest")
                    st = wdata.get("status", "Executing")
                    status = f"{st} ({check})"
                except Exception:
                    pass

            worktrees.append({
                "task_id": cid,
                "branch": branch,
                "elapsed": elapsed,
                "status": status,
                "path": str(p),
            })

        return worktrees

    def promote_task(self, task_id: str) -> bool:
        """Promotes proposed task to refined/ if DoR rules are satisfied."""
        target = next((t for t in self.state.proposed_tasks if t.canonical_id == task_id), None)
        if not target:
            return False

        dor_ok, _ = validate_definition_of_ready(target, self.config)
        if not dor_ok:
            self.state.status_message = f"❌ {task_id} failed Definition of Ready gate"
            return False

        self.queue.refine_task(target)
        self.refresh()
        self.state.status_message = f"✅ Promoted {task_id} to refined/ · Buffer now {self.state.buffer_badge}"
        return True

    def claim_task(self, task_id: str, claimant: str = "riley") -> bool:
        """Provisions worktree and claims task for developer."""
        target = next((t for t in self.state.refined_tasks if t.canonical_id == task_id), None)
        if not target:
            return False

        clean_num = task_id.lower().replace("task-", "").zfill(4)
        branch = f"feat/task-{clean_num}"
        wt_path = self.config.root_dir / ".worktrees" / f"task-{clean_num}"

        create_worktree(self.config.root_dir, branch, wt_path)

        target.claimed_by = claimant
        target.branch = branch
        write_task_file(target)

        self.refresh()
        self.state.status_message = f"✅ Provisioned {wt_path.name} on {branch} for {claimant}"

        if sys.stdin.isatty():
            shell = os.environ.get("SHELL", "/bin/bash")
            subprocess.run([shell], cwd=wt_path)
            self.refresh()

        return True

    def render_layout(self) -> Layout:
        """Constructs Rich 3-column layout displaying live flow telemetry."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )

        header_text = Text()
        header_text.append("⚡ SpecOps Backlog Flow Monitor", style="bold cyan")
        header_text.append(f"  |  Completed: {self.state.completed_count}", style="green")
        header_text.append(f"  |  {self.state.buffer_badge}", style=f"bold {self.state.buffer_color.lower()}")
        layout["header"].update(Panel(header_text, style="cyan", border_style="cyan"))

        footer_text = Text()
        footer_text.append("[r] Refine Task  ", style="bold yellow")
        footer_text.append("[c] Claim & Worktree  ", style="bold green")
        footer_text.append("[h/l/Tab] Columns  ", style="bold cyan")
        footer_text.append("[j/k] Navigate  ", style="bold cyan")
        footer_text.append("[q] Quit", style="bold red")
        if self.state.status_message:
            footer_text.append(f"  |  {self.state.status_message}", style="white")
        layout["footer"].update(Panel(footer_text, style="dim", border_style="dim"))

        # Column 1: Proposed
        p_table = Table(expand=True, box=None)
        p_table.add_column("Task ID", style="magenta", width=12)
        p_table.add_column("Title", style="white")
        for idx, t in enumerate(self.state.proposed_tasks):
            is_sel = self.state.active_column == "proposed" and idx == self.state.selected_index["proposed"]
            style = "bold reverse" if is_sel else ""
            p_table.add_row(t.canonical_id, t.title, style=style)

        # Column 2: Refined (Buffer: X/10 [Color])
        r_table = Table(expand=True, box=None)
        r_table.add_column("Task ID", style="yellow", width=12)
        r_table.add_column("Title", style="white")
        for idx, t in enumerate(self.state.refined_tasks):
            is_sel = self.state.active_column == "refined" and idx == self.state.selected_index["refined"]
            style = "bold reverse" if is_sel else ""
            r_table.add_row(t.canonical_id, t.title, style=style)

        # Column 3: In-Flight Worktrees
        w_table = Table(expand=True, box=None)
        w_table.add_column("Worker / Branch", style="cyan", width=22)
        w_table.add_column("Elapsed", style="dim", width=10)
        w_table.add_column("Preflight Status", style="green")
        for idx, wt in enumerate(self.state.worktrees):
            is_sel = self.state.active_column == "worktrees" and idx == self.state.selected_index["worktrees"]
            style = "bold reverse" if is_sel else ""
            w_table.add_row(wt["branch"], wt["elapsed"], wt["status"], style=style)

        buf_color = self.state.buffer_color.lower()
        col_prop = Panel(p_table, title=f"📋 Proposed ({len(self.state.proposed_tasks)})", border_style="magenta" if self.state.active_column == "proposed" else "dim")
        col_ref = Panel(r_table, title=f"⚡ Refined ({self.state.buffer_badge})", border_style=buf_color if self.state.active_column == "refined" else "dim")
        col_wt = Panel(w_table, title=f"🚀 In-Flight Worktrees ({len(self.state.worktrees)})", border_style="cyan" if self.state.active_column == "worktrees" else "dim")

        layout["body"].split_row(
            Layout(col_prop, name="col_proposed"),
            Layout(col_ref, name="col_refined"),
            Layout(col_wt, name="col_worktrees"),
        )
        return layout

    def render_snapshot(self, console: Console | None = None) -> None:
        """Renders single snapshot frame without entering interactive loop."""
        con = console or Console()
        self.refresh()
        con.print(self.render_layout())

    def run(self) -> int:
        """Executes full-screen interactive terminal flow loop."""
        if not sys.stdin.isatty():
            self.render_snapshot()
            return 0

        console = Console()
        running = True
        try:
            with Live(self.render_layout(), console=console, screen=True, auto_refresh=False) as live:
                while running:
                    self.refresh()
                    live.update(self.render_layout())
                    live.refresh()

                    key = _read_flow_keypress(timeout=0.3)
                    if not key:
                        continue

                    action = handle_flow_key(key, self.state)
                    if action.action == "QUIT":
                        running = False
                        break
                    elif action.action == "SWITCH_COLUMN":
                        self.state.active_column = action.column
                    elif action.action == "NAVIGATE":
                        self.state.selected_index[action.column] = action.index
                    elif action.action == "REFINE":
                        self.promote_task(action.target)
                    elif action.action == "CLAIM":
                        claimant = os.environ.get("SPECOPS_CLAIMANT", "riley")
                        self.claim_task(action.target, claimant=claimant)
        except KeyboardInterrupt:
            pass

        return 0
