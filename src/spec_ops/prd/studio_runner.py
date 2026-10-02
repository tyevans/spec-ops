"""PRD Studio server launcher and frontdoor execution runner.

Governed by ADR-0007, ADR-0021. Decoupled from visualizer via callback registration.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable
import webbrowser

from ..config.models import SpecOpsConfig

_server_launcher: Callable[..., Any] | None = None


def register_default_server_launcher(launcher: Callable[..., Any]) -> None:
    """Registers the server launcher callback for PRD Studio."""
    global _server_launcher
    _server_launcher = launcher


def _get_server_launcher() -> Callable[..., Any]:
    global _server_launcher
    if _server_launcher is not None:
        return _server_launcher
    import importlib
    mod = importlib.import_module("spec_ops.visualizer.server")
    return getattr(mod, "serve_visualizer")


def launch_prd_studio(
    config: SpecOpsConfig,
    host: str = "127.0.0.1",
    port: int = 8787,
    open_browser: bool = False,
    block: bool = True,
) -> int:
    """Launches local web server for PRD Studio with optional browser auto-open."""
    if open_browser:
        def _open() -> None:
            time.sleep(0.5)
            webbrowser.open(f"http://{host}:{port}/studio")

        threading.Thread(target=_open, daemon=True).start()

    launcher = _get_server_launcher()

    if not block:
        t = threading.Thread(
            target=launcher,
            args=(config,),
            kwargs={"host": host, "port": port, "default_view": "studio"},
            daemon=True,
        )
        t.start()
        time.sleep(0.4)
        return 0

    launcher(config, host=host, port=port, default_view="studio")
    return 0
