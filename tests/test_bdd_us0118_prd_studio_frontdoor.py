"""BDD step definitions for US-0118: PRD Studio Blackbox Frontdoor Verification."""

from __future__ import annotations

import json
import socket
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.prd.studio_runner import launch_prd_studio
from spec_ops.scaffold.init import init_project

scenarios("features/us_0118_prd_studio_frontdoor.feature")


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    return {}


@given("a project initialized with SpecOps")
def init_project_step(tmp_path: Path, bdd_ctx: dict[str, Any]):
    init_project(tmp_path, name="FrontdoorStudioProject")
    config = load_config(root_dir=tmp_path)
    bdd_ctx["config"] = config
    bdd_ctx["tmp_path"] = tmp_path


@when("the user launches the PRD Studio server on a local test port")
def launch_studio_server(bdd_ctx: dict[str, Any]):
    port = _get_free_port()
    config = bdd_ctx["config"]
    launch_prd_studio(config, host="127.0.0.1", port=port, open_browser=False, block=False)
    bdd_ctx["port"] = port
    bdd_ctx["base_url"] = f"http://127.0.0.1:{port}"


@then('the server responds to HTTP requests at "/studio" with the studio interface')
def verify_studio_html_response(bdd_ctx: dict[str, Any]):
    url = f"{bdd_ctx['base_url']}/studio"
    with urllib.request.urlopen(url, timeout=3) as resp:
        assert resp.status == 200
        html = resp.read().decode("utf-8")
        assert "SpecOps PRD Studio" in html
        assert "Diataxis Live Preview" in html


@then('the server provides REST API access to "/api/studio/state".')
def verify_api_state_response(bdd_ctx: dict[str, Any]):
    url = f"{bdd_ctx['base_url']}/api/studio/state"
    with urllib.request.urlopen(url, timeout=3) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("success") is True
        assert "state" in data


@given("a running PRD Studio web server")
def running_studio_server(tmp_path: Path, bdd_ctx: dict[str, Any]):
    init_project(tmp_path, name="RunningStudioServer")
    config = load_config(root_dir=tmp_path)
    port = _get_free_port()
    launch_prd_studio(config, host="127.0.0.1", port=port, open_browser=False, block=False)
    bdd_ctx["config"] = config
    bdd_ctx["tmp_path"] = tmp_path
    bdd_ctx["port"] = port
    bdd_ctx["base_url"] = f"http://127.0.0.1:{port}"


@when(
    parsers.parse(
        'the user creates a new draft for persona "{persona}" titled "{title}"'
    )
)
def create_draft_via_http(persona: str, title: str, bdd_ctx: dict[str, Any]):
    url = f"{bdd_ctx['base_url']}/api/studio/draft/new"
    payload = {
        "title": title,
        "persona": persona,
        "component": "prd",
        "problem_statement": "Automated receipt verification is required.",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        assert resp.status == 200
        bdd_ctx["last_new_res"] = json.loads(resp.read().decode("utf-8"))


@when(parsers.parse('adds checkable outcome "{outcome}"'))
def add_outcome_via_http(outcome: str, bdd_ctx: dict[str, Any]):
    url = f"{bdd_ctx['base_url']}/api/studio/draft/outcome/add"
    req = urllib.request.Request(
        url,
        data=json.dumps({"outcome": outcome}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        assert resp.status == 200


@when("submits a request to save the draft")
def save_draft_via_http(bdd_ctx: dict[str, Any]):
    url = f"{bdd_ctx['base_url']}/api/studio/draft/save"
    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as resp:
        assert resp.status == 200
        bdd_ctx["save_res"] = json.loads(resp.read().decode("utf-8"))


@then("the PRD file is persisted under docs/project/product/idea/")
def verify_file_on_disk(bdd_ctx: dict[str, Any]):
    save_res = bdd_ctx["save_res"]
    assert save_res.get("success") is True
    file_path = save_res.get("file_path")
    assert file_path is not None
    assert "docs/project/product/idea" in file_path
    disk_file = bdd_ctx["tmp_path"] / file_path
    assert disk_file.exists()
    bdd_ctx["disk_content"] = disk_file.read_text(encoding="utf-8")


@then("the saved document satisfies ADR-0001 specification invariants.")
def verify_document_invariants(bdd_ctx: dict[str, Any]):
    content = bdd_ctx["disk_content"]
    assert "status: Idea" in content
    assert "target_persona: Taylor" in content
    assert "## Problem Statement" in content
    assert "## Checkable Outcomes" in content
    assert "Running spec-ops prd uat generates verifiable receipt" in content
