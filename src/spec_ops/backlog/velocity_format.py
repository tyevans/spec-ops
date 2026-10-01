"""Rich terminal formatters for hybrid velocity and rescue analytics."""

from __future__ import annotations

from rich.table import Table

from .velocity_models import VelocityReport


def format_velocity_table(report: VelocityReport) -> Table:
    """Formats velocity KPIs as a rich table."""
    table = Table(title=f"Hybrid Delivery Velocity (Window: {report.window})", border_style="dim")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Agent Workers", style="green", justify="right")
    table.add_column("Human Developers", style="magenta", justify="right")
    table.add_column("Hybrid Total", style="bold white", justify="right")

    am = report.agent_metrics
    hm = report.human_metrics
    tot = report.hybrid_total

    table.add_row("Tasks Delivered", str(am.tasks_delivered), str(hm.tasks_delivered), str(tot.tasks_delivered))
    table.add_row("Merged Commits", str(am.merged_commits), str(hm.merged_commits), str(tot.merged_commits))
    table.add_row("Tasks Delivered per Week", f"{am.tasks_per_week:.1f}", f"{hm.tasks_per_week:.1f}", f"{tot.tasks_per_week:.1f}")
    table.add_row("Average Task Cycle Time", am.avg_cycle_time_formatted, hm.avg_cycle_time_formatted, tot.avg_cycle_time_formatted)
    table.add_row(
        "First-Pass Preflight Pass Rate",
        f"{am.preflight_pass_rate:.1f}%" if am.preflight_pass_rate is not None else "N/A",
        f"{hm.preflight_pass_rate:.1f}%" if hm.preflight_pass_rate is not None else "N/A",
        f"{tot.preflight_pass_rate:.1f}%" if tot.preflight_pass_rate is not None else "N/A",
    )
    table.add_row(
        "Self-Healing Resolution Rate",
        f"{am.self_healing_rate:.1f}%" if am.self_healing_rate is not None else "N/A",
        "N/A",
        f"{tot.self_healing_rate:.1f}%" if tot.self_healing_rate is not None else "N/A",
    )
    table.add_row(
        "Human Rescue Escalation Rate",
        f"{am.rescue_escalation_rate:.1f}%" if am.rescue_escalation_rate is not None else "N/A",
        "N/A",
        f"{tot.rescue_escalation_rate:.1f}%" if tot.rescue_escalation_rate is not None else "N/A",
    )
    return table


def format_rescues_table(report: VelocityReport) -> Table:
    """Formats rescue failure clustering table."""
    table = Table(title="Autonomous Agent Rescue & Failure Telemetry", border_style="dim")
    table.add_column("Failure Cluster", style="bold red")
    table.add_column("Incidents", style="yellow", justify="right")
    table.add_column("Percentage", style="cyan", justify="right")
    table.add_column("Top Invariants / Sample", style="dim white")

    if report.rescues and report.rescues.failure_clusters:
        for c in report.rescues.failure_clusters:
            invs = ", ".join(c.top_invariants) if c.top_invariants else (c.sample_reason or "—")
            table.add_row(c.cluster, str(c.incidents), f"{c.percentage:.1f}%", invs)
    else:
        table.add_row("No rescue incidents recorded", "0", "0.0%", "Clean autonomous execution")

    return table
