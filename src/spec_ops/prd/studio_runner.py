"""PRD Studio server launcher and frontdoor execution runner."""

from __future__ import annotations

import threading
import time
import webbrowser
from typing import Any

from ..config.models import SpecOpsConfig
from ..visualizer.server import serve_visualizer


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

    if not block:
        t = threading.Thread(
            target=serve_visualizer,
            args=(config,),
            kwargs={"host": host, "port": port, "default_view": "studio"},
            daemon=True,
        )
        t.start()
        time.sleep(0.4)
        return 0

    serve_visualizer(config, host=host, port=port, default_view="studio")
    return 0
