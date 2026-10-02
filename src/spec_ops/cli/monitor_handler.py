"""CLI command handler for spec-ops monitor command."""

from __future__ import annotations

import argparse
import json
import sys

from ..config.models import SpecOpsConfig
from ..tui.live_monitor import LiveMonitor


def handle_monitor_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Dispatches 'spec-ops monitor' execution."""
    interval = getattr(args, "interval", 1.0) or 1.0
    headless = getattr(args, "headless", False)
    tab = getattr(args, "tab", "workers") or "workers"
    as_json = getattr(args, "json", False)

    monitor = LiveMonitor(config=config, interval=interval, initial_tab=tab)

    if as_json:
        monitor.poll_events()
        leases = monitor.lease_mgr.list_leases()
        tasks = monitor.backlog_queue.list_all_tasks()
        payload = {
            "tab": monitor.active_tab,
            "leases": [l.to_dict() for l in leases],
            "events_count": len(monitor.events),
            "events": [ev.to_dict() for ev in monitor.events[-20:]],
            "health": {
                "total_tasks": len(tasks),
                "completed": sum(1 for t in tasks if t.status == "Complete"),
                "refined": sum(1 for t in tasks if t.status == "Refined"),
                "proposed": sum(1 for t in tasks if t.status == "Proposed"),
            },
        }
        print(json.dumps(payload, indent=2))
        return 0

    if headless or not sys.stdin.isatty():
        monitor.render_snapshot()
        return 0

    return monitor.run()
