"""
Desktop entry point for Option Price Calculator.
- Dev:  python launcher.py
- Build: PyInstaller — Windows (BUILD_WINDOWS.md), macOS (BUILD_MAC.md)

Uses Streamlit bootstrap directly (avoids click context required by streamlit.web.cli._main_run).
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _resource_path(rel: str) -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


def main() -> None:
    main_py = _resource_path("Main.py")
    if not os.path.isfile(main_py):
        sys.stderr.write(f"Missing Main.py (looked at {main_py})\n")
        sys.exit(1)

    port = os.environ.get("OPTIONCALC_PORT", "8501")
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    os.environ.setdefault("STREAMLIT_SERVER_PORT", port)
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENTMODE", "false")

    url = f"http://localhost:{port}"

    def _open_browser() -> None:
        time.sleep(2.2)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    main_script_path = os.path.abspath(main_py)

    from streamlit import config as st_config
    from streamlit.runtime.credentials import check_credentials
    from streamlit.web import bootstrap
    from streamlit.web.server.app_discovery import discover_asgi_app

    st_config._main_script_path = main_script_path
    bootstrap.load_config_options(flag_options={})
    check_credentials()

    discovery = discover_asgi_app(Path(main_script_path))
    if discovery.is_asgi_app:
        bootstrap.run_asgi_app(
            main_script_path,
            discovery.import_string,  # type: ignore[arg-type]
            [],
            {},
        )
    else:
        bootstrap.run(main_script_path, is_hello=False, args=[], flag_options={})


if __name__ == "__main__":
    main()
