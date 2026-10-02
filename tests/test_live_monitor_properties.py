"""Hypothesis property tests for terminal dashboard live monitor rendering.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0008, ADR-0009, ADR-0010; PRD-0001, PRD-0006; TASK-0167.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from hypothesis import given, settings
import hypothesis.strategies as st
from rich.console import Console

from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.event_streamer import EventEnvelope
from spec_ops.tui.live_monitor import LiveMonitor


# Strategy generating arbitrary EventEnvelope payloads and string attributes
event_strategy = st.builds(
    EventEnvelope,
    event_id=st.text(min_size=0, max_size=50),
    event_type=st.text(min_size=0, max_size=50),
    aggregate_id=st.text(min_size=0, max_size=50),
    sequence_number=st.integers(min_value=0, max_value=100000),
    timestamp=st.text(min_size=0, max_size=50),
    payload=st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(st.text(), st.integers(), st.booleans(), st.none()),
        max_size=5,
    ),
)


@settings(max_examples=50, deadline=None)
@given(
    events=st.lists(event_strategy, min_size=0, max_size=10),
    width=st.integers(min_value=40, max_value=240),
    height=st.integers(min_value=15, max_value=100),
    tab=st.sampled_from(["workers", "events", "health"]),
)
def test_render_routines_handle_arbitrary_events_and_dimensions(
    events: list[EventEnvelope], width: int, height: int, tab: str
):
    """Asserts that terminal rendering routines handle arbitrary event payloads and screen sizes without throwing uncaught exceptions."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = SpecOpsConfig(root_dir=Path(tmp_dir))
        monitor = LiveMonitor(config=config, interval=0.1, initial_tab=tab)
        monitor.events = list(events)

        console = Console(record=True, width=width, height=height)

        # Invariant 1: render_layout() executes safely and can be rendered by console
        layout = monitor.render_layout()
        console.print(layout)
        output = console.export_text()
        assert isinstance(output, str)
        assert len(output) > 0

        # Invariant 2: render_snapshot() executes safely across all tabs
        for t in ["workers", "events", "health"]:
            monitor.active_tab = t
            snap_console = Console(record=True, width=width, height=height)
            monitor.render_snapshot(console=snap_console)
            snap_text = snap_console.export_text()
            assert isinstance(snap_text, str)
            assert len(snap_text) > 0
