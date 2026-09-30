"""Rich view renderers for the SpecOps TUI dashboard."""

from __future__ import annotations

from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from ..backlog.health import HealthCheckReport
from ..backlog.queue import BacklogQueue
from ..core.models import ProjectData, Task

STATUS_STYLES = {
    "Complete": "bold green",
    "Refined": "bold yellow",
    "Proposed": "bold magenta",
    "In-Progress": "bold cyan",
}


def render_header(project_name: str, active_tab: str) -> Panel:
    """Renders the top branding and tab bar."""
    text = Text()
    text.append("⚡ SpecOps TUI", style="bold cyan")
    text.append(f"  |  Project: {project_name}", style="bold white")
    text.append("  |  Active View: ", style="dim")
    text.append(f"[{active_tab.upper()}]", style="bold yellow")
    return Panel(text, style="cyan", border_style="cyan")


def render_backlog_panel(report: HealthCheckReport, queue: BacklogQueue) -> Panel:
    """Renders backlog buffer gauge and priority task table."""
    table = Table(title="Top Priority Queue", expand=True, border_style="dim")
    table.add_column("Rank", justify="center", style="dim", width=6)
    table.add_column("ID", style="bold cyan", width=12)
    table.add_column("Title", style="white")
    table.add_column("Status", width=14)

    tasks = queue.list_all_tasks()
    for idx, t in enumerate(tasks[:8], start=1):
        style = STATUS_STYLES.get(t.status, "white")
        table.add_row(str(idx), t.canonical_id, t.title, Text(t.status, style=style))

    # Buffer badge
    buf_color = "green" if report.buffer_status == "OPTIMAL" else "yellow" if report.buffer_status == "UNDER_BUFFERED" else "red"
    summary_text = Text()
    summary_text.append(f"Complete: {report.completed_tasks}  |  ", style="green")
    summary_text.append(f"Refined Buffer: {report.refined_tasks} ({report.buffer_status})  |  ", style=buf_color)
    summary_text.append(f"Proposed: {report.proposed_tasks}", style="magenta")

    content = Columns([Panel(summary_text, title="Buffer State", border_style=buf_color), table])
    return Panel(content, title="📋 Backlog Management", border_style="blue")


def render_entity_tree(data: ProjectData) -> Panel:
    """Renders the full entity hierarchy as a navigable Rich Tree."""
    root = Tree(f"[bold cyan]📦 Project Entities ({len(data.tasks)} tasks, {len(data.stories)} stories, {len(data.prds)} PRDs)")

    # Personas branch
    p_branch = root.add(f"[bold yellow]👤 Personas ({len(data.personas)})")
    for p in data.personas:
        p_node = p_branch.add(f"{p.name} [dim]({p.role})[/dim]")
        for s in data.stories:
            if s.persona.lower() in p.name.lower() or p.name.lower() in s.persona.lower():
                p_node.add(f"[cyan]{s.id}[/cyan]: {s.title}")

    # PRDs branch
    prd_branch = root.add(f"[bold red]📄 PRDs & Features ({len(data.prds)})")
    for prd in data.prds:
        prd_node = prd_branch.add(f"[bold white]{prd.id}[/bold white] — {prd.title} [dim]({prd.status})[/dim]")
        for tid in prd.implementing_tasks:
            prd_node.add(f"[magenta]{tid}[/magenta]")

    # ADRs branch
    adr_branch = root.add(f"[bold blue]🏛️ Architecture Decision Records ({len(data.adrs)})")
    for a in data.adrs:
        adr_branch.add(f"[blue]{a.id}[/blue]: {a.title} [dim]({a.status})[/dim]")

    # Tasks branch
    t_branch = root.add(f"[bold green]🎯 Backlog Tasks ({len(data.tasks)})")
    for t in data.tasks[:10]:
        st_style = STATUS_STYLES.get(t.status, "white")
        t_branch.add(f"[{st_style}]{t.canonical_id}[/{st_style}] {t.title} [dim]({t.status})[/dim]")

    if len(data.tasks) > 10:
        t_branch.add(f"[dim]... and {len(data.tasks) - 10} more tasks[/dim]")

    return Panel(root, title="🌳 Relational Entity Tree", border_style="yellow")


def render_task_dependency_tree(tasks: list[Task], completed_ids: set[str], reverse: bool = False) -> Panel:
    """Renders the live task dependency DAG tree for the TUI dashboard."""
    from ..backlog.tree import TaskDependencyTreeEngine

    engine = TaskDependencyTreeEngine(tasks, completed_ids=completed_ids)
    if reverse:
        tree = engine.build_prerequisite_tree(include_completed=False)
        title = "🔍 Task Prerequisites Tree (Blocked By)"
    else:
        tree = engine.build_forward_tree(include_completed=False)
        title = "🌳 Task Dependency Tree (Execution Flow)"
    return Panel(tree, title=title, border_style="yellow")


def render_health_panel(report: HealthCheckReport) -> Panel:
    """Renders codebase invariants and file length distributions."""
    table = Table(title="Largest Source Files (<500 lines limit)", expand=True, border_style="dim")
    table.add_column("Lines", justify="right", width=8)
    table.add_column("File Path", style="white")
    table.add_column("Status", width=12)

    for lines, path in report.top_largest_files[:8]:
        if lines > 500:
            status = Text("VIOLATION", style="bold red")
        elif lines >= 400:
            status = Text("WARNING", style="bold yellow")
        else:
            status = Text("OK", style="green")
        table.add_row(str(lines), str(path), status)

    inv_text = Text()
    if report.violations:
        inv_text.append(f"❌ {len(report.violations)} File Length Violation(s)\n", style="bold red")
    else:
        inv_text.append("✅ Invariant Met: Zero files exceed length limit (<500 lines)\n", style="bold green")

    if report.warnings:
        inv_text.append(f"⚠️ {len(report.warnings)} Proactive Warning(s) (>=400 lines)\n", style="bold yellow")

    if report.priority_sync_ok:
        inv_text.append("✅ PRIORITY.md is synchronized with disk state", style="bold green")
    else:
        inv_text.append("❌ PRIORITY.md is out of sync with disk state", style="bold red")

    content = Columns([Panel(inv_text, title="Invariant Verification", border_style="green" if report.is_healthy else "red"), table])
    return Panel(content, title="🏥 Invariant Health Status", border_style="green" if report.is_healthy else "red")


def render_task_detail(task: Task) -> Panel:
    """Renders deep inspection view of a single task."""
    st_style = STATUS_STYLES.get(task.status, "white")
    header_text = Text()
    header_text.append(f"{task.canonical_id}: ", style="bold cyan")
    header_text.append(f"{task.title}\n", style="bold white")
    header_text.append(f"Status: {task.status}  |  ", style=st_style)
    header_text.append(f"Target BC: {task.target_bc or 'core'}  |  ", style="dim")
    header_text.append(f"Dependencies: {', '.join(task.dependencies) or 'None'}\n", style="dim")
    header_text.append(f"Governing ADRs: {', '.join(task.governing_adrs) or 'None'}  |  ", style="blue")
    header_text.append(f"Governing PRDs: {', '.join(task.governing_prds) or 'None'}\n", style="red")

    body_panel = Panel(task.body[:600] + ("..." if len(task.body) > 600 else ""), title="Task Specification", border_style="dim")
    return Panel(Columns([Panel(header_text, border_style="cyan"), body_panel]), title="🔍 Task Details", border_style="magenta")


def render_footer(message: str = "") -> Panel:
    """Renders interactive navigation keybindings."""
    footer = Text()
    footer.append("[1] Overview  ", style="bold cyan")
    footer.append("[2] Backlog  ", style="bold cyan")
    footer.append("[3] Tree  ", style="bold cyan")
    footer.append("[4] Health  ", style="bold cyan")
    footer.append("|  [t] Toggle Tree  ", style="bold yellow")
    footer.append("[c] Curate  ", style="bold yellow")
    footer.append("[h] Health  ", style="bold green")
    footer.append("[q] Quit", style="bold red")
    if message:
        footer.append(f"  |  {message}", style="bold yellow")
    return Panel(footer, style="dim", border_style="dim")
