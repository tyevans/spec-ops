"""Blackbox frontdoor tests for mobile responsive visualizer guided tour (US-0129, TASK-0252)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.bundle import compile_bundle, serialize_bundle_data
from spec_ops.visualizer.styles import VISUALIZER_CSS
from spec_ops.visualizer.template import VISUALIZER_HTML_TEMPLATE
from spec_ops.visualizer.tour_script import TOUR_CSS, TOUR_JS


def test_tour_overlay_has_no_backdrop_blur():
    """Verify that .tour-overlay does NOT apply backdrop-filter blur."""
    assert "backdrop-filter: blur" not in TOUR_CSS
    assert ".tour-overlay" in TOUR_CSS
    # Ensure overlay uses a clean, transparent backdrop
    assert "background: rgba(15, 23, 42, 0.45)" in TOUR_CSS or "rgba(15, 23, 42" in TOUR_CSS


def test_tour_css_mobile_responsiveness():
    """Verify responsive media queries and containment rules in TOUR_CSS."""
    assert "@media (max-width: 768px)" in TOUR_CSS
    assert "max-width: 100vw" in TOUR_CSS
    assert "overflow-y: auto" in TOUR_CSS
    assert "flex-wrap: wrap" in TOUR_CSS


def test_visualizer_css_mobile_overflow_prevention():
    """Verify html, body prevent horizontal blowout on mobile viewports."""
    assert "html, body" in VISUALIZER_CSS
    assert "max-width: 100vw" in VISUALIZER_CSS
    assert "overflow-x: hidden" in VISUALIZER_CSS
    assert "@media (max-width: 768px)" in VISUALIZER_CSS


def test_visualizer_template_tag_nesting_integrity():
    """Verify modal divs are properly closed and not nested inside each other."""
    rendered = VISUALIZER_HTML_TEMPLATE.format(title="Test", back_link="index.html", data_json="{}")

    # Ensure drift-audit-modal is NOT inside tour-modal
    tour_modal_idx = rendered.find('id="tour-modal"')
    assert tour_modal_idx != -1

    drift_modal_idx = rendered.find('id="drift-audit-modal"')
    assert drift_modal_idx != -1

    # Between tour-modal and drift-audit-modal, there must be two closing </div> tags
    snippet_between = rendered[tour_modal_idx:drift_modal_idx]
    close_div_count = snippet_between.count("</div>")
    open_div_count = snippet_between.count("<div")
    assert close_div_count >= open_div_count, "tour-modal or tour-overlay not properly closed before drift-audit-modal"


def test_tour_js_scroll_into_view_support():
    """Verify applyTourHighlight attempts to scroll highlighted element into view."""
    assert "scrollIntoView" in TOUR_JS
    assert "tour-highlight" in TOUR_JS


def test_compiled_bundle_contains_mobile_tour_fixes(tmp_path: Path):
    """Verify fully compiled HTML bundle includes responsive styles and no backdrop blur."""
    init_project(tmp_path, name="MobileTourTest")
    config = load_config(root_dir=tmp_path)
    html = compile_bundle(config)

    # Blur filter must be absent from tour-overlay
    overlay_match = re.search(r"\.tour-overlay\s*\{([^}]+)\}", html)
    assert overlay_match is not None
    overlay_rules = overlay_match.group(1)
    assert "backdrop-filter: blur" not in overlay_rules

    # Mobile media query must be present
    assert "@media (max-width: 768px)" in html
    assert "id=\"tour-modal\"" in html
    assert "id=\"welcome-modal\"" in html
