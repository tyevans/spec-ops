"""Interactive Terminal UI application for SpecOps."""

from __future__ import annotations

import select
import sys

from rich.console import Console
from rich.layout import Layout
from rich.live import Live

from ..backlog.curator import BacklogCurator
from ..backlog.health import HealthChecker, HealthCheckReport
from ..backlog.queue import BacklogQueue
from ..config.loader import load_config
from ..config.models import SpecOpsConfig
from ..core.graph import process_project_graph
from ..core.models import ProjectData
from ..core.parser import SpecOpsParser
from .views import (
    render_backlog_panel,
    render_entity_tree,
    render_footer,
    render_header,
    render_health_panel,
    render_task_dependency_tree,
)


def _read_single_keypress(timeout: float = 0.2) -> str | None:
    """Reads a single keypress without requiring Enter (Unix-compatible)."""
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
                char = sys.stdin.read(1)
                return char
            return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        return None


class TUIDashboard:
    """SpecOps Interactive Terminal Dashboard."""

    def __init__(self, config: SpecOpsConfig | None = None) -> None:
        self.config = config or load_config()
        self.active_view = "overview"
        self.tree_view_type = "dependency"
        self.status_message = "Ready (Press 1-4 to navigate, t to toggle tree, c to curate, q to quit)"
        self.data: ProjectData | None = None
        self.report: HealthCheckReport | None = None
        self.queue: BacklogQueue | None = None
        self.refresh_data()

    def refresh_data(self) -> None:
        """Reloads project entities, backlog queue, and health invariants from disk."""
        parser = SpecOpsParser(self.config.project_docs_dir)
        self.data = parser.parse_all()
        process_project_graph(self.data, target_buffer=self.config.architecture.buffer_target)

        checker = HealthChecker(self.config)
        self.report = checker.run_check()
        self.queue = BacklogQueue(self.config.backlog_dir)

    def curate_backlog(self) -> str:
        """Triggers JIT backlog curation and refreshes dashboard state."""
        curator = BacklogCurator(self.config)
        res = curator.curate()
        self.refresh_data()
        msg = f"Curated: {len(res.tasks_refined)} tasks refined"
        self.status_message = msg
        return msg

    def render_layout(self, view: str | None = None) -> Layout:
        """Builds Rich Layout for the current or specified view."""
        current_view = view or self.active_view
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )

        header = render_header(self.config.project.name, current_view)
        footer = render_footer(self.status_message)
        layout["header"].update(header)
        layout["footer"].update(footer)

        if self.report is None or self.queue is None or self.data is None:
            self.refresh_data()

        assert self.report is not None
        assert self.queue is not None
        assert self.data is not None

        if current_view == "overview":
            layout["body"].split_row(
                Layout(render_backlog_panel(self.report, self.queue), name="backlog_panel"),
                Layout(render_health_panel(self.report), name="health_panel"),
            )
        elif current_view == "backlog":
            layout["body"].update(render_backlog_panel(self.report, self.queue))
        elif current_view == "tree":
            if self.tree_view_type == "dependency":
                layout["body"].update(
                    render_task_dependency_tree(
                        self.queue.list_all_tasks(),
                        self.queue.get_completed_task_ids(),
                    )
                )
            else:
                layout["body"].update(render_entity_tree(self.data))
        elif current_view == "health":
            layout["body"].update(render_health_panel(self.report))
        else:
            layout["body"].update(render_backlog_panel(self.report, self.queue))

        return layout

    def render_snapshot(self, view: str = "overview", console: Console | None = None) -> None:
        """Renders a single dashboard frame and exits without interactive event loop."""
        con = console or Console()
        self.active_view = view
        layout = self.render_layout(view)
        con.print(layout)

    def run(self, initial_view: str = "overview") -> int:
        """Runs the interactive TUI event loop (or snapshot if non-interactive)."""
        self.active_view = initial_view
        if not sys.stdin.isatty():
            self.render_snapshot(initial_view)
            return 0

        console = Console()
        running = True
        try:
            with Live(self.render_layout(), console=console, screen=True, auto_refresh=False) as live:
                while running:
                    live.update(self.render_layout())
                    live.refresh()

                    key = _read_single_keypress(timeout=0.3)
                    if not key:
                        continue

                    if key in ("q", "Q", "\x03"):  # 'q' or Ctrl+C
                        running = False
                        break
                    elif key == "1":
                        self.active_view = "overview"
                        self.status_message = "Switched to Overview"
                    elif key == "2":
                        self.active_view = "backlog"
                        self.status_message = "Switched to Backlog Queue"
                    elif key == "3":
                        self.active_view = "tree"
                        self.status_message = f"Switched to Tree ({self.tree_view_type.capitalize()})"
                    elif key == "4":
                        self.active_view = "health"
                        self.status_message = "Switched to Health Invariants"
                    elif key in ("t", "T"):
                        if self.active_view != "tree":
                            self.active_view = "tree"
                        if self.tree_view_type == "dependency":
                            self.tree_view_type = "entity"
                            self.status_message = "Switched Tree to Entity Hierarchy"
                        else:
                            self.tree_view_type = "dependency"
                            self.status_message = "Switched Tree to Task Dependency Flow"
                    elif key in ("c", "C"):
                        self.status_message = "Curating backlog..."
                        live.update(self.render_layout())
                        live.refresh()
                        self.curate_backlog()
                    elif key in ("h", "H", "r", "R"):
                        self.refresh_data()
                        self.status_message = "Refreshed health and graph metrics"
        except KeyboardInterrupt:
            pass

        return 0
