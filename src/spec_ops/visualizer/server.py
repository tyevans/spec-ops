"""Lightweight development web server for SpecOps living visualizer and PRD Studio."""

from __future__ import annotations

import json
import queue
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from .generator import generate_standalone_html, serialize_project_data
from .prd_studio import commit_prd_specification, create_prd_draft
from .story_assistant import accept_user_story, extract_frontdoor_steps
from .studio_view import render_studio_html


class VisualizerHandler(BaseHTTPRequestHandler):
    config: SpecOpsConfig
    default_view: str = "visualizer"

    def _get_studio_manager(self) -> Any:
        root = getattr(self.config, "root_dir", Path.cwd())
        mgr = getattr(self.server, "studio_manager", None)
        if mgr is None:
            from ..prd.studio_state import PRDStudioStateManager

            mgr = PRDStudioStateManager(repo_root=root)
            self.server.studio_manager = mgr
        return mgr

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path.startswith("/api/studio/"):
            from ..prd.studio_api import dispatch_studio_api_request

            query_params = urllib.parse.parse_qs(parsed_url.query)
            code, res = dispatch_studio_api_request(
                self._get_studio_manager(), "GET", path, query_params=query_params
            )
            self._send_json(code, res)
        elif path in ("/", "/index.html"):
            if getattr(self, "default_view", "visualizer") == "studio":
                html = render_studio_html()
            else:
                html = generate_standalone_html(self.config)
            self._send_response_bytes(200, "text/html; charset=utf-8", html.encode("utf-8"))
        elif path in ("/prd-studio", "/studio"):
            html = render_studio_html()
            self._send_response_bytes(200, "text/html; charset=utf-8", html.encode("utf-8"))
        elif path == "/api/data":
            data = serialize_project_data(self.config)
            self._send_json(200, data)
        elif path in ("/api/prd/draft", "/api/prd/status"):
            query_params = urllib.parse.parse_qs(parsed_url.query)
            root = getattr(self.config, "root_dir", Path.cwd())
            from .prd_sync import handle_prd_draft_get

            code, res = handle_prd_draft_get(root, query_params)
            self._send_json(code, res)
        elif path == "/api/telemetry":
            from .lead_console import harvest_fleet_telemetry

            telemetry = harvest_fleet_telemetry(self.config)
            self._send_json(200, telemetry)
        elif path == "/api/steps/frontdoor":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            q = query_params.get("q", [None])[0]
            root = getattr(self.config, "root_dir", Path.cwd())
            steps = extract_frontdoor_steps(root, query=q)
            self._send_json(200, steps)
        elif path in ("/api/uat/export", "/uat/export"):
            query_params = urllib.parse.parse_qs(parsed_url.query)
            prd_id = query_params.get("prd", [None])[0]
            root = getattr(self.config, "root_dir", Path.cwd())
            if prd_id:
                from ..prd.uat_export import render_uat_matrix_html

                try:
                    html_doc, _ = render_uat_matrix_html(root, prd_id=prd_id)
                    self._send_response_bytes(200, "text/html; charset=utf-8", html_doc.encode("utf-8"))
                except Exception as exc:
                    self._send_json(400, {"success": False, "error": str(exc)})
            else:
                self._send_json(400, {"success": False, "error": "Missing 'prd' parameter"})
        elif path in ("/api/prd/journey", "/api/journey", "/journey"):
            query_params = urllib.parse.parse_qs(parsed_url.query)
            persona_filter = query_params.get("persona", [None])[0]
            fmt = query_params.get("format", ["json" if "api" in path else "html"])[0]
            root = getattr(self.config, "root_dir", Path.cwd())
            from ..prd.journey_map import JourneyMapEngine

            engine = JourneyMapEngine(repo_root=root, config=self.config)
            report = engine.correlate(persona_filter=persona_filter)
            if fmt == "html":
                html_doc = engine.generate_html(report)
                self._send_response_bytes(200, "text/html; charset=utf-8", html_doc.encode("utf-8"))
            else:
                self._send_json(200, report.to_dict())
        elif path == "/api/events/stream":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            limit_val = query_params.get("limit", ["50"])[0]
            since_val = query_params.get("since", query_params.get("since_sequence", ["0"]))[0]
            live_val = query_params.get("live", ["true"])[0].lower()
            live = live_val not in ("false", "0", "no")

            try:
                limit = int(limit_val)
            except ValueError:
                limit = 50
            try:
                since_seq = int(since_val)
            except ValueError:
                since_seq = 0

            root = getattr(self.config, "root_dir", Path.cwd())
            from ..core.event_streamer import get_event_streamer

            streamer = get_event_streamer(root)

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive" if live else "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            replayed = streamer.replay_events(limit=limit, since_sequence=since_seq)
            for ev in replayed:
                chunk = streamer.format_sse(ev)
                self.wfile.write(chunk.encode("utf-8"))
            self.wfile.flush()

            if not live:
                self.close_connection = True
                return

            sub_queue = streamer.subscribe_sync()
            try:
                while True:
                    try:
                        ev = sub_queue.get(timeout=0.5)
                        chunk = streamer.format_sse(ev)
                        self.wfile.write(chunk.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        if getattr(self.server, "_shutdown_event", False):
                            break
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                streamer.unsubscribe_sync(sub_queue)
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

        if path.startswith("/api/studio/"):
            from ..prd.studio_api import dispatch_studio_api_request

            code, res = dispatch_studio_api_request(
                self._get_studio_manager(), "POST", path, payload=payload
            )
            self._send_json(code, res)
            return

        if path == "/api/prd/save":
            from .prd_sync import handle_prd_save_post

            code, res = handle_prd_save_post(root, payload)
            self._send_json(code, res)
        elif path == "/api/prd/draft":
            if payload.get("content") is not None and (payload.get("file_path") or payload.get("path")):
                from .prd_sync import handle_prd_save_post

                code, res = handle_prd_save_post(root, payload)
                self._send_json(code, res)
            else:
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
        elif path == "/api/story/accept":
            res = accept_user_story(root, payload)
            code = 201 if res.get("success") else 400
            self._send_json(code, res)
        elif path == "/api/uat/signoff":
            from ..prd.uat import record_uat_signoff

            prd_id = payload.get("prd_id", "")
            outcome_id = payload.get("outcome_id", "")
            reviewer = payload.get("reviewer", "Taylor")
            status = payload.get("status", "Approved")
            notes = payload.get("notes", "")
            timestamp = payload.get("timestamp")

            if not prd_id or not outcome_id:
                self._send_json(400, {"success": False, "error": "Missing 'prd_id' or 'outcome_id'"})
                return

            entry = record_uat_signoff(
                repo_root=root,
                prd_id=prd_id,
                outcome_id=outcome_id,
                reviewer=reviewer,
                status=status,
                notes=notes,
                timestamp=timestamp,
            )
            self._send_json(200, {"success": True, "signoff": entry})
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


def serve_visualizer(
    config: SpecOpsConfig,
    host: str = "127.0.0.1",
    port: int = 8787,
    default_view: str = "visualizer",
) -> None:
    handler = VisualizerHandler
    handler.config = config
    handler.default_view = default_view
    server = ThreadingHTTPServer((host, port), handler)
    label = "SpecOps PRD Studio" if default_view == "studio" else "SpecOps Visualizer"
    print(f"⚡ {label} running at http://{host}:{port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n🛑 {label} stopped.")
        server.server_close()

