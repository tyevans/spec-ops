"""Unit tests for PRD Studio user interface and component stories."""

from __future__ import annotations

import json

from spec_ops.prd.studio import KNOWN_PERSONAS
from spec_ops.prd.studio_ui import STUDIO_COMPONENT_STORIES, render_studio_html


def test_component_stories_catalog_structure():
    assert len(STUDIO_COMPONENT_STORIES) >= 5
    for name, story in STUDIO_COMPONENT_STORIES.items():
        assert "title" in story
        assert "description" in story
        assert "props" in story
        assert "default_state" in story
        assert isinstance(story["props"], list)
        assert isinstance(story["default_state"], dict)


def test_render_studio_html_empty_state():
    html = render_studio_html()
    assert "<!DOCTYPE html>" in html
    assert "<title>SpecOps PRD Studio</title>" in html
    assert 'id="prdTitle"' in html
    assert 'id="prdPersona"' in html
    assert 'id="prdComponent"' in html
    assert 'id="prdProblem"' in html
    assert 'id="outcomesContainer"' in html
    assert 'id="previewContent"' in html
    assert "Diataxis Live Preview" in html
    for p in KNOWN_PERSONAS:
        assert f'<option value="{p}">{p}</option>' in html


def test_render_studio_html_seeded_state():
    seed = {
        "session_id": "studio-seeded-99",
        "title": "Seeded Visualizer PRD",
        "persona": "Alex",
        "component": "visualizer",
        "problem_statement": "Graph layout lacks hierarchy.",
        "outcomes": ["Outcomes test line"],
        "stage": "shaped",
        "is_dirty": True,
        "is_valid": True,
    }
    html = render_studio_html(initial_state=seed)
    assert "studio-seeded-99" in html
    assert "Seeded Visualizer PRD" in html
    assert "/api/studio/draft/update" in html
    assert "/api/studio/draft/save" in html
    assert "/api/studio/draft/commit" in html
    assert "/api/studio/draft/promote" in html


def test_render_studio_html_zero_cdn_dependencies():
    """Verify strictly zero external CDN scripts or stylesheet dependencies (ADR-0003)."""
    html = render_studio_html()
    assert "cdn.jsdelivr.net" not in html
    assert "unpkg.com" not in html
    assert "cdnjs.cloudflare.com" not in html
    assert "fonts.googleapis.com" not in html
