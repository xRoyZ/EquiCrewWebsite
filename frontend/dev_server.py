"""Development server for the EquiCrew website (standard library only).

Serves the files of this directory on the port from the environment variable PORT
(default 8000). Directory URLs such as /kontakt/ answer with their index.html.
The path /js/config.js is answered dynamically with the API origin from the
environment variable API_BASE_URL; when it is unset, the static file is served,
whose apiBase "" means "same origin".

Usage:  PORT=8000 API_BASE_URL=http://localhost:8001 python3 dev_server.py
"""

from __future__ import annotations

import json
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = "/js/config.js"
DEFAULT_PORT = 8000

# Content types of the files this site serves, independent of the host's mime database.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".woff2": "font/woff2",
    ".webp": "image/webp",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
}


def config_script(api_base: str) -> bytes:
    """Return the body of /js/config.js for the given API origin."""
    config = {"apiBase": api_base.rstrip("/")}
    return f"window.EQUICREW_CONFIG = {json.dumps(config)};\n".encode()


class SiteHandler(SimpleHTTPRequestHandler):
    """Static file handler with a dynamic /js/config.js."""

    def guess_type(self, path: str | os.PathLike[str]) -> str:
        known = CONTENT_TYPES.get(Path(path).suffix.lower())
        return known or super().guess_type(path)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _api_base(self) -> str | None:
        value = os.environ.get("API_BASE_URL", "").strip()
        return value or None

    def _send_config(self, head_only: bool) -> None:
        body = config_script(self._api_base() or "")
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_GET(self) -> None:
        if urlsplit(self.path).path == CONFIG_PATH and self._api_base() is not None:
            self._send_config(head_only=False)
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if urlsplit(self.path).path == CONFIG_PATH and self._api_base() is not None:
            self._send_config(head_only=True)
            return
        super().do_HEAD()

    def log_message(self, format: str, *args: object) -> None:
        # Request line and status only; the visitor's address is not written to the log.
        sys.stderr.write(f"[web] {format % args}\n")


def read_port() -> int:
    """Read PORT from the environment, naming the variable when it is not a valid port."""
    raw = os.environ.get("PORT", "").strip()
    if not raw:
        return DEFAULT_PORT
    try:
        port = int(raw)
    except ValueError:
        raise SystemExit(f"PORT must be a number between 1 and 65535, got {raw!r}") from None
    if not 0 < port < 65536:
        raise SystemExit(f"PORT must be a number between 1 and 65535, got {raw!r}")
    return port


def make_server(port: int, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    """Create (but do not start) the HTTP server for this directory."""
    handler = partial(SiteHandler, directory=str(ROOT))
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    port = read_port()
    try:
        server = make_server(port)
    except OSError as exc:
        raise SystemExit(f"Cannot listen on port {port}: {exc.strerror or exc}") from None
    api = os.environ.get("API_BASE_URL", "").strip() or "same origin"
    print(f"[web] serving {ROOT} on http://localhost:{port}/ (API: {api})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
