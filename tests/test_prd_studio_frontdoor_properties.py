"""Generative Hypothesis property tests for PRD Studio frontdoor CLI parsing."""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.cli.main import build_parser

SAFE_ALPHABET = string.ascii_letters + string.digits + ".-_"
valid_hosts = st.sampled_from(["127.0.0.1", "0.0.0.0", "localhost"])
valid_ports = st.integers(min_value=1024, max_value=65535)


@settings(max_examples=40, deadline=None)
@given(host=valid_hosts, port=valid_ports, open_flag=st.booleans())
def test_cli_parsing_invariants(host: str, port: int, open_flag: bool):
    parser = build_parser()
    cmd = ["prd", "studio", "--host", host, "--port", str(port)]
    if open_flag:
        cmd.append("--open")

    args = parser.parse_args(cmd)
    assert args.command == "prd"
    assert args.prd_action == "studio"
    assert args.host == host
    assert args.port == port
    assert args.open is open_flag
