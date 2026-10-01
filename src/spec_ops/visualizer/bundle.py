"""Standalone portable single-file HTML bundle compiler and exporter for SpecOps visualizer."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from .generator import serialize_project_data
from .lead_console import harvest_fleet_telemetry
from .template import VISUALIZER_HTML_TEMPLATE

# 5MB size limit invariant for standalone air-gapped bundle
MAX_BUNDLE_BYTES: int = 5 * 1024 * 1024


def validate_airgap_integrity(html_content: str) -> bool:
    """Validates that the standalone HTML bundle contains zero external CDN or network dependencies."""
    external_scripts = re.findall(r'<script\b[^>]*\bsrc=["\'](https?://[^"\']+)["\']', html_content, re.IGNORECASE)
    external_links = re.findall(r'<link\b[^>]*\bhref=["\'](https?://[^"\']+)["\']', html_content, re.IGNORECASE)
    return len(external_scripts) == 0 and len(external_links) == 0


def serialize_bundle_data(config: SpecOpsConfig) -> dict[str, Any]:
    """Serializes project graph along with live agent fleet telemetry for offline bundle."""
    data = serialize_project_data(config)
    telemetry = harvest_fleet_telemetry(config)
    data["telemetry"] = telemetry
    return data


def compile_bundle(config: SpecOpsConfig, back_link: str = "../index.html") -> str:
    """Compiles complete zero-dependency, self-contained HTML visualizer bundle."""
    payload = serialize_bundle_data(config)
    data_json = json.dumps(payload).replace("<", "\\u003c")
    title = config.project.name
    return VISUALIZER_HTML_TEMPLATE.format(
        title=title,
        data_json=data_json,
        back_link=back_link,
    )


def export_bundle(
    config: SpecOpsConfig,
    output_path: str | Path = "dist/index.html",
    back_link: str = "../index.html",
) -> Path:
    """Compiles and writes self-contained HTML visualizer bundle to disk, verifying size and airgap integrity."""
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    html = compile_bundle(config, back_link=back_link)

    if not validate_airgap_integrity(html):
        raise ValueError("Airgap integrity check failed: external scripts or stylesheets detected.")

    out_file.write_text(html, encoding="utf-8")

    size_bytes = out_file.stat().st_size
    if size_bytes > MAX_BUNDLE_BYTES:
        raise ValueError(
            f"Exported visualizer bundle size ({size_bytes} bytes) exceeds {MAX_BUNDLE_BYTES} byte (5MB) limit."
        )

    return out_file
