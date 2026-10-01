"""Architectural spike lifecycle and empirical ADR synthesis CLI parser."""

from __future__ import annotations

import argparse


def register_spike_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers architectural spike lifecycle commands."""
    p_spike = subparsers.add_parser("spike", help="Governed architectural spike lifecycle, sandboxing, and empirical ADR synthesis")
    spike_subs = p_spike.add_subparsers(dest="spike_action", help="Spike action")

    p_spk_create = spike_subs.add_parser("create", help="Author a new architectural spike task and isolated test harness")
    p_spk_create.add_argument("--name", required=True, help="Spike descriptive name / topic")
    p_spk_create.add_argument("--question", required=True, help="Unanswered question or hypothesis statement to validate")
    p_spk_create.add_argument("--timebox", default="2h", help="Timebox duration (default: 2h)")
    p_spk_create.add_argument("--task", default=None, help="Governing task canonical ID (e.g. TASK-0052)")
    p_spk_create.add_argument("--prd", default=None, help="Governing PRD canonical ID (e.g. PRD-0002)")

    p_spk_start = spike_subs.add_parser("start", help="Instantiate disposable sandboxed spike worktree")
    p_spk_start.add_argument("spike_id", help="Spike canonical identifier (e.g. SPIKE-0002 or 0002)")
    p_spk_start.add_argument("--hypothesis", default=None, help="Hypothesis statement for empirical validation")
    p_spk_start.add_argument("--timebox", default=None, help="Spike timebox duration (e.g. 2h, 4h)")

    p_spk_check = spike_subs.add_parser("check", help="Check spike timebox and write isolation")
    p_spk_check.add_argument("spike_id", nargs="?", default=None, help="Spike identifier (optional if run inside worktree)")
    p_spk_check.add_argument("--elapsed", type=float, default=None, help="Simulated elapsed seconds for testing")

    p_spk_preflight = spike_subs.add_parser("preflight", help="Enforce in-worktree write isolation preflight hook")
    p_spk_preflight.add_argument("spike_id", nargs="?", default=None, help="Spike identifier")

    p_spk_grad = spike_subs.add_parser("graduate", help="Graduate empirical spike findings into an Architectural Decision Record")
    p_spk_grad.add_argument("spike_id", help="Spike canonical identifier (e.g. SPIKE-0002 or 0002)")
    p_spk_grad.add_argument("--result", required=True, choices=["proven", "disproven"], help="Empirical hypothesis validation result")
    p_spk_grad.add_argument("--title", default=None, help="ADR Title")
    p_spk_grad.add_argument("--notes", default=None, help="Empirical observations or rationale")
    p_spk_grad.add_argument("--findings", default=None, help="Recorded benchmark output / findings")
    p_spk_grad.add_argument("--status", default=None, help="ADR status (e.g. Accepted, Proposed)")
