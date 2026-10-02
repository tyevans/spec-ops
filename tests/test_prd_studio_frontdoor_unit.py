"""Blackbox frontdoor tests for PRD Studio CLI and HTTP lifecycle."""

from __future__ import annotations

import json
import socket
import urllib.request
from pathlib import Path

from spec_ops.cli.main import build_parser
from spec_ops.config.loader import load_config
from spec_ops.prd.studio_runner import launch_prd_studio
from spec_ops.scaffold.init import init_project


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_cli_parser_studio_flags():
    """Verify CLI parser registers 'prd studio' subparser and public flags."""
    parser = build_parser()
    args = parser.parse_args(["prd", "studio", "--open", "--port", "8999", "--host", "0.0.0.0"])
    assert args.command == "prd"
    assert args.prd_action == "studio"
    assert args.open is True
    assert args.port == 8999
    assert args.host == "0.0.0.0"


def test_launch_prd_studio_http_integration(tmp_path: Path):
    """Verify launch_prd_studio boots server and responds to public HTTP contracts."""
    init_project(tmp_path, name="TestLaunchStudio")
    config = load_config(root_dir=tmp_path)
    port = _get_free_port()

    res_code = launch_prd_studio(config, host="127.0.0.1", port=port, open_browser=False, block=False)
    assert res_code == 0

    base_url = f"http://127.0.0.1:{port}"

    # 1. Test HTML view
    with urllib.request.urlopen(f"{base_url}/studio", timeout=3) as resp:
        assert resp.status == 200
        html = resp.read().decode("utf-8")
        assert "SpecOps PRD Studio" in html

    # 2. Test GET state
    with urllib.request.urlopen(f"{base_url}/api/studio/state", timeout=3) as resp:
        assert resp.status == 200
        state_data = json.loads(resp.read().decode("utf-8"))
        assert state_data["success"] is True
        assert state_data["state"]["stage"] == "idea"

    # 3. Test POST new draft and save
    new_req = urllib.request.Request(
        f"{base_url}/api/studio/draft/new",
        data=json.dumps({
            "title": "Frontdoor Tested Feature",
            "persona": "Taylor",
            "component": "prd",
            "problem_statement": "Manual testing takes too long.",
            "outcomes": ["Automated frontdoor suite passes cleanly"],
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(new_req, timeout=3) as resp:
        assert resp.status == 200

    save_req = urllib.request.Request(
        f"{base_url}/api/studio/draft/save",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(save_req, timeout=3) as resp:
        assert resp.status == 200
        save_data = json.loads(resp.read().decode("utf-8"))
        assert save_data["success"] is True
        file_path = save_data["file_path"]
        assert (tmp_path / file_path).exists()
