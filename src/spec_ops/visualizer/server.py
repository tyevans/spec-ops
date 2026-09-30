"""Lightweight development web server for SpecOps living visualizer and PRD Studio."""

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..prd.step_assistant import extract_frontdoor_steps
from ..prd.studio import commit_prd_specification, create_prd_draft
from .generator import generate_standalone_html, serialize_project_data
from .studio_view import render_studio_html


class VisualizerHandler(BaseHTTPRequestHandler):
    config: SpecOpsConfig

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in ("/", "/index.html"):
            html = generate_standalone_html(self.config)
            self._send_response_bytes(200, "text/html; charset=utf-8", html.encode("utf-8"))
        elif path in ("/prd-studio", "/studio"):
            html = render_studio_html()
            self._send_response_bytes(200, "text/html; charset=utf-8", html.encode("utf-8"))
        elif path == "/api/data":
            data = serialize_project_data(self.config)
            self._send_json(200, data)
        elif path == "/api/steps/frontdoor":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            q = query_params.get("q", [None])[0]
            root = getattr(self.config, "root_dir", Path.cwd())
            steps = extract_frontdoor_steps(root, query=q)
            self._send_json(200, steps)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"

        try:
            payload = json.loads(post_body.decode("utf-8")) if post_body else {}
        except Exception:
            self._send_json(400, {"success": False, "error": "Invalid JSON body"})
            return

        root = getattr(self.config, "root_dir", Path.cwd())

        if path == "/api/prd/draft":
            res = create_prd_draft(root, payload)
            code = 201 if res.get("success") else 400
            self._send_json(code, res)
        elif path == "/api/prd/commit":
            file_path = payload.get("file_path")
            content = payload.get("content")
            if not file_path:
                self._send_json(400, {"success": False, "error": "Missing 'file_path'"})
                return

            if content is None:
                # If content is not provided, read existing from disk
                target = (Path(root) / file_path).resolve()
                if not target.exists():
                    self._send_json(400, {"success": False, "error": f"File not found: {file_path}"})
                    return
                content = target.read_text(encoding="utf-8")

            res = commit_prd_specification(
                repo_root=root,
                file_path=file_path,
                content=content,
                commit_message=payload.get("commit_message"),
                author_name=payload.get("author_name", "Taylor"),
                author_email=payload.get("author_email", "taylor@specops.local"),
            )
            code = 200 if res.get("success") else 400
            self._send_json(code, res)
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, status_code: int, data: Any) -> None:
        payload = json.dumps(data)
        self._send_response_bytes(status_code, "application/json", payload.encode("utf-8"))

    def _send_response_bytes(self, status_code: int, content_type: str, body: bytes) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
