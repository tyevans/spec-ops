"""Hypothesis property-based tests for standalone Customer UAT Matrix HTML export."""

from __future__ import annotations

import html
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spec_ops.prd.uat import record_uat_signoff
from spec_ops.prd.uat_export import render_uat_matrix_html
from spec_ops.scaffold.init import init_project


class WellFormedHTMLValidator(HTMLParser):
    """Simple parser validating HTML tags and structure."""

    def __init__(self):
        super().__init__()
        self.tags: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        self.tags.append(tag)

    def error(self, message: str):
        self.errors.append(message)


# Strategy for arbitrary outcome text including potential script injections
dangerous_text = st.one_of(
    st.text(min_size=1, max_size=80),
    st.sampled_from([
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert(1)>",
        "<svg/onload=alert('svg')>",
        "'; DROP TABLE outcomes; --",
        "\"onmouseover=\"alert(1)\"",
        "& < > \" ' ` = /",
        "Outcome with <b>bold</b> and <i>italic</i> tags",
        "🚀 Unicode outcome with emojis ✨ and linebreaks\n\t",
    ]),
)

status_strategy = st.sampled_from(["Approved", "Pending", "Rejected", "Unknown"])


@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture], deadline=None)
@given(
    outcomes=st.lists(dangerous_text, min_size=1, max_size=5),
    reviewer=dangerous_text,
    notes=dangerous_text,
    status=status_strategy,
)
def test_hypothesis_html_export_escapes_injections(
    tmp_path_factory: pytest.TempPathFactory,
    outcomes: list[str],
    reviewer: str,
    notes: str,
    status: str,
):
    tmp_path = tmp_path_factory.mktemp("hypo_repo")
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="HypoUAT")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.dev"], cwd=repo, check=True, capture_output=True)

    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)

    outcomes_lines = "\n".join(f"{i+1}. {o.replace(chr(10), ' ')}" for i, o in enumerate(outcomes))
    (prd_dir / "prd-0003-hypo.md").write_text(
        f"""---
id: '0003'
title: Generative PRD Testing
status: Accepted
target_persona: Taylor (The Product Manager)
component: prd
---

# PRD-0003 — Generative PRD Testing

## Checkable Outcomes

{outcomes_lines}
""",
        encoding="utf-8",
    )

    clean_reviewer = reviewer.replace("\n", " ").strip() or "Taylor <taylor@specops.local>"
    for i in range(len(outcomes)):
        record_uat_signoff(
            repo_root=repo,
            prd_id="PRD-0003",
            outcome_id=str(i + 1),
            reviewer=clean_reviewer,
            status=status,
            notes=notes.replace("\n", " "),
        )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup hypo repo"], cwd=repo, check=True, capture_output=True)

    html_doc, meta = render_uat_matrix_html(repo, "PRD-0003")

    # 1. Must be non-empty and well-formed
    assert "<!DOCTYPE html>" in html_doc
    assert "</html>" in html_doc

    validator = WellFormedHTMLValidator()
    validator.feed(html_doc)
    assert len(validator.errors) == 0

    # 2. Assert no unescaped script or img injection in table rows
    # The only <script> block in the entire document should be the template's own filterOutcomes script
    script_blocks = html_doc.split("<script>")
    assert len(script_blocks) == 2  # Exactly 1 template script block

    # Verify evil scripts are not injected as raw HTML tags
    assert "<script>alert('xss')</script>" not in html_doc
    assert "<img src=x onerror=alert(1)>" not in html_doc
    assert "<svg/onload=alert('svg')>" not in html_doc

    # 3. Cryptographic meta tags must be present and well-formed
    assert '<meta name="spec-ops:document" content="customer-uat-acceptance-matrix">' in html_doc
    assert f'<meta name="spec-ops:receipt-signature" content="{meta["signature"]}">' in html_doc
    assert f'<meta name="spec-ops:tree-digest" content="{meta["tree_digest"]}">' in html_doc
    assert f'<meta name="spec-ops:ledger-digest" content="{meta["ledger_digest"]}">' in html_doc
