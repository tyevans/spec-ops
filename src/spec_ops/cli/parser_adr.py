"""CLI argument parsers for Architectural Decision Record (ADR) commands."""

from __future__ import annotations

import argparse


def register_adr_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers Architectural Decision Record (ADR) lifecycle commands."""
    p_adr = subparsers.add_parser("adr", help="Architectural Decision Record (ADR) lifecycle, amendment, and supersession")
    adr_subs = p_adr.add_subparsers(dest="adr_action", help="ADR action")

    # spec-ops adr supersede
    p_sup = adr_subs.add_parser("supersede", help="Supersede an existing ADR with a new decision")
    p_sup.add_argument("old_id", nargs="?", default=None, help="Canonical ID or path of superseded ADR (e.g. ADR-0003)")
    p_sup.add_argument("new_id_pos", nargs="?", default=None, help="Superseding ADR identifier or path")
    p_sup.add_argument("--old", dest="opt_old", default=None, help="Target old ADR to supersede")
    p_sup.add_argument("--title", default=None, help="Title of new superseding ADR")
    p_sup.add_argument("--by", "--with", dest="by", default=None, help="Superseding ADR identifier or path (e.g. ADR-0015)")
    p_sup.add_argument("--dry-run", action="store_true", default=False, help="Simulate supersession without modifying files")

    # spec-ops adr amend
    p_amd = adr_subs.add_parser("amend", help="Amend an existing ADR with an incremental refinement")
    p_amd.add_argument("old_id", nargs="?", default=None, help="Canonical ID or path of target ADR to amend (e.g. ADR-0101)")
    p_amd.add_argument("new_id_pos", nargs="?", default=None, help="Amending ADR identifier or path")
    p_amd.add_argument("--old", dest="opt_old", default=None, help="Target old ADR to amend")
    p_amd.add_argument("--title", default=None, help="Title of new amending ADR")
    p_amd.add_argument("--by", "--with", dest="by", default=None, help="Amending ADR identifier or path (e.g. ADR-0116)")
    p_amd.add_argument("--dry-run", action="store_true", default=False, help="Simulate amendment without modifying files")
