"""Rich tree and panel formatters for task dependency DAGs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

if TYPE_CHECKING:
    from .tree import TaskDependencyTreeEngine, TaskNodeState


def render_node_label(states: dict[str, TaskNodeState], cid: str) -> Text:
    """Renders rich badge and title for a task node."""
    state = states.get(cid)
    text = Text()
    if not state:
        text.append(f"{cid} [Missing]", style="dim red")
        return text

    t = state.task
    if state.is_complete:
        text.append(f"{cid} ", style="bold green")
        text.append(f"{t.title} ", style="green")
        text.append("[COMPLETE]", style="bold green")
    elif state.is_blocked_by_unknown:
        text.append(f"{cid} ", style="bold red")
        text.append(f"{t.title} ", style="white")
        text.append("[BLOCKED: UNKNOWN]", style="bold red on black")
        if t.blocker and t.blocker.question:
            text.append(f'\n   ❓ Unknown: "{t.blocker.question}"', style="bold yellow")
        if t.blocker and t.blocker.spike_id:
            text.append(f" (Investigating in {t.blocker.spike_id})", style="bold cyan")
    elif state.is_ready:
        st_color = "bold yellow" if t.status == "Refined" else "bold cyan"
        badge = "[READY]" if t.status == "Refined" else "[READY TO REFINE]"
        text.append(f"{cid} ", style=st_color)
        text.append(f"{t.title} ", style="bold white")
        text.append(f"{badge}", style=st_color)
        if t.claimed_by:
            text.append(f" [CLAIMED: {t.claimed_by}]", style="cyan")
    else:
        text.append(f"{cid} ", style="dim magenta")
        text.append(f"{t.title} ", style="dim white")
        unsat_str = ", ".join(state.unsatisfied_dependencies)
        text.append(f"[BLOCKED by {unsat_str}]", style="dim red")

    return text


def build_forward_tree(
    engine: TaskDependencyTreeEngine,
    focus_id: str | None = None,
    include_completed: bool = False,
) -> Tree:
    """Constructs forward execution tree (Unlocks / Flow view)."""
    root_title = Text(
        "🚀 Execution Dependency Tree (What Unlocks What)", style="bold cyan"
    )
    root = Tree(root_title)

    if focus_id:
        from .tree import normalize_task_id

        canon = normalize_task_id(focus_id)
        if canon not in engine.states:
            root.add(Text(f"❌ Task {focus_id} not found", style="bold red"))
            return root
        sub = root.add(engine.render_node_label(canon))
        _expand_forward(engine, sub, canon, visited=set())
        return root

    # Roots: tasks with 0 unsatisfied dependencies that are not completed (Wave 0)
    # Or completed tasks if include_completed is True
    roots: list[str] = []
    if include_completed:
        for cid, s in engine.states.items():
            if not engine.upstream.get(cid):
                roots.append(cid)
    else:
        for cid, s in engine.states.items():
            if not s.is_complete and len(s.unsatisfied_dependencies) == 0:
                roots.append(cid)

    roots.sort(
        key=lambda x: engine.states[x].task.priority_rank
        if x in engine.states
        else 999999
    )

    if not roots:
        root.add(
            Text(
                "All tasks are blocked or completed. Run with --all or --waves.",
                style="yellow",
            )
        )
        return root

    for r_id in roots:
        branch = root.add(engine.render_node_label(r_id))
        _expand_forward(
            engine, branch, r_id, visited=set(), include_completed=include_completed
        )

    return root


def _expand_forward(
    engine: TaskDependencyTreeEngine,
    parent: Tree,
    current_id: str,
    visited: set[str],
    include_completed: bool = False,
) -> None:
    if current_id in visited:
        parent.add(
            Text(f"🔁 Cycle detected referencing {current_id}", style="bold red")
        )
        return
    visited.add(current_id)

    dependents = sorted(
        engine.downstream.get(current_id, []),
        key=lambda x: engine.states[x].task.priority_rank
        if x in engine.states
        else 999999,
    )
    for dep in dependents:
        state = engine.states.get(dep)
        if not include_completed and state and state.is_complete:
            continue
        child = parent.add(engine.render_node_label(dep))
        _expand_forward(
            engine, child, dep, set(visited), include_completed=include_completed
        )


def build_prerequisite_tree(
    engine: TaskDependencyTreeEngine,
    focus_id: str | None = None,
    include_completed: bool = False,
) -> Tree:
    """Constructs reverse prerequisite tree (Blocked By view)."""
    root_title = Text(
        "🔍 Prerequisite Dependency Tree (Blocked By What)", style="bold magenta"
    )
    root = Tree(root_title)

    if focus_id:
        from .tree import normalize_task_id

        canon = normalize_task_id(focus_id)
        if canon not in engine.states:
            root.add(Text(f"❌ Task {focus_id} not found", style="bold red"))
            return root
        sub = root.add(engine.render_node_label(canon))
        _expand_reverse(
            engine, sub, canon, visited=set(), include_completed=include_completed
        )
        return root

    # Roots: tasks that no other task depends on (delivery leaves / end goals)
    leaf_tasks = [
        cid
        for cid, s in engine.states.items()
        if not s.is_complete and not engine.downstream.get(cid)
    ]
    leaf_tasks.sort(key=lambda x: engine.states[x].task.priority_rank)

    if not leaf_tasks:
        leaf_tasks = [cid for cid, s in engine.states.items() if not s.is_complete]
        leaf_tasks.sort(key=lambda x: engine.states[x].task.priority_rank)

    for leaf_id in leaf_tasks[:10]:
        branch = root.add(engine.render_node_label(leaf_id))
        _expand_reverse(
            engine,
            branch,
            leaf_id,
            visited=set(),
            include_completed=include_completed,
        )

    if len(leaf_tasks) > 10:
        root.add(
            Text(
                f"... and {len(leaf_tasks) - 10} more delivery endpoints",
                style="dim",
            )
        )

    return root


def _expand_reverse(
    engine: TaskDependencyTreeEngine,
    parent: Tree,
    current_id: str,
    visited: set[str],
    include_completed: bool = False,
) -> None:
    if current_id in visited:
        parent.add(
            Text(f"🔁 Cycle detected referencing {current_id}", style="bold red")
        )
        return
    visited.add(current_id)

    prereqs = sorted(
        engine.upstream.get(current_id, []),
        key=lambda x: engine.states[x].task.priority_rank
        if x in engine.states
        else 999999,
    )
    for p in prereqs:
        state = engine.states.get(p)
        child = parent.add(engine.render_node_label(p))
        if not include_completed and state and state.is_complete:
            continue
        _expand_reverse(
            engine, child, p, set(visited), include_completed=include_completed
        )


def render_waves_panel(engine: TaskDependencyTreeEngine) -> Panel:
    """Renders delivery horizons / execution waves table."""
    table = Table(
        title="🌊 Backlog Execution Horizons (Waves)",
        expand=True,
        border_style="dim",
    )
    table.add_column("Wave", justify="center", style="bold cyan", width=8)
    table.add_column("Tasks Unblocked in Wave", style="white")
    table.add_column("Wave Meaning & Action", style="dim", width=36)

    for idx, wave in enumerate(engine.waves):
        task_texts: list[str] = []
        for tid in wave:
            st = engine.states[tid]
            tag = "[READY]" if st.task.status == "Refined" else "[PROPOSED]"
            task_texts.append(f"{tid} {st.task.title} {tag}")
        meaning = (
            "Execute immediately (zero prerequisites)"
            if idx == 0
            else f"Unlocks when Wave {idx - 1} completes"
        )
        table.add_row(f"Wave {idx}", "\n".join(task_texts), meaning)

    # Choke points summary footer
    chokes = engine.get_choke_points(3)
    choke_text = Text(
        "\n🔥 Critical Path Choke Points (Complete these to unlock the most work):\n",
        style="bold yellow",
    )
    for idx, cp in enumerate(chokes, start=1):
        choke_text.append(
            f"  {idx}. {cp.canonical_id}: {cp.task.title} (Unlocks {cp.downstream_impact_count} downstream tasks)\n",
            style="white",
        )

    return Panel(table, title="🗓️ Delivery Horizons", border_style="cyan")
