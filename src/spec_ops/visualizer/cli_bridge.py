"""CLI bridge and entity deep-linking for SpecOps visualizer."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.models import SpecOpsConfig


def normalize_entity_id(entity_id: str | None) -> str | None:
    """Normalizes an entity identifier into canonical uppercase format."""
    if not entity_id:
        return None
    cleaned = entity_id.strip()
    if not cleaned:
        return None
    if cleaned.isdigit():
        return f"TASK-{cleaned.zfill(4)}"
    return cleaned.upper()


def generate_entity_deep_link(
    entity_id: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8787,
    tab: str | None = None,
) -> str:
    """Generates the deep-link URL for visualizer entity inspection."""
    base_url = f"http://{host}:{port}/"
    clean_id = normalize_entity_id(entity_id)
    if not clean_id:
        if tab:
            return f"{base_url}#tab={tab}"
        return base_url

    if tab and tab != "graph":
        return f"{base_url}#tab={tab}&entity={clean_id}"
    return f"{base_url}#entity={clean_id}"


def handle_visualizer_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles visualizer CLI command invocation."""
    from .bundle import export_bundle
    from .server import serve_visualizer

    action = getattr(args, "viz_action", None)
    if action == "export":
        target = getattr(args, "out_pos", None) or getattr(args, "output", "dist/index.html")
        out_file = export_bundle(config, output_path=target)
        print(f"✅ Exported standalone visualizer bundle to {out_file}")
        return 0

    if getattr(args, "build", None):
        out_file = export_bundle(config, output_path=args.build)
        print(f"✅ Exported standalone visualizer bundle to {out_file}")
        return 0

    port = getattr(args, "port", 8787)
    host = getattr(args, "host", "127.0.0.1") if hasattr(args, "host") else "127.0.0.1"
    entity = getattr(args, "entity", None)

    target_url = generate_entity_deep_link(entity, host=host, port=port)

    # Launch browser if entity specified or requested
    if entity is not None:
        import threading
        import webbrowser

        def _open() -> None:
            import time

            time.sleep(0.3)
            try:
                webbrowser.open(target_url)
            except Exception:
                pass

        threading.Thread(target=_open, daemon=True).start()

    serve_visualizer(config, host=host, port=port)
    return 0
