"""Tests for standalone 2D project visualizer generator and multi-view templates."""

from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.generator import generate_standalone_html, serialize_project_data
from spec_ops.visualizer.template import SafeTemplate


def test_safe_template_keyword_substitution():
    """Verify SafeTemplate substitutes {key} without breaking CSS braces."""
    raw = "body { color: {text_color}; margin: 0; } .nav { padding: 1rem; }"
    tmpl = SafeTemplate(raw)
    result = tmpl.format(text_color="#FFFFFF")
    assert "color: #FFFFFF;" in result
    assert "margin: 0;" in result
    assert ".nav { padding: 1rem; }" in result


def test_visualizer_generation_on_scaffolded_project(tmp_path: Path):
    """Verify standalone HTML visualizer generates with all multi-view modules."""
    init_project(tmp_path, name="TestVisProject")
    config = load_config(root_dir=tmp_path)

    payload = serialize_project_data(config)
    assert payload["project"]["name"] == "TestVisProject"
    assert len(payload["nodes"]) >= 4
    assert len(payload["edges"]) >= 1
    assert "tasks" in payload
    assert "personas" in payload
    assert "stories" in payload
    assert "adrs" in payload

    html = generate_standalone_html(config)
    assert "<!DOCTYPE html>" in html
    assert "TestVisProject — SpecOps Visualizer" in html
    # Check tab buttons
    assert 'data-tab="graph"' in html
    assert 'data-tab="gantt"' in html
    assert 'data-tab="kanban"' in html
    assert 'data-tab="prds"' in html
    assert 'data-tab="adrs"' in html
    assert 'data-tab="personas"' in html
    # Check scripts embedded
    assert "window.switchTab = function(" in html
    assert "function renderGanttView(" in html
    assert "function renderKanbanView(" in html
    assert "function renderPrdsView(" in html
    assert "function renderAdrsView(" in html
    assert "function renderPersonasView(" in html
    assert "window.openDrawer = function(" in html
