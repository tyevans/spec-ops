"""Lightweight development web server for SpecOps living visualizer."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from .generator import generate_standalone_html, serialize_project_data


class VisualizerHandler(BaseHTTPRequestHandler):
    config: SpecOpsConfig

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            html = generate_standalone_html(self.config)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        elif self.path == "/api/data":
            data = serialize_project_data(self.config)
            payload = json.dumps(data)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(payload.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # Minimal logging
        pass


def serve_visualizer(config: SpecOpsConfig, host: str = "127.0.0.1", port: int = 8787) -> None:
    handler = VisualizerHandler
    handler.config = config
    server = HTTPServer((host, port), handler)
    print(f"⚡ SpecOps Visualizer running at http://{host}:{port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 SpecOps Visualizer stopped.")
        server.server_close()
